"""The atlas may not leave the Mac while publication is held (D-NOB-076).

The hold exists because the chain's last stage is a deploy. A decision
recorded only in DECISIONS.md would have been overruled by a script several
hours later, which is the failure mode this file is about: not whether the
refusal prints nicely, but whether the two scripts that can publish both
consult it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "publication_hold.py"
CONFIG = ROOT / "config" / "publication_hold.toml"


def _run(config: Path, campaign: Path | None = None):
    command = [sys.executable, str(TOOL), "--config", str(config)]
    if campaign is not None:
        command += ["--campaign", str(campaign)]
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True)


def _held(tmp_path: Path, **fields) -> Path:
    config = tmp_path / "publication_hold.toml"
    defaults = {"held": "true", "decision": '"D-TEST-001"',
                "reason": '"a test reason"', "released_by": '""'}
    defaults.update({key: value for key, value in fields.items()})
    config.write_text("\n".join(f"{key} = {value}"
                                for key, value in defaults.items()) + "\n")
    return config


def test_a_held_atlas_is_refused(tmp_path):
    result = _run(_held(tmp_path))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "publication is held by D-TEST-001" in result.stderr


def test_the_refusal_carries_the_recorded_reason(tmp_path):
    """So the person who hits it does not have to go and find the decision."""
    config = _held(tmp_path, reason='"the control has not passed"')
    assert "the control has not passed" in _run(config).stderr


def test_a_release_needs_a_named_decision(tmp_path):
    """held = false on its own is indistinguishable from a slip of the hand."""
    config = _held(tmp_path, held="false", released_by='""')
    result = _run(config)
    assert result.returncode == 2, result.stdout
    assert "names no decision" in result.stderr


def test_a_named_release_publishes(tmp_path):
    config = _held(tmp_path, held="false", released_by='"D-TEST-002"')
    result = _run(config)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "released by D-TEST-002" in result.stdout


def test_a_missing_hold_file_is_read_as_held(tmp_path):
    """A gate that opens when its own configuration is deleted is not a gate."""
    result = _run(tmp_path / "absent.toml")
    assert result.returncode == 2
    assert "is missing" in result.stderr


def test_the_live_curve_is_printed_rather_than_the_recorded_one(tmp_path):
    """The numbers in the refusal come from the campaign, not from the config.

    A hold that quotes the day it was written goes stale without saying so,
    and the whole reason it is re-read on every attempt is that whoever
    releases it should see what is true now.
    """
    campaign = tmp_path / "campaign_synthetic"
    campaign.mkdir()
    (campaign / "validation.json").write_text(json.dumps({
        "layers": {"pose_recovery": {
            "computed": True,
            "summary": {
                "overall_curve": {"within_1.0A": 0.0, "within_5.0A": 0.5,
                                  "n": 4, "median_rmsd": 4.25},
                "by_pair": {"synthetic_pair": {"median_rmsd": 4.25}},
            },
        }},
    }))
    out = _run(_held(tmp_path), campaign=campaign).stderr
    assert "median 4.25 A" in out
    assert "synthetic_pair" in out


def test_a_campaign_without_the_layer_says_so_rather_than_inventing_one(tmp_path):
    campaign = tmp_path / "campaign_bare"
    campaign.mkdir()
    (campaign / "validation.json").write_text(json.dumps(
        {"layers": {"pose_recovery": {"computed": False, "status": "not_computed"}}}))
    assert "not computed" in _run(_held(tmp_path), campaign=campaign).stderr


def test_deploy_checks_the_hold_before_opening_a_connection():
    """Local refusal, so a held atlas costs no ssh and no rsync."""
    deploy = (ROOT / "deploy" / "deploy.sh").read_text()
    assert "tools/publication_hold.py" in deploy
    assert deploy.index("tools/publication_hold.py") < deploy.index("ssh ok"), (
        "the hold is checked after the droplet connection is opened"
    )


def test_the_chain_checks_the_hold_before_its_deploy_stage():
    """The reason this file exists: the chain's last stage is a deploy."""
    chain = (ROOT / "tools" / "run_chain.sh").read_text()
    assert "tools/publication_hold.py" in chain
    assert chain.index("tools/publication_hold.py") < chain.index("deploy/deploy.sh"), (
        "the chain reaches deploy.sh before it consults the hold"
    )


def test_the_live_hold_states_a_decision():
    """Whatever the hold currently says, it has to be attributable."""
    import tomllib
    with CONFIG.open("rb") as handle:
        hold = tomllib.load(handle)
    if hold.get("held"):
        assert hold.get("decision"), "the live hold names no decision"
        assert hold.get("reason"), "the live hold gives no reason"
    else:
        assert hold.get("released_by"), "the live release names no decision"


def test_no_success_radius_was_invented_to_decide_this():
    """The hold is a decision, not a threshold (D-NOB-076).

    If a `recovery_success_a` ever appears in thresholds.toml it will be
    because someone chose a radius inside which a pose counts as recovered,
    and that choice belongs in DECISIONS.md with its reasoning, not in a
    config file that a deploy script can read as permission to publish.
    """
    source = TOOL.read_text()
    assert "thresholds()" not in source, (
        "publication_hold.py reads a threshold: the hold decides publication, "
        "and no measured cutoff decides it"
    )
    thresholds = (ROOT / "config" / "thresholds.toml").read_text()
    assert "recovery_success_a" not in thresholds
