"""An unmeasurable seed is not a seed that failed to bridge.

bridge_formation_rate is `bridged / total`, and `total` counted every
BridgeScore the geometry returned. Most reject reasons are real findings:
BINMAN's "single_chain:1_qualifying_of_1" means the glue buried surface
against one chain rather than two, which is the whole of spec 4.1 and
belongs in the denominator.

Four reasons are not findings. They are assigned before any geometry runs
and say the input was unusable: no structure, no ligand chain in the
output, no peptide chain, or a binary complex. Counting those as seeds
that did not bridge reports a prediction nobody could assess as one that
failed.

Latent so far. Every reject reason in every campaign to date is the
single_chain verdict. The main campaign is 1,573 ternary jobs with a
fallback ladder that expects some to fail, which is why this is fixed
before it runs rather than after.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.score import geometry  # noqa: E402


def _bridge(found, reason=None):
    return geometry.BridgeScore(
        job_id="j", structure="s.cif", found=found, reject_reason=reason,
        bridge_percentile=88.0 if found else None,
        dsasa_total=300.0 if found else None,
        bridging_balance=0.4 if found else None,
    )


def _score(monkeypatch, tmp_path, scores):
    """Score one pair whose ternary seeds return the given BridgeScores."""
    from nobble.score import run as run_module

    campaign = tmp_path / "campaign_x"
    (campaign / "outputs").mkdir(parents=True)
    jobs = []
    for index, _ in enumerate(scores):
        structure = campaign / "outputs" / f"s{index}.cif"
        structure.write_text("data_x\n")
        jobs.append({
            "job_id": f"j{index}", "pair_id": "p1", "seed": index + 1,
            "complex_type": "ternary", "conditioning": "unconstrained",
            "construct": "CRBN_CULT", "e3_gene": "CRBN", "peptide_id": "pep",
            "tier": "benchmark", "tokens": 400, "tier_setting": 1,
            "structure": str(structure),
            "confidence": {"pair_chains_iptm": {"0": {"1": 0.5}, "1": {"0": 0.5}}},
        })
    (campaign / "results.jsonl").write_text(
        "\n".join(json.dumps(j) for j in jobs) + "\n")

    sequence = list(scores)
    monkeypatch.setattr(run_module.geometry, "score_structure",
                        lambda job: sequence[int(job["job_id"][1:])])
    monkeypatch.setattr(run_module.geometry, "contact_map",
                        lambda job: {"status": "ok"})
    monkeypatch.setattr(run_module, "plip", type("P", (), {
        "fingerprint": staticmethod(lambda job: type("F", (), {
            "status": "failed: stubbed", "canonical_matched": [],
            "peptide_contacts": [], "to_dict": lambda self: {"status": "failed: stubbed"},
        })()),
        "CANONICAL_FINGERPRINTS": {},
    })())

    run_module.score_campaign(campaign)
    rows = [json.loads(line) for line in
            (campaign / "scores.jsonl").read_text().splitlines() if line.strip()]
    return rows[0]


def test_a_real_negative_still_counts_in_the_denominator(monkeypatch, tmp_path):
    """The single_chain verdict is a finding, not a failure."""
    row = _score(monkeypatch, tmp_path, [
        _bridge(True), _bridge(True), _bridge(True),
        _bridge(False, "single_chain:1_qualifying_of_1"),
        _bridge(False, "single_chain:1_qualifying_of_1"),
    ])
    assert row["bridging_seeds_total"] == 5
    assert row["bridging_seeds_with_bridge"] == 3
    assert row["bridge_formation_rate"] == 0.6
    assert row["bridging_seeds_unmeasurable"] == 0
    assert row["bridge_reject_reasons"] == {"single_chain:1_qualifying_of_1": 2}


def test_an_unmeasurable_seed_leaves_the_denominator(monkeypatch, tmp_path):
    """Four of eight bridged, four could not be assessed: 1.0 of what was
    measurable, not 0.5 of everything."""
    row = _score(monkeypatch, tmp_path, [
        _bridge(True), _bridge(True), _bridge(True), _bridge(True),
        _bridge(False, "no_ligand_chain_in_output"),
        _bridge(False, "no_ligand_chain_in_output"),
        _bridge(False, "structure_missing"),
        _bridge(False, "no_peptide_chain_in_output"),
    ])
    assert row["bridging_seeds_total"] == 4
    assert row["bridging_seeds_with_bridge"] == 4
    assert row["bridge_formation_rate"] == 1.0
    assert row["bridging_seeds_unmeasurable"] == 4
    assert row["bridging_unmeasurable_reasons"] == {
        "no_ligand_chain_in_output": 2,
        "structure_missing": 1,
        "no_peptide_chain_in_output": 1,
    }
    # And the unmeasurable ones are not described as negatives.
    assert row["bridge_reject_reasons"] == {}


def test_the_two_kinds_are_reported_side_by_side(monkeypatch, tmp_path):
    row = _score(monkeypatch, tmp_path, [
        _bridge(True),
        _bridge(False, "single_chain:1_qualifying_of_1"),
        _bridge(False, "structure_missing"),
    ])
    assert row["bridging_seeds_total"] == 2
    assert row["bridge_formation_rate"] == 0.5
    assert row["bridging_seeds_unmeasurable"] == 1
    assert row["bridge_reject_reasons"] == {"single_chain:1_qualifying_of_1": 1}


def test_a_pair_with_nothing_measurable_reports_no_rate(monkeypatch, tmp_path):
    """Not a rate of zero: there is no denominator."""
    row = _score(monkeypatch, tmp_path, [
        _bridge(False, "structure_missing"),
        _bridge(False, "structure_missing"),
    ])
    assert row["bridging_seeds_total"] == 0
    assert row["bridge_formation_rate"] is None
    assert row["bridging_seeds_unmeasurable"] == 2


def test_the_failure_list_names_reasons_geometry_actually_assigns():
    """An allowlist of strings drifts the moment a reason is renamed."""
    source = (ROOT / "nobble" / "score" / "geometry.py").read_text()
    for reason in geometry.MEASUREMENT_FAILURES:
        assert f'"{reason}"' in source, (
            f"{reason!r} is in MEASUREMENT_FAILURES but geometry no longer "
            "assigns it"
        )
