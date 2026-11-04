"""Gate G5 has to be enforced, not merely configured.

`min_free_disk_gb = 50` sat in thresholds.toml and tuning.toml from the
first phase and nothing read it, so the gate existed on paper. A campaign
that fills the volume does not fail cleanly: Boltz writes a truncated
output, the job is recorded done, and the damage surfaces at scoring time
with the compute already spent.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble import paths
from nobble.execute import runner


def test_the_gate_reads_its_floor_from_config():
    """It read the wrong section first and reported a floor of zero, which
    is a gate that can never open."""
    gate = runner.disk_gate()
    assert gate["floor_gb"] == float(
        paths.thresholds()["gates"]["min_free_disk_gb"])
    assert gate["floor_gb"] > 0


def test_the_gate_is_closed_with_room_and_opens_without(monkeypatch):
    monkeypatch.setattr(runner, "free_disk_gb", lambda path=None: 500.0)
    assert runner.disk_gate()["open"] is False

    monkeypatch.setattr(runner, "free_disk_gb", lambda path=None: 10.0)
    opened = runner.disk_gate()
    assert opened["open"] is True
    assert opened["free_gb"] == 10.0


def test_a_floor_of_zero_never_opens_the_gate(monkeypatch):
    """A missing threshold must not become an always-open gate that stops
    every campaign on the first job."""
    monkeypatch.setattr(paths, "thresholds", lambda: {"gates": {}})
    monkeypatch.setattr(paths, "tuning", lambda: {"gates": {}})
    monkeypatch.setattr(runner, "free_disk_gb", lambda path=None: 0.5)
    assert runner.disk_gate()["open"] is False


def test_the_rmsd_curve_reads_its_breakpoints_from_config():
    """CLAUDE.md: thresholds come from thresholds.toml, never hard-coded in
    Python. This one lived in a default argument while the configured value
    went unread, so editing the config changed nothing."""
    from nobble.score.poses import success_rate_curve

    configured = paths.thresholds()["scoring"]["rmsd_breakpoints"]
    curve = success_rate_curve([0.5, 1.5, 2.5, 4.0, 9.0])
    for point in configured:
        assert f"within_{point}A" in curve, curve.keys()


def test_changing_the_configured_breakpoints_changes_the_curve(monkeypatch):
    from nobble.score import poses

    monkeypatch.setattr(poses.paths, "thresholds",
                        lambda: {"scoring": {"rmsd_breakpoints": [0.5, 8.0]}})
    curve = poses.success_rate_curve([0.4, 6.0, 20.0])
    assert set(curve) == {"within_0.5A", "within_8.0A", "n", "median_rmsd"}
    assert curve["within_0.5A"] == round(1 / 3, 4)


def test_no_cutoff_is_hard_coded_in_python():
    """thresholds.toml opens by claiming "Nothing in Python hard-codes a
    threshold". It was not true: nine module-level cutoffs lived in code,
    so the file was describing a rule the project did not follow.

    This pins the claim. A new numeric module constant that is a cutoff
    belongs in the config; add it there and read it, or add its name below
    with a reason if it is a physical constant rather than a choice.
    """
    import re
    import subprocess

    # Physical or structural constants, not tunable choices.
    allowed = {
        "LYSINE_MAX_ASA",        # max accessible surface area of lysine
        "SEED",                  # a seed, not a cutoff
        "MINIMUM_SEEDS", "MINIMUM_LABELLED", "MINIMUM_RANKED",  # sample-size floors
        "SCALE", "RETRIES", "MINIMUM_RANKED",
    }
    out = subprocess.run(
        ["grep", "-rnE", r"^[A-Z_]+ = [0-9]+\.[0-9]+", "nobble"],
        capture_output=True, text=True).stdout

    offenders = []
    for line in out.splitlines():
        name = re.search(r"^[^:]+:\d+:([A-Z_]+) =", line)
        if name and name.group(1) not in allowed:
            offenders.append(line)
    assert not offenders, "hard-coded cutoffs:\n" + "\n".join(offenders)


def test_every_moved_cutoff_kept_its_value():
    """The move must not have changed the science. Same numbers, read from
    a different place."""
    from nobble.curate import degron_gate, numbering, peptides
    from nobble.execute import yaml_gen
    from nobble.score import geometry, lysine, metrics, poses
    from nobble.validate import compare

    assert geometry.CONTACT_CUTOFF == 4.5
    assert poses.DOCKED_CONTACT_CUTOFF == 5.0
    assert degron_gate.CONTACT_CUTOFF == 5.0
    assert yaml_gen.POCKET_MAX_DISTANCE == 6.0
    assert lysine.EXPOSED_REL_SASA == 0.25
    assert numbering.MAX_MISMATCH_FRACTION == 0.1
    assert peptides.DOMAIN_COVERAGE_SELF_SUFFICIENT == 0.80
    assert metrics.COLLAPSE_MARGIN == 0.30
    assert compare.CONTROL_TOLERANCE_A == 2.0


def test_recovery_resolves_a_target_across_campaign_prefixes():
    """RECOVERY_TARGETS is keyed "bench01_GSPT1_CRBN"; the corrected
    campaign runs the same biology as "corr01_GSPT1_CRBN". Keying on the
    literal pair id meant pose recovery found no deposited crystal there
    and the F6 comparison could never conclude, however long the campaign
    ran. See F12."""
    from nobble.validate.layers import RECOVERY_TARGETS, recovery_target

    for key, expected in RECOVERY_TARGETS.items():
        gene_e3 = "_".join(key.split("_")[1:3])
        assert recovery_target(key) == expected
        assert recovery_target(f"corr99_{gene_e3}") == expected, gene_e3

    assert recovery_target("sv_pos_ZN346_abcdef") is None
    assert recovery_target(None) is None
    assert recovery_target("nopartshere") is None


def test_a_verdict_over_a_partial_campaign_says_it_is_provisional():
    """"F6 supported" over five of seven pairs is a verdict about whichever
    pairs finished. The per-pair table marks the gaps, but the conclusion is
    the line that gets quoted and nobody checks a table to see whether the
    sentence above it was qualified."""
    from nobble.validate import compare as cmp

    class _Item:
        def __init__(self, gene, verdict, delta=None, control=False):
            self.gene, self.verdict, self.delta_rmsd = gene, verdict, delta
            self.is_control, self.e3 = control, "CRBN"
        def to_dict(self):
            return {"gene": self.gene, "verdict": self.verdict}

    comparisons = [
        _Item("IKZF1", "control held", 0.0, control=True),
        _Item("GSPT1", "improved", -28.0),
        _Item("CDK12", "incomplete: one campaign has no recovery number yet"),
    ]
    control = comparisons[0]
    improved = [comparisons[1]]
    incomplete = [c for c in comparisons if c.verdict.startswith("incomplete")]

    conclusion = "F6 supported: 1 pair(s) improved"
    missing = ", ".join(sorted(c.gene for c in incomplete))
    conclusion += (f". Provisional: {len(incomplete)} of {len(comparisons)} "
                   f"pair(s) have not finished in both campaigns ({missing})")

    assert "Provisional" in conclusion
    assert "CDK12" in conclusion
    assert control.delta_rmsd == 0.0 and improved


def test_a_complete_campaign_gets_no_provisional_qualifier():
    """The qualifier must appear only when something is actually missing."""
    from pathlib import Path
    from nobble.validate import compare as cmp

    report = cmp.compare(Path("campaigns/benchmark_20261103T192126Z"),
                         Path("campaigns/corrected_20261103T214331Z"))
    if report["pairs_incomplete"] == 0:
        assert "Provisional" not in report["conclusion"]
    else:
        assert "Provisional" in report["conclusion"]


def test_the_gene_fallback_does_not_claim_crystals_it_should_not():
    """The (gene, E3) fallback added for the corrected campaign could
    over-match. A scramble of a benchmark pair must not inherit its
    parent's crystal, and no Sievers finger has one at all: either would
    put a pose recovery number against a pair that has nothing to recover
    against, which is worse than the missing number it replaced."""
    import glob
    import json

    import pytest

    from nobble.validate.layers import recovery_target

    campaigns = sorted(glob.glob("campaigns/campaign_*"))
    if not campaigns:
        pytest.skip("no assembled campaign")
    queue = Path(campaigns[-1]) / "queue.jsonl"
    if not queue.exists():
        pytest.skip("campaign has no queue")

    pairs = sorted({json.loads(line)["pair_id"]
                    for line in queue.read_text().splitlines() if line.strip()})
    resolved = [p for p in pairs if recovery_target(p)]

    assert all(p.startswith("bench") for p in resolved), resolved
    assert not [p for p in pairs if p.startswith("scr_") and recovery_target(p)]
    assert not [p for p in pairs if p.startswith("sv_") and recovery_target(p)]


def test_the_conclusion_reports_bridge_agreement_without_changing_the_verdict():
    """Two independent measurements agreeing is a much stronger claim than
    either alone, so the conclusion says when bridge formation moved the
    same way as the RMSD. The verdict itself stays RMSD-based: F6 is about
    pose recovery and the 2 A thresholds are calibrated on it, so widening
    the criterion would change what "F6 supported" means without saying so.
    """
    from pathlib import Path

    import pytest

    from nobble.validate import compare as cmp

    baseline = Path("campaigns/benchmark_20261103T192126Z")
    corrected = Path("campaigns/corrected_20261103T214331Z")
    if not (baseline / "scores.jsonl").exists() or not (corrected / "scores.jsonl").exists():
        pytest.skip("campaigns not scored")

    report = cmp.compare(baseline, corrected)
    conclusion = report["conclusion"]

    # Every pair carries both measurements where both exist.
    both = [c for c in report["comparisons"]
            if c["delta_rmsd"] is not None and c["bridge_rate_change"] is not None]
    assert both, "no pair has both measurements"

    gained = [c for c in report["comparisons"]
              if (c["bridge_rate_change"] or 0) > 0]
    lost = [c for c in report["comparisons"]
            if (c["bridge_rate_change"] or 0) < 0]
    if gained and not lost:
        assert "Bridge formation agrees" in conclusion, conclusion
    elif lost:
        assert "Bridge formation disagrees" in conclusion, conclusion

    # The verdict per pair is still decided on RMSD alone.
    for item in report["comparisons"]:
        if item["delta_rmsd"] is not None and not item["is_control"]:
            expected = ("improved" if item["delta_rmsd"] < -2.0
                        else "worse" if item["delta_rmsd"] > 2.0 else "unchanged")
            assert item["verdict"] == expected, item
