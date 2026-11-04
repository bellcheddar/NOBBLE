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
