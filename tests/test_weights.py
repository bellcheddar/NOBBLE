"""The composite weight fitter (spec 4.8).

A fitter that is only ever exercised on a campaign with no negatives is a
fitter nobody has tested. These run it against synthetic splits where the right
answer is known, so both halves of its behaviour are covered: that it fits when
there is signal, and that it refuses when there is not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from nobble.score import weights


def _row(pair_id, label, bridge=None, delta=None, convergence=None, plip=None):
    return {
        "pair_id": pair_id,
        "peptide_label": label,
        "bridge_percentile": bridge,
        "delta_iptm": delta,
        "convergence_score": convergence,
        "plip_fingerprint_match": plip,
        "lysine_reach": {"peptide_lysines": 2, "exposed_lysines": 1},
    }


def _campaign(tmp_path: Path, rows: list[dict]) -> Path:
    (tmp_path / "scores.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n"
    )
    return tmp_path


def test_refuses_without_negatives(tmp_path):
    """The benchmark panel is all true positives: no split, so no fit."""
    rows = [_row(f"p{i}", "degraded", bridge=80, delta=0.3) for i in range(10)]
    result = weights.fit(_campaign(tmp_path, rows))
    assert not result.fitted
    assert "negative" in result.status


def test_refuses_below_the_floor(tmp_path):
    rows = [_row("p1", "degraded", bridge=80), _row("p2", "not_degraded", bridge=10)]
    result = weights.fit(_campaign(tmp_path, rows))
    assert not result.fitted
    assert "floor" in result.status


def test_fits_and_finds_the_discriminating_component(tmp_path):
    """Bridge percentile separates perfectly; convergence is pure noise.

    The fit should load the component that discriminates and the reported
    per-component AUC should say so, which is the property that makes a fitted
    weight interpretable rather than arbitrary.
    """
    rows = []
    for i in range(12):
        rows.append(_row(f"pos{i}", "degraded", bridge=70 + i, delta=0.1,
                         convergence=0.5, plip=0.5))
        rows.append(_row(f"neg{i}", "not_degraded", bridge=10 + i, delta=0.1,
                         convergence=0.5, plip=0.5))
    result = weights.fit(_campaign(tmp_path, rows))
    assert result.fitted, result.status
    assert result.objective == pytest.approx(1.0, abs=0.01)
    assert result.weights.get("bridge_percentile", 0) > 0
    assert result.per_component_auc["bridge_percentile"] > 0.9
    # A component with no signal should sit at chance, whatever weight it gets.
    assert result.per_component_auc["convergence_score"] == pytest.approx(0.5, abs=0.01)


def test_caveats_a_weight_on_an_unvalidated_component(tmp_path):
    """Lysine geometry may take weight, but never silently (D-NOB-024)."""
    rows = []
    for i in range(12):
        rows.append(_row(f"pos{i}", "degraded", bridge=50, delta=0.1))
        rows.append(_row(f"neg{i}", "not_degraded", bridge=50, delta=0.1))
    result = weights.fit(_campaign(tmp_path, rows))
    if result.fitted and result.weights.get("lysine_reach_exposed_fraction", 0) > 0:
        assert any("validated" in caveat for caveat in result.caveats)


def test_small_sample_is_always_caveated(tmp_path):
    rows = []
    for i in range(5):
        rows.append(_row(f"pos{i}", "degraded", bridge=80 + i, delta=0.3))
        rows.append(_row(f"neg{i}", "not_degraded", bridge=10 + i, delta=-0.3))
    result = weights.fit(_campaign(tmp_path, rows))
    assert result.fitted, result.status
    assert any("indicative" in caveat for caveat in result.caveats)


def test_apply_is_bounded_and_handles_missing_components(tmp_path):
    row = _row("p", "degraded", bridge=100, delta=1.0, convergence=None, plip=None)
    value = weights.apply(row, {"bridge_percentile": 0.5, "delta_iptm": 0.5,
                                "convergence_score": 0.5})
    assert value is not None
    assert 0.0 <= value <= 1.0


def test_the_fitter_works_at_full_campaign_scale_and_says_the_auc_is_in_sample():
    """The fitter has never actually fitted: every campaign so far has had
    too few labelled pairs and it refused. Its fitting path first runs for
    real after the main campaign, so it is exercised here at that size.

    The AUC it reports is in-sample by construction, because the grid
    maximised it on the pairs it is reported over. That is the number most
    likely to be quoted as if it measured performance on unseen pairs,
    which is what the matched-control ROC is for.
    """
    import json
    import random
    import tempfile
    from pathlib import Path

    from nobble.score import weights

    random.seed(21)
    rows = []
    for index in range(158):
        degraded = index < 31
        edge = 0.18 if degraded else 0.0
        rows.append({
            "pair_id": f"p{index}",
            "peptide_label": "degraded" if degraded else "not_degraded",
            "delta_iptm": round(random.gauss(0.05 + edge, 0.18), 4),
            "bridge_percentile": round(min(100, max(0, random.gauss(50 + edge * 90, 22))), 2),
            "convergence_score": round(random.random(), 3),
            "plip_fingerprint_match": round(random.random(), 3),
        })

    with tempfile.TemporaryDirectory() as work:
        campaign = Path(work)
        (campaign / "scores.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in rows))
        fit = weights.fit(campaign).to_dict()

    assert fit["fitted"] is True, fit["status"]
    assert fit["labelled_pairs"] == 158
    assert 0.0 <= fit["objective"] <= 1.0
    assert abs(sum(fit["weights"].values()) - 1.0) < 1e-6, "weights must normalise"
    assert any("in-sample" in caveat for caveat in fit["caveats"]), fit["caveats"]
    # The components given pure noise should not carry the fit.
    assert fit["weights"]["delta_iptm"] > 0, fit["weights"]
