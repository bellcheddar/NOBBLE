"""A difference of minima is only comparable between pairs sampled alike.

`delta_iptm` is `iptm_min_ternary - iptm_min_binary`, and a minimum over ten
draws sits below a minimum over five whatever the underlying distribution.
Every Sievers pair contributes 5 binary and 10 ternary seeds, so the ROC,
which is scoped to that arm, compares like with like and
`matched_control_roc` refuses when it does not.

The weight fit is deliberately not scoped that way: spec 4.8 fits on the
benchmark panel and the Sievers matched set, so `_label` spans both. That
means it inherits the panel's irregular pairs. On the main campaign two of
158 have 5 ternary rather than 10, one benchmark and one scramble, because
their conditioned arm was dropped for having no pocket, which is the same ten
jobs `campaign.json` records as `conditioned_jobs_dropped_no_pocket`.

Two pairs out of 158 do not move a weight searched on a five-point grid, so
the fit reports the composition rather than refusing. What it must not do is
stay silent, because a panel with more irregular pairs or a finer grid would
make it matter (F104).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.score.weights import fit  # noqa: E402
from nobble.execute.campaign import latest_or_absent as _newest  # noqa: E402


def _campaign(tmp_path: Path, rows: list[dict]) -> Path:
    campaign = tmp_path / "campaign_shapes"
    campaign.mkdir()
    (campaign / "scores.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n")
    return campaign


def _row(pair: str, label: str, binary: int | None, ternary: int | None) -> dict:
    row = {"pair_id": pair, "peptide_label": label, "delta_iptm": -0.05,
           "bridge_percentile": 50.0}
    if binary is not None:
        row["seeds_binary"] = binary
    if ternary is not None:
        row["seeds_ternary"] = ternary
    return row


def test_a_uniform_panel_reports_one_shape_and_no_caveat(tmp_path):
    campaign = _campaign(tmp_path, [
        _row(f"p{i}", "degraded" if i < 3 else "not_degraded", 5, 10)
        for i in range(8)
    ])
    result = fit(campaign)
    assert result.seed_shapes == {"5 binary, 10 ternary": 8}
    assert not any("different number of seeds" in c for c in result.caveats)


def test_an_irregular_pair_is_counted_and_caveated(tmp_path):
    campaign = _campaign(tmp_path, [
        _row(f"p{i}", "degraded" if i < 3 else "not_degraded", 5, 10)
        for i in range(7)
    ] + [_row("odd", "negative_control", 5, 5)])
    result = fit(campaign)
    assert result.seed_shapes == {"5 binary, 10 ternary": 7, "5 binary, 5 ternary": 1}
    caveat = next(c for c in result.caveats if "different number of seeds" in c)
    assert "1 of 8 labelled pair(s)" in caveat
    assert "5 binary, 10 ternary" in caveat


def test_the_modal_shape_leads_the_count(tmp_path):
    """So the caveat names the shape most pairs actually have, not whichever
    one happened to be read first."""
    campaign = _campaign(tmp_path, [_row("a", "degraded", 5, 5)]
                         + [_row(f"p{i}", "not_degraded", 5, 10) for i in range(6)])
    result = fit(campaign)
    assert list(result.seed_shapes)[0] == "5 binary, 10 ternary"
    assert "modal 5 binary, 10 ternary" in next(
        c for c in result.caveats if "different number of seeds" in c)


def test_rows_without_seed_counts_are_named_not_assumed(tmp_path):
    """Score files written before the counts existed. Folding them into a
    shape would invent a fact about them."""
    campaign = _campaign(tmp_path, [
        _row(f"p{i}", "degraded" if i < 3 else "not_degraded", 5, 10)
        for i in range(6)
    ] + [_row("old", "not_degraded", None, None)])
    result = fit(campaign)
    assert result.seed_shapes.get("seed counts not recorded") == 1


def test_the_composition_is_reported_even_when_the_fit_refuses(tmp_path):
    """The fit refuses below a floor of labelled pairs, and that refusal
    returns early. A diagnostic that only appears on success is no use while
    a campaign is still filling, which is exactly when it is read."""
    campaign = _campaign(tmp_path, [_row("a", "degraded", 5, 10),
                                    _row("b", "not_degraded", 5, 5)])
    result = fit(campaign)
    assert result.status.startswith("not_fitted"), result.status
    assert result.seed_shapes, "the refused fit reported no composition"
    assert sum(result.seed_shapes.values()) == 2


def test_the_live_panel_shows_the_dropped_conditioned_arm():
    """The real case. The benchmark panel has one pair whose conditioned arm
    was dropped for having no pocket, so it contributes 5 ternary against the
    other six at 10."""
    campaign = _newest("benchmark")
    if not (campaign / "scores.jsonl").exists():
        pytest.skip("no benchmark scores")
    result = fit(campaign)
    assert result.seed_shapes, result.status
    assert result.seed_shapes.get("5 binary, 5 ternary") == 1, result.seed_shapes
    assert result.seed_shapes.get("5 binary, 10 ternary") == 6, result.seed_shapes


def test_the_roc_still_refuses_where_the_fit_reports():
    """The two consumers must not converge. The ROC is the falsifiable test
    and has to refuse on incomparable minima; the fit spans a wider panel by
    design and would lose pairs the spec tells it to use."""
    source = (ROOT / "nobble" / "validate" / "layers.py").read_text()
    assert "not comparable" in source, (
        "matched_control_roc no longer refuses on uneven seed counts"
    )
    weights = (ROOT / "nobble" / "score" / "weights.py").read_text()
    assert "Reported rather than refused" in weights
