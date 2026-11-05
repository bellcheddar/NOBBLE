"""A step that gates publication has its status read (F194).

`tools/refresh.sh` ran score, validate, throughput and atlas, and piped two
of them into `tail`, which discards the exit status. The consequences were
not symmetrical:

- A failed score left `scores.jsonl` holding the previous run's values, and
  the atlas build copied them. The drift check cannot catch that, because a
  rebuild reads the same stale file: F171's compare-stale-against-stale, one
  layer up.
- A refused atlas build printed its refusal and the script then printed
  "=== refreshed. Deploy separately ===". That was live: `build_atlas.py`
  returns 1 on stale inputs, which is the main campaign's state today, so
  the chain would have reached refresh after thirty-six hours, refused to
  publish, and logged a successful refresh.

`run_design.sh` had the same gap in the other script that scores and then
consumes what it scored: its lift step reads those scores.

Throughput is deliberately not gating. It feeds a panel, and refusing to
publish a valid campaign because a timing summary failed is the wrong trade,
which is also why these runners do not use `set -e`: a uniform abort would
make every informational step fatal.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFRESH = ROOT / "tools" / "refresh.sh"
DESIGN = ROOT / "tools" / "run_design.sh"


def code_only(script: Path) -> str:
    return "\n".join(line for line in script.read_text().splitlines()
                     if not line.strip().startswith("#"))


def test_scoring_failure_stops_the_refresh_before_publishing():
    body = code_only(REFRESH)
    assert "SCORE_CODE=$?" in body
    assert re.search(r'if \[ "\$SCORE_CODE" -ne 0 \]', body), (
        "the scoring status is captured and not acted on"
    )
    # And it must stop before the atlas step, not merely complain.
    stop = body.index("SCORE_CODE")
    atlas = body.index("build_atlas.py")
    assert stop < atlas
    assert "exit 1" in body[stop:atlas], (
        "a failed score does not stop the refresh, so the atlas would copy "
        "the previous run's scores"
    )


def test_a_refused_atlas_build_is_not_reported_as_a_refresh():
    body = code_only(REFRESH)
    assert "ATLAS_CODE=$?" in body
    guard = body.index("ATLAS_CODE")
    done = body.index("=== refreshed.")
    assert guard < done, "the success line is printed before the build is judged"
    assert "exit 1" in body[guard:done], (
        "the script still says it refreshed after a refused build"
    )


def test_neither_gating_step_pipes_its_status_away():
    """`cmd | tail` makes $? tail's, which is how both of these were lost."""
    body = code_only(REFRESH)
    for gating in ("nobble.score.run", "build_atlas.py"):
        line = next(l for l in body.splitlines() if gating in l)
        assert "|" not in line, (
            f"{gating} is piped, so its status is the pipe's last command: "
            f"{line.strip()}"
        )


def test_throughput_warns_rather_than_blocking():
    """The asymmetry is deliberate and should stay visible."""
    body = code_only(REFRESH)
    assert "THROUGHPUT_CODE=$?" in body
    start = body.index("THROUGHPUT_CODE")
    end = body.index("--- atlas")
    between = body[start:end]
    assert "exit 1" not in between, (
        "a throughput failure now blocks publication, which refuses to "
        "publish good science over a timing summary"
    )


def test_every_script_that_scores_then_uses_the_scores_checks_it():
    """The category, not the instance: refresh.sh and run_design.sh."""
    for script in (REFRESH, DESIGN):
        body = code_only(script)
        if "nobble.score.run" not in body:
            continue
        assert "SCORE_CODE=$?" in body, (
            f"{script.name} runs the scorer and does not read its status, so "
            "the step that consumes the scores would read stale ones"
        )
        assert re.search(r'if \[ "\$SCORE_CODE" -ne 0 \]', body), script.name


def test_the_design_scan_does_not_lift_from_stale_scores():
    body = code_only(DESIGN)
    score = body.index("nobble.score.run")
    lift = body.index("design import lift")
    assert "SCORE_CODE" in body[score:lift]
    assert "exit 1" in body[score:lift], (
        "a failed score falls through to the lift, which would compute a "
        "number that looks like a measurement of this scan"
    )
