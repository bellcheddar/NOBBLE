"""Did refinement move the poses, and does the tool say so honestly?

The instrument Gate G6 turns on (F212). The failure it has to be proof
against is its own: a pose that moved 0.37 A from 5.36 to 4.99 crosses the
5 A breakpoint, and the first version of the verdict reported that as
"refinement crossed 5.0 A", which turns a pose measured twice into a
recovery.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import recovery_delta                                   # noqa: E402
from nobble import paths                                # noqa: E402
from nobble.validate.layers import RECOVERY_TARGETS     # noqa: E402

MARGIN = float(paths.thresholds()["scoring"]["campaign_change_margin_a"])
BREAKPOINTS = [float(point) for point
               in paths.thresholds()["scoring"]["rmsd_breakpoints"]]


class _Result:
    """What recovery_against_crystal returns, reduced to what is read."""

    def __init__(self, rmsd, anchor=1.0, identity=1.0):
        self.rmsd = rmsd
        self.receptor_rmsd = anchor
        self.peptide_identity = identity


def _campaign(tmp_path: Path, pairs: dict[str, tuple[float, float]]) -> Path:
    """One ternary job per pair, with a tier-1 and a tier-2 RMSD each."""
    campaign = tmp_path / "campaign_rd"
    campaign.mkdir(exist_ok=True)
    tier1, tier2 = [], []
    for pair_id in pairs:
        job_id = f"{pair_id}__ternary__conditioned__seed1"
        tier1.append({"job_id": job_id, "pair_id": pair_id,
                      "complex_type": "ternary", "status": "done"})
        tier2.append({"job_id": job_id + "__tier2", "pair_id": pair_id,
                      "complex_type": "ternary", "status": "done"})
    (campaign / "results.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in tier1))
    (campaign / "results_tier2.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in tier2))
    return campaign


@pytest.fixture
def stub(monkeypatch):
    """Resolve each job to the RMSD the test asked for."""
    table: dict[str, tuple[float, float]] = {}

    def fake(job):
        before, after = table[job["pair_id"]]
        return _Result(after if job["job_id"].endswith("__tier2") else before)

    monkeypatch.setattr(recovery_delta, "_recovery", fake)
    monkeypatch.setattr(recovery_delta.layers, "recovery_target",
                        lambda pair_id: {"pdb_id": "0XXX", "substrate_chain": "B",
                                         "substrate_acc": "P0", "receptor_chain": "A",
                                         "receptor_acc": "P1"})
    return table


def test_a_move_inside_the_margin_is_not_reported_as_a_crossing(tmp_path, stub):
    # 5.36 -> 4.99 is the live case: it crosses 5 A and moves 0.37 A.
    pair = sorted(RECOVERY_TARGETS)[0]
    stub[pair] = (5.36, 4.99)
    report = recovery_delta.compare(_campaign(tmp_path, stub))
    assert report["status"] == "computed"
    verdict = recovery_delta.verdict(report)
    assert "did not move the poses" in verdict, verdict
    assert "crossed" not in verdict, verdict
    # The crossing is still reported, as the lesser fact it is.
    assert "far side of a breakpoint" in verdict, verdict


def test_a_real_improvement_is_reported_as_a_crossing(tmp_path, stub):
    pair = sorted(RECOVERY_TARGETS)[0]
    stub[pair] = (17.5, 1.8)
    report = recovery_delta.compare(_campaign(tmp_path, stub))
    verdict = recovery_delta.verdict(report)
    assert "crossed" in verdict, verdict
    assert report["improved"] == 1
    assert report["worsened"] == 0


def test_a_real_regression_is_not_dressed_up(tmp_path, stub):
    pair = sorted(RECOVERY_TARGETS)[0]
    stub[pair] = (6.0, 20.0)
    report = recovery_delta.compare(_campaign(tmp_path, stub))
    verdict = recovery_delta.verdict(report)
    assert "further" in verdict, verdict
    assert "crossed" not in verdict, verdict
    assert report["worsened"] == 1


def test_partial_coverage_says_so(tmp_path, stub):
    pair = sorted(RECOVERY_TARGETS)[0]
    stub[pair] = (17.5, 17.4)
    report = recovery_delta.compare(_campaign(tmp_path, stub))
    assert report["pairs_compared"] == 1
    assert report["pairs_expected"] == len(RECOVERY_TARGETS)
    assert "so this is partial" in recovery_delta.verdict(report)


def test_a_complete_panel_does_not_say_partial(tmp_path, stub):
    for pair_id in RECOVERY_TARGETS:
        stub[pair_id] = (17.5, 17.4)
    report = recovery_delta.compare(_campaign(tmp_path, stub))
    assert report["pairs_compared"] == len(RECOVERY_TARGETS)
    assert "so this is partial" not in recovery_delta.verdict(report)


def test_no_refined_results_is_not_computed(tmp_path):
    campaign = tmp_path / "campaign_empty"
    campaign.mkdir()
    (campaign / "results.jsonl").write_text("")
    report = recovery_delta.compare(campaign)
    assert report["status"].startswith("not_computed")
    assert recovery_delta.verdict(report) == report["status"]


def test_a_refined_pose_with_no_tier_one_counterpart_is_skipped(tmp_path, stub):
    pair = sorted(RECOVERY_TARGETS)[0]
    stub[pair] = (10.0, 3.0)
    campaign = _campaign(tmp_path, stub)
    # A refined job whose tier-1 row is absent: comparing it against nothing
    # would make the move the whole RMSD.
    with (campaign / "results_tier2.jsonl").open("a") as handle:
        handle.write(json.dumps({
            "job_id": "orphan__ternary__conditioned__seed1__tier2",
            "pair_id": pair, "complex_type": "ternary", "status": "done"}) + "\n")
    report = recovery_delta.compare(campaign)
    assert report["poses_compared"] == 1


def test_the_thresholds_come_from_the_config_not_the_source():
    # The project rule: no cutoff hard-coded in Python. Both numbers this
    # tool keys on must be the configured ones.
    source = (ROOT / "tools" / "recovery_delta.py").read_text()
    assert str(MARGIN) not in source, (
        f"the margin {MARGIN} is written into the source as a literal")
    assert recovery_delta.MOVED_A == MARGIN
    assert list(recovery_delta.BREAKPOINTS) == BREAKPOINTS


def test_the_anchor_is_carried_so_the_two_numbers_are_comparable(tmp_path, monkeypatch):
    # A refinement that moved the frame rather than the peptide would make
    # tier1 and tier2 incomparable, and the flag is what says so.
    pair = sorted(RECOVERY_TARGETS)[0]
    monkeypatch.setattr(recovery_delta.layers, "recovery_target",
                        lambda pair_id: {"pdb_id": "0XXX", "substrate_chain": "B",
                                         "substrate_acc": "P0", "receptor_chain": "A",
                                         "receptor_acc": "P1"})
    monkeypatch.setattr(
        recovery_delta, "_recovery",
        lambda job: _Result(5.0, anchor=9.0 if job["job_id"].endswith("__tier2") else 1.0))
    report = recovery_delta.compare(_campaign(tmp_path, {pair: (5.0, 5.0)}))
    assert report["pairs"][pair]["anchor_shifted"] is True


def test_a_pair_whose_tiers_folded_different_inputs_is_not_compared():
    """A move across a changed input measures the change, not the refinement.

    bench02_BRD4_VHL's tier-1 poses hold a hydroxyproline its YAML no longer
    asks for, and its tier-2 jobs get a fresh output directory and so
    featurise the YAML as it stands. The subtraction spans two different
    molecules, and it reported +3.37 A: readable as refinement making the
    pair worse (F219).

    Read off the live report rather than a hand-built one, because the thing
    worth testing is that `compare` wires the detection to the exclusion.
    """
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import recovery_delta as delta

    campaigns = sorted((ROOT / "campaigns").glob("campaign_*/queue.jsonl"))
    if not campaigns:
        pytest.skip("no main campaign on this checkout")
    report = delta.compare(campaigns[-1].parent)
    if report.get("status") != "computed":
        pytest.skip(f"nothing to compare yet: {report.get('status')}")
    if not report.get("confounded"):
        pytest.skip("no pair's tier-1 input has been superseded, so there is "
                    "no confound to exclude")

    for pair_id in report["confounded"]:
        assert pair_id in report["pairs"], pair_id
        assert report["pairs"][pair_id]["comparable"] is False
        # And out of every figure, not merely flagged in its own row.
        assert all(row["pair_id"] != pair_id for row in report["detail"]), (
            f"{pair_id} is excluded in the table and still in the detail"
        )

    comparable = [pair for pair, body in report["pairs"].items()
                  if body["comparable"]]
    assert report["pairs_compared"] == len(comparable), (
        "pairs_compared counts a pair the figures do not rest on"
    )


def test_the_confound_is_detected_from_the_cache_not_assumed():
    """The exclusion comes from reading what was folded, so it disappears by
    itself once the correction takes."""
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import recovery_delta as delta

    assert delta._pair_of("bench02_BRD4_VHL__ternary__conditioned__seed1") \
        == "bench02_BRD4_VHL"
    campaigns = sorted((ROOT / "campaigns").glob("campaign_*/queue.jsonl"))
    if not campaigns:
        pytest.skip("no main campaign on this checkout")
    confounded = delta._confounded_pairs(campaigns[-1].parent)
    # Whatever it finds, it must be pair ids rather than job ids.
    assert all("__" not in pair for pair in confounded), confounded
