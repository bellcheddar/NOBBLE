"""The YAML Boltz reads and the queue row describing it must agree.

A campaign holds two descriptions of every job. The queue row says what
the job is, and everything downstream reads it; the YAML is what Boltz is
actually given. They are written by one assembly and normally agree.

They stopped agreeing once. F47 fixed a modification rule that keyed on the
E3 rather than the degron class and had put a hydroxyproline on BRD4
Pro379. The queue was reassembled and correctly records that
`bench02_BRD4_VHL` needs no modification; the fifteen YAMLs were already on
disk and were not regenerated, so they still carry `ccd: HYP`.

Nothing compared the two, and a disagreement between them is invisible from
either side: the results look like results for the job the queue describes.
Fifteen jobs ran and would have been published as BRD4 against VHL (F59).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.validate import inputs  # noqa: E402

MAIN = ROOT / "campaigns" / "campaign_20261104T004632Z"


def _campaign(tmp_path, jobs):
    """jobs: (job_id, pair_id, required_modification, yaml_text)."""
    campaign = tmp_path / "campaign_20261104T000000Z"
    (campaign / "yaml").mkdir(parents=True)
    rows = []
    for job_id, pair_id, required, text in jobs:
        path = campaign / "yaml" / f"{job_id}.yaml"
        if text is not None:
            path.write_text(text)
        rows.append({"job_id": job_id, "pair_id": pair_id,
                     "required_modification": required, "yaml": str(path)})
    (campaign / "queue.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    return campaign


CLEAN = """sequences:
- protein:
    id: A
    sequence: MKV
- protein:
    id: B
    sequence: PFQ
"""

MODIFIED = """sequences:
- protein:
    id: A
    sequence: MKV
- protein:
    id: B
    sequence: PFQ
    modifications:
    - position: 1
      ccd: HYP
"""


def test_a_yaml_with_a_modification_the_queue_does_not_want_is_stale(tmp_path):
    """The real case, in miniature."""
    campaign = _campaign(tmp_path, [("j1", "p1", None, MODIFIED)])
    (stale,) = inputs.stale_inputs(campaign)
    assert stale["pair_id"] == "p1"
    assert stale["yaml"] == [(1, "HYP")]
    assert stale["queue"] == []
    assert "disagree" in stale["reason"]


def test_a_yaml_missing_a_modification_the_queue_wants_is_stale(tmp_path):
    """The other direction, which is the one a reassembly would cause."""
    campaign = _campaign(
        tmp_path, [("j1", "p1", {"position": 1, "ccd": "HYP"}, CLEAN)])
    (stale,) = inputs.stale_inputs(campaign)
    assert stale["yaml"] == []
    assert stale["queue"] == [(1, "HYP")]


def test_agreement_in_both_shapes_is_not_stale(tmp_path):
    campaign = _campaign(tmp_path, [
        ("j1", "p1", None, CLEAN),
        ("j2", "p2", {"position": 1, "ccd": "HYP"}, MODIFIED),
        ("j3", "p3", [{"position": 1, "ccd": "HYP"}], MODIFIED),
    ])
    assert inputs.stale_inputs(campaign) == []


def test_a_different_ccd_is_stale(tmp_path):
    """Not merely present or absent: the wrong modification is as wrong as
    a missing one, and this is what a rule keyed on the wrong attribute
    produces once more than one modification class exists."""
    campaign = _campaign(
        tmp_path, [("j1", "p1", {"position": 1, "ccd": "SEP"}, MODIFIED)])
    (stale,) = inputs.stale_inputs(campaign)
    assert stale["yaml"] == [(1, "HYP")]
    assert stale["queue"] == [(1, "SEP")]


def test_a_different_position_is_stale(tmp_path):
    campaign = _campaign(
        tmp_path, [("j1", "p1", {"position": 7, "ccd": "HYP"}, MODIFIED)])
    assert len(inputs.stale_inputs(campaign)) == 1


def test_a_missing_yaml_is_reported_not_skipped(tmp_path):
    """Absent is not agreement. A queue row naming a YAML that is not there
    describes a job that cannot run as described."""
    campaign = _campaign(tmp_path, [("j1", "p1", None, None)])
    (stale,) = inputs.stale_inputs(campaign)
    assert stale["yaml"] is None
    assert "not on disk" in stale["reason"]


def test_a_campaign_with_no_queue_is_not_an_error(tmp_path):
    campaign = tmp_path / "campaign_20261104T000000Z"
    campaign.mkdir()
    assert inputs.stale_inputs(campaign) == []


def test_the_refusal_names_the_pair_and_the_command():
    stale = [{"job_id": "j1", "pair_id": "bench02_BRD4_VHL",
              "reason": "x", "queue": [], "yaml": [(1, "HYP")]}]
    message = inputs.refusal(stale)
    assert "REFUSING TO PUBLISH" in message
    assert "bench02_BRD4_VHL" in message
    assert "tools/rerun_pair.py" in message


def test_the_live_campaign_holds_exactly_the_f47_pair():
    """The scope, measured rather than assumed. If this ever reports a
    different count the correction is incomplete or something new has
    drifted, and either way the atlas build is already refusing."""
    if not MAIN.exists():
        pytest.skip("no main campaign on this checkout")
    stale = inputs.stale_inputs(MAIN)
    if not stale:
        pytest.skip("the F47 correction has been applied")
    assert {row["pair_id"] for row in stale} == {"bench02_BRD4_VHL"}
    assert len(stale) == 15
    assert all(row["yaml"] == [(1, "HYP")] for row in stale)


def test_the_atlas_build_refuses_rather_than_publishing(tmp_path):
    """The wiring, not the helper (F40). A stale campaign must stop the
    publish, and must stop it before the previous atlas is removed."""
    if not MAIN.exists():
        pytest.skip("no main campaign on this checkout")
    if not inputs.stale_inputs(MAIN):
        pytest.skip("the F47 correction has been applied")

    atlas = ROOT / "deploy" / "atlas"
    before = sorted(p.name for p in atlas.iterdir()) if atlas.exists() else None

    completed = subprocess.run(
        [str(ROOT.parent / "BINMAN" / ".pixi" / "envs" / "default" / "bin"
             / "python"), "deploy/build_atlas.py", str(MAIN)],
        cwd=ROOT, capture_output=True, text=True, timeout=600,
        env={"PYTHONPATH": str(ROOT), "KMP_DUPLICATE_LIB_OK": "TRUE",
             "PATH": "/usr/bin:/bin",
             # Never the real atlas. With the refusal in place this script
             # writes nothing, but this test exists to be run against a
             # build whose refusal has been removed.
             "NOBBLE_ATLAS_OUT": str(tmp_path / "atlas")},
    )
    assert completed.returncode == 1, completed.stdout[-2000:]
    assert "REFUSING TO PUBLISH" in completed.stderr
    assert "bench02_BRD4_VHL" in completed.stderr

    after = sorted(p.name for p in atlas.iterdir()) if atlas.exists() else None
    assert after == before, "the published atlas was disturbed by a refusal"
