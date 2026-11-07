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


def _with_footprint(tmp_path: Path, footprint: dict) -> Path:
    campaign = tmp_path / "campaign_footprint"
    campaign.mkdir()
    (campaign / "validation.json").write_text(json.dumps({
        "layers": {"pose_recovery": {
            "computed": True,
            "summary": {
                "overall_curve": {"n": 2, "median_rmsd": 9.0},
                "by_pair": {"pair_a": {"median_rmsd": 5.0},
                            "pair_b": {"median_rmsd": 13.0}},
                "footprint": footprint,
            },
        }},
    }))
    return campaign


MEASURED = {"status": "measured", "jaccard": 0.9,
            "window_residues_touched": 15, "window_residues": 15}


def test_the_refusal_says_where_the_poses_are_not_only_how_far(tmp_path):
    """An RMSD cannot distinguish a missed site from a wrong register (F227).

    Whoever reads this output is deciding whether to release the hold, so the
    split belongs in front of them rather than in a tool they would have to
    know to run.
    """
    campaign = _with_footprint(tmp_path, {"pair_a": MEASURED})
    out = _run(_held(tmp_path), campaign=campaign).stderr
    assert "contact jaccard 0.9" in out, out
    assert "15 of 15 window residue(s) touched" in out, out


def test_a_confounded_pair_is_not_counted_as_measurable(tmp_path):
    """The validation layer cannot know this; this file can, so it must.

    Without it the footprint presents a pair whose poses came from an input
    no longer on disk as a measurement of the current input, which is F222's
    mistake one file over.
    """
    campaign = _with_footprint(tmp_path, {"pair_a": MEASURED,
                                          "pair_b": dict(MEASURED)})
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "publication_hold", ROOT / "tools" / "publication_hold.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    summary = json.loads((campaign / "validation.json").read_text())[
        "layers"]["pose_recovery"]["summary"]

    clean = "\n".join(module.describe(summary, confounded=set()))
    assert "2 of 2 measurable" in clean, clean

    flagged = "\n".join(module.describe(summary, confounded={"pair_b"}))
    assert "1 of 2 measurable" in flagged, flagged
    assert "pair_b" in flagged and "confounded" in flagged, flagged


def test_an_unknown_confounded_check_is_not_read_as_none_confounded(tmp_path):
    """Unknown is not clean, which is F216 in a third file."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "publication_hold", ROOT / "tools" / "publication_hold.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    campaign = _with_footprint(tmp_path, {"pair_a": MEASURED})
    summary = json.loads((campaign / "validation.json").read_text())[
        "layers"]["pose_recovery"]["summary"]

    unknown = "\n".join(module.describe(summary, confounded=None))
    assert "could not be checked" in unknown, unknown


def test_a_campaign_with_no_footprint_says_so(tmp_path):
    campaign = _with_footprint(tmp_path, {})
    assert "footprint: not computed" in _run(
        _held(tmp_path), campaign=campaign).stderr


def test_the_refusal_contrasts_the_two_representations():
    """The hold's reason is that pose recovery failed. Both halves matter.

    It failed on the campaign the atlas is built from, whose substrates are
    15-mer peptides, and the same pipeline recovers six of seven pairs given
    the whole folded domain (F236). Whoever reads this output is deciding
    whether to release the hold, and that is the difference between "cannot
    place a degron" and "places a degron given its domain".
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "publication_hold", ROOT / "tools" / "publication_hold.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    import os

    cwd = os.getcwd()
    try:
        os.chdir(ROOT)
        lines = module.representation_contrast()
    finally:
        os.chdir(cwd)

    text = "\n".join(lines)
    if "no corrected-construct campaign" in text:
        pytest.skip("no corrected campaign on disk")
    assert "with the whole domain instead of a 15-mer" in text, text
    assert "control held" in text, text
    # And the control is named, or a row that correctly does not move reads
    # as a row that failed to improve.
    assert "control: a linear epitope" in text, text


def test_a_missing_corrected_campaign_says_so_rather_than_nothing(tmp_path):
    import importlib.util
    import os

    spec = importlib.util.spec_from_file_location(
        "publication_hold", ROOT / "tools" / "publication_hold.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        lines = module.representation_contrast()
    finally:
        os.chdir(cwd)
    assert any("no corrected-construct campaign" in line for line in lines), lines


def test_the_contrast_quotes_the_same_curve_the_hold_refuses_on():
    """The reason is "no pose reaches 3 A", which is an overall_curve.

    So the answer has to be the other campaign's overall_curve, not a list of
    per-pair medians: 0 of 65 within 3 A at a median of 17.54 A, against 53.8
    per cent within 3 A at 2.494 A. One measurement, two representations.
    """
    import importlib.util
    import os

    spec = importlib.util.spec_from_file_location(
        "publication_hold", ROOT / "tools" / "publication_hold.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cwd = os.getcwd()
    try:
        os.chdir(ROOT)
        text = "\n".join(module.representation_contrast())
    finally:
        os.chdir(cwd)

    if "no corrected-construct campaign" in text:
        pytest.skip("no corrected campaign on disk")
    assert "the same curve on the whole-domain campaign" in text, text
    assert "median" in text, text
    assert "within 3.0 A" in text, (
        "the contrast omits the radius the hold's own reason names")
