"""Running the corrections twice must not spend an hour arriving nowhere.

`tools/corrections.sh` sequences the two GPU corrections the main campaign
needs and then the refresh they feed. Both underlying operations clear results
so the jobs re-run, so the script has to know when there is nothing left to
correct, and it reads that off the rehearsal rather than off an exit code.

The exit code cannot carry it. `rerun_pair.py --regenerate` exits 2 and says
"byte-identical" when the YAMLs already match the code. The reference path
exits 0 whether or not there is anything to do: for bench02 today it reports
"0 of 15 YAML(s) differ" and "15 of those hold a featurisation that
disagrees", and once the correction has worked it will report the same first
line with "none of those disagrees with its YAML today". Those two differ only
in the second line.

The first draft of the script put the check inside the non-zero branch, where
the reference path never reaches it, so a second run after a successful
correction would have cleared fifteen results and re-run fifteen jobs on an
input that was already right (F267).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "corrections.sh"

NOTHING_TO_DO_REFERENCE = """bench02_BRD4_VHL: 15 job(s) in the queue
  0 of 15 YAML(s) differ from their known-good reference and would be rewritten; 15 already match
  30 row(s) would be dropped from state.jsonl
  15 cached output directory/ies would be removed, so the re-run featurises the corrected YAML instead of reusing the old one
  none of those disagrees with its YAML today, so there is no stale featurisation left to clear
  rerun with --apply to do it
"""

WORK_TO_DO_REFERENCE = """bench02_BRD4_VHL: 15 job(s) in the queue
  0 of 15 YAML(s) differ from their known-good reference and would be rewritten; 15 already match
  30 row(s) would be dropped from state.jsonl
  15 of those hold a featurisation that disagrees with the YAML today, which is what this removes
  rerun with --apply to do it
"""

NOTHING_TO_DO_REGENERATE = """
REFUSING: the current code regenerates all 15 YAML(s) byte-identical to what is on disk, so there is nothing to correct and clearing the results would re-run the same input (F146).
scr_bench04_IKZF1_CRBN: 15 job(s) in the queue
"""

WORK_TO_DO_REGENERATE = """scr_bench03_BRD4_CRBN: 10 job(s) in the queue
  5 of 10 YAML(s) differ from what the current code emits and would be rewritten
  rerun with --apply --regenerate to do it
"""


def _decides_nothing_to_do(text: str) -> bool:
    """The script's two conditions, applied the way the script applies them.

    `grep -q` on the whole text, and `grep -qE` with a line anchor for the
    count, so this has to use MULTILINE to match that behaviour rather than
    a looser search that would pass either way.
    """
    if "byte-identical" in text:
        return True
    return bool(
        "no stale featurisation left to clear" in text
        and re.search(r"^\s*0 of [0-9]+ YAML\(s\) differ", text, re.M))


@pytest.mark.parametrize("text,expected", [
    (NOTHING_TO_DO_REFERENCE, True),
    (WORK_TO_DO_REFERENCE, False),
    (NOTHING_TO_DO_REGENERATE, True),
    (WORK_TO_DO_REGENERATE, False),
], ids=["reference-done", "reference-todo", "regenerate-done",
        "regenerate-todo"])
def test_the_decision_matches_the_rehearsal(text, expected):
    assert _decides_nothing_to_do(text) is expected


def test_the_script_uses_both_conditions():
    """The patterns in the test have to be the patterns in the script.

    A test of a copy of the logic proves nothing about the script, so this
    pins the two greps by their text.
    """
    source = SCRIPT.read_text()
    assert 'grep -q "byte-identical"' in source, source[:0] or "pattern moved"
    assert "no stale featurisation left to clear" in source
    assert r"^\s*0 of [0-9]+ YAML\(s\) differ" in source


def test_the_check_is_not_inside_the_failure_branch():
    """Where the first draft put it, and the reference path never gets there.

    Structural, because the defect is a placement rather than a value: both
    greps have to appear before the `status -ne 0` test.
    """
    source = SCRIPT.read_text()
    first_grep = source.index('grep -q "byte-identical"')
    stale_grep = source.index("no stale featurisation left to clear")
    failure_branch = source.index('if [[ "$status" -ne 0 ]]; then')
    assert first_grep < failure_branch, (
        "the byte-identical check sits inside the failure branch again")
    assert stale_grep < failure_branch, (
        "the stale-featurisation check sits inside the failure branch again")


def test_the_dry_run_writes_nothing_and_says_so():
    """Default is a rehearsal, and it has to name both pairs.

    Run for real, because a script that only looks right is the thing this
    file is about. It touches no GPU: without --apply it never sources the
    wait or calls run_queue.
    """
    if not (ROOT / "campaigns").exists():
        pytest.skip("no campaigns on disk")
    import os

    out = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True,
                         cwd=ROOT, timeout=600,
                         env={**os.environ, "PYTHONPATH": str(ROOT),
                              "KMP_DUPLICATE_LIB_OK": "TRUE"})
    if "no complete campaign" in out.stderr:
        pytest.skip("no complete campaign assembled")
    assert out.returncode == 0, out.stderr[-800:]
    assert "DRY RUN" in out.stdout, out.stdout[:400]
    assert "bench02_BRD4_VHL" in out.stdout
    assert "scr_bench03_BRD4_CRBN" in out.stdout
    assert "would run tools/refresh.sh" in out.stdout


def test_the_waits_come_before_anything_is_cleared():
    """Order, because clearing first is the destructive mistake.

    Twenty results cleared while the chain is still scoring hands its scorer
    a campaign with twenty holes in it. run_queue.sh waits for the GPU
    itself, but by then the clearing has happened.
    """
    source = SCRIPT.read_text()
    wait = source.index("nobble_wait_for_gpu")
    first_apply = source.index('run_one bench02_BRD4_VHL')
    assert wait < first_apply, (
        "the GPU wait comes after the first correction, so results would be "
        "cleared while another run holds the device")
