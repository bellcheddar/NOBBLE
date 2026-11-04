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
