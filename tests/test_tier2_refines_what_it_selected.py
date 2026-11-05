"""Tier 2 refines this selection's queue, or nothing (F193).

`tools/tier2.sh` keyed on the selector's exit code and handled one value,
3, for Gate G1. The script's own comment gave the reason and the reason is
wider than the guard: "without that the refiner runs next with no queue to
read, which is harmless and reads in the log as though the refinement had
been done".

Exit 0 covers four outcomes. A selection that queued jobs. A refusal with
nothing rankable. An unpriceable refusal, which F161 made distinct from G1.
And "no tier-1 queue to refine", which turned up while testing this and
which I had not enumerated. Only the first writes `queue_tier2.jsonl`, so the
status cannot carry the decision.

It is worse than a no-op, because the queue file persisted across runs.
`campaigns/benchmark_20261103T192126Z/queue_tier2.jsonl` held ten jobs for
`bench02_BRD4_VHL` written on 3 November: a refusal would have had the
refiner spend GPU hours on that selection while the log read as a fresh
decile.

So two changes, and these tests hold both. `run()` clears any previous queue
before selecting, which makes "the queue exists" mean "this call wrote one"
for every caller rather than only for the shell. And the selector prints a
`TIER2_QUEUE=` line, which the shell reads instead of guessing from the exit
code.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.execute import tier2  # noqa: E402

SCRIPT = ROOT / "tools" / "tier2.sh"
SELECTOR = ROOT / "nobble" / "execute" / "tier2.py"


def _campaign(tmp_path: Path) -> Path:
    campaign = tmp_path / "campaigns" / "benchmark_fixture"
    campaign.mkdir(parents=True)
    (campaign / "campaign.json").write_text("{}")
    return campaign


def test_a_refusal_clears_a_queue_an_earlier_run_left(tmp_path):
    """The failure that was live: a days-old queue surviving a refusal."""
    campaign = _campaign(tmp_path)
    stale = campaign / "queue_tier2.jsonl"
    stale.write_text('{"job_id": "from_a_previous_selection"}\n')

    tier2.run(campaign)

    assert not stale.exists(), (
        "a previous selection's queue survived a refusal, so the refiner "
        "would spend GPU hours on it while the log read as a fresh decile"
    )


def test_the_queue_is_cleared_before_selecting_not_after(tmp_path):
    """Order matters: cleared after a success would delete the real queue."""
    source = SELECTOR.read_text()
    body = source[source.index("def run("):]
    clear = body.index("unlink(missing_ok=True)")
    select = body.index("select_top_decile(")
    assert clear < select, (
        "the queue is cleared after the selection runs, which would remove "
        "the queue the selection just wrote"
    )


def test_the_selector_prints_a_queue_line_either_way(tmp_path):
    campaign = _campaign(tmp_path)
    done = subprocess.run(
        [sys.executable, "-m", "nobble.execute.tier2", str(campaign)],
        cwd=ROOT, capture_output=True, text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT),
             "KMP_DUPLICATE_LIB_OK": "TRUE"},
    )
    lines = [line for line in done.stdout.splitlines()
             if line.startswith("TIER2_QUEUE=")]
    assert len(lines) == 1, f"expected one sentinel, got {lines}\n{done.stdout[-400:]}"
    # This fixture has no tier-1 queue, so there is nothing to refine.
    assert lines[0] == "TIER2_QUEUE=none", lines[0]
    assert done.returncode == 0, (
        "a refusal is not a failure of the selection step; the shell reads "
        "the sentinel, not the status"
    )


def test_the_sentinel_is_read_by_prefix_so_trailing_output_cannot_hide_it():
    """A pixi environment can print a warning after the answer."""
    script = SCRIPT.read_text()
    assert "s/^TIER2_QUEUE=//p" in script, (
        "the shell no longer reads the sentinel by prefix"
    )


def test_the_shell_refines_only_when_a_queue_was_written():
    script = SCRIPT.read_text()
    body = "\n".join(line for line in script.splitlines()
                     if not line.strip().startswith("#"))
    assert 'if [ "$QUEUE" = "none" ]; then' in body
    assert 'if [ -z "$QUEUE" ]; then' in body, (
        "a selector that printed no sentinel at all is not handled, so an "
        "older build would fall through to the refiner"
    )
    # And both checks must precede the refiner.
    refine = body.index("nobble.execute.runner")
    for guard in ('if [ -z "$QUEUE" ]; then', 'if [ "$QUEUE" = "none" ]; then'):
        assert body.index(guard) < refine, f"{guard} runs after the refiner"


def test_the_shell_reads_the_selector_status_not_tees(tmp_path):
    """The pipeline's first element, which is F188's lesson applied here."""
    body = SCRIPT.read_text()
    assert "PIPESTATUS[0]" in body, (
        "the selector's status is taken from tee rather than from the "
        "selector, so a crash in it would read as success"
    )


def test_the_exit_codes_the_shell_uses_are_distinct():
    """3 is Gate G1, 4 is "no sentinel", 0 is "nothing to refine"."""
    body = SCRIPT.read_text()
    assert "exit 3" in body and "exit 4" in body
    assert body.index("exit 3") < body.index("exit 4"), (
        "the gate check no longer runs before the sentinel check, so an open "
        "gate would be reported as a missing sentinel"
    )
