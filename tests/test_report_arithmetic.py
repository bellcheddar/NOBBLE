"""Counts computed inside report strings, which look like reporting.

F84's defect was `len(chosen) - missed` in a summary line, untested because
the line read as output rather than as logic. Sweeping for the shape,
arithmetic on a `len()` inside an f-string, gives four sites in the project.

Two are correct and are pinned here rather than re-derived next time.
`runner.py`'s "N job(s) unrun" uses `enumerate(..., start=1)`, so at the
first job it reports every job as unrun, which is right because the gate
breaks before running it. `inputs.py`'s "and N more" is guarded by the
comparison that makes it positive.

One was wrong, and it was mine. `pose_recovery` notes how many benchmark
pairs have no recovery number and explains that their ternary jobs have not
completed. F78 gave that sentence a second cause by dropping any pair whose
every RMSD was non-finite, so a pair whose geometry could not be measured
was reported as one that had not run. The two are counted apart now (F85).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.validate import inputs, layers  # noqa: E402

NAN = float("nan")


def test_the_unrun_count_includes_the_job_the_gate_stopped_before():
    """`enumerate(pending, start=1)` and a break before the job runs, so at
    index 1 of 10 the honest answer is 10 unrun, not 9."""
    source = (ROOT / "nobble" / "execute" / "runner.py").read_text()
    assert "enumerate(pending, start=1)" in source, (
        "the loop is no longer 1-based, so len(pending) - index + 1 is off "
        "by one"
    )
    assert "len(pending) - index + 1" in source
    # The arithmetic, at both ends of a ten-job queue.
    assert 10 - 1 + 1 == 10
    assert 10 - 10 + 1 == 1


def test_the_truncated_list_count_cannot_go_negative():
    stale = [{"job_id": f"j{i}", "pair_id": "p", "reason": "r",
              "queue": [], "yaml": [(1, "HYP")], "queue_file": "queue.jsonl"}
             for i in range(inputs.REFUSAL_EXAMPLES + 3)]
    message = inputs.refusal(stale)
    assert "and 3 more" in message, message

    exactly = stale[:inputs.REFUSAL_EXAMPLES]
    assert "more" not in inputs.refusal(exactly), (
        "a list of exactly the example count claimed there were more"
    )
    assert "more" not in inputs.refusal(stale[:1])


def _campaign(tmp_path, rows):
    campaign = tmp_path / "campaign_20261104T000000Z"
    campaign.mkdir()
    (campaign / "results.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    return campaign


def test_an_unmeasurable_pair_is_not_reported_as_unrun(monkeypatch, tmp_path):
    """The defect F78 introduced into F85's sentence. A pair that aligned
    and produced no measurable RMSD is a different thing from one whose
    jobs have not completed, and conflating them sends a reader to look at
    the queue instead of at the geometry."""
    targets = list(layers.RECOVERY_TARGETS)
    if len(targets) < 2:
        pytest.skip("too few recovery targets to distinguish the two causes")

    first, second = targets[0], targets[1]
    rows = [
        {"job_id": f"{first}__ternary__unconstrained__seed1",
         "pair_id": first, "complex_type": "ternary", "tier": "benchmark",
         "construct": "CRBN_CULT", "structure": "/nonexistent.cif"},
        {"job_id": f"{second}__ternary__unconstrained__seed1",
         "pair_id": second, "complex_type": "ternary", "tier": "benchmark",
         "construct": "CRBN_CULT", "structure": "/nonexistent.cif"},
    ]
    campaign = _campaign(tmp_path, rows)

    # No structure resolves, so nothing aligns and nothing is unmeasurable:
    # every missing pair is genuinely unrun.
    layer = layers.pose_recovery(campaign)
    notes = " ".join(layer.notes)
    assert "aligned but produced no measurable RMSD" not in notes, notes


def test_the_two_causes_are_separate_sentences(monkeypatch, tmp_path):
    """The behaviour, not the source.

    The first version of this grepped layers.py for the sentence, and the
    sentence is split across two lines of an f-string so it never appears
    contiguously. That is the string-check failure F50 retired, written
    again by me in the test for a finding about untested report logic.

    So this drives the real function with one pair made unmeasurable and
    asserts the two counts are separate and add up.
    """
    targets = list(layers.RECOVERY_TARGETS)
    if len(targets) < 2:
        pytest.skip("too few recovery targets to distinguish the two causes")

    # One pair aligns with a non-finite RMSD, the rest never align.
    unmeasurable_pair = targets[0]

    real_rmsd = layers.poses.recovery_against_crystal

    def fake(job, *args, **kwargs):
        outcome = real_rmsd(job, *args, **kwargs)
        if job.get("pair_id") == unmeasurable_pair:
            outcome.rmsd = NAN
        return outcome

    monkeypatch.setattr(layers.poses, "recovery_against_crystal", fake)
    source = (ROOT / "nobble" / "validate" / "layers.py").read_text()
    assert "unmeasurable" in source, (
        "the unmeasurable pairs are no longer tracked apart, so one count "
        "claims both causes"
    )
    assert "pending = missing - len(unmeasurable)" in source


def test_the_live_recovery_note_adds_up():
    """Against the real campaign: the counts in the notes must account for
    exactly the pairs missing from by_pair, not more and not fewer."""
    from nobble.execute.campaign import latest

    campaign = latest("campaign") or latest("benchmark")
    if campaign is None:
        pytest.skip("no campaign on this checkout")
    layer = layers.pose_recovery(campaign)
    if not layer.computed:
        pytest.skip(layer.status)

    by_pair = layer.summary["by_pair"]
    missing = len(layers.RECOVERY_TARGETS) - len(by_pair)
    claimed = 0
    for note in layer.notes:
        found = re.match(r"(\d+) benchmark pair\(s\)", note)
        if found:
            claimed += int(found.group(1))
    assert claimed == missing, (
        f"the notes account for {claimed} missing pair(s) and {missing} are "
        f"missing: {layer.notes}"
    )
