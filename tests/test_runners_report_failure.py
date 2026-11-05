"""Every runner can say "failed" (F195).

A runner that always exits 0 cannot be gated on, and the only way to find
one is to ask what its exit status would be if its principal command failed.
Reading the script does not tell you: the bug is an absence.

The family had three states when this was written. `run_queue.sh` and
`run_msa.sh` captured the status on its own line, reported it and exited with
it. `run_corrected.sh` captured and reported it and exited 0 anyway, which is
F190 fixing the log line and stopping there. `run_substrate_msa.sh` ended on
an `echo`, so its status was the echo's and a failed precompute reported
success.

Low severity, and worth saying so: the chain calls the runner and the scorer
directly, and `run_queue.sh` with a deliberate `|| true`, so none of this was
breaking the live path the way F194's refresh was. It matters for an operator
running a script by hand and for `status.sh`, which scans these logs for
failures that `exit=0` can never match.

This enumerates the family rather than naming the two files that were wrong,
so a new runner cannot ship with a status that only ever says success.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Scripts whose job is to run one long thing and report how it went. The
# sourced helpers are not runners, and `status.sh` and `refresh.sh` are
# multi-step and judged by their own tests (F194).
RUNNERS = ["run_queue.sh", "run_corrected.sh", "run_design.sh",
           "run_msa.sh", "run_substrate_msa.sh", "tier2.sh"]


def body(name: str) -> str:
    text = (ROOT / "tools" / name).read_text()
    return "\n".join(line for line in text.splitlines()
                     if not line.strip().startswith("#"))


@pytest.mark.parametrize("name", RUNNERS)
def test_the_runner_captures_a_status_on_its_own_line(name):
    """Not inline with a command substitution, which clobbers it (F190)."""
    text = body(name)
    # `${PIPESTATUS[0]}` counts: tier2.sh captures that way because its
    # selector is piped through tee, and it is more correct than `$?` there,
    # not less. The first version of this regex accepted only `=$?` and
    # reported that script as having no capture at all.
    assert re.search(r"^\s*[A-Z_a-z]+=(\$\?|\$\{PIPESTATUS\[0\]\}|"
                     r'"\$\{PIPESTATUS\[0\]\}")\s*$',
                     text, re.M), (
        f"{name} never captures an exit status on a line of its own"
    )
    assert not re.search(r'exit=\$\?', text), (
        f"{name} reads $? inline in a string, where an earlier $(...) on the "
        "same line has already overwritten it"
    )


@pytest.mark.parametrize("name", RUNNERS)
def test_the_runner_can_exit_non_zero_from_a_captured_status(name):
    """The property, rather than a proxy for it.

    This first asserted the last line is not an `echo`, which is a proxy: a
    multi-step script may legitimately end on one, as long as every failure
    path has exited before it. `tier2.sh` is that case and the proxy called
    it broken. What actually matters is that somewhere the script exits with
    a status it captured, so a failure can leave the script non-zero.
    """
    text = body(name)
    assert re.search(r'^\s*exit "?\$\{?[A-Za-z_]+\}?"?\s*$', text, re.M), (
        f"{name} never exits with a captured status, so every run of it "
        "leaves 0 however it went"
    )


@pytest.mark.parametrize("name", ["run_queue.sh", "run_corrected.sh",
                                  "run_msa.sh", "run_substrate_msa.sh"])
def test_the_single_command_runners_propagate_it(name):
    """The four that wrap one command end by exiting with its status.

    `run_design.sh` and `tier2.sh` are excluded: they have steps after the
    inference and exit on their own terms, which their own tests cover.
    """
    text = body(name)
    assert re.search(r"^\s*exit \$\{?(STATUS|status)\}?\s*$", text, re.M), (
        f"{name} does not exit with the status it captured, so a caller "
        "cannot tell a failed run from a clean one"
    )


def test_the_capture_and_propagate_pattern_actually_works():
    """Demonstrated, because the whole family relies on this one idiom."""
    done = subprocess.run(
        ["bash", "-c", 'false; STATUS=$?; echo "exit=$STATUS"; exit $STATUS'],
        capture_output=True, text=True)
    assert done.stdout.strip() == "exit=1"
    assert done.returncode == 1

    # And the shape that was wrong: the echo swallows the status.
    swallowed = subprocess.run(
        ["bash", "-c", 'false; STATUS=$?; echo "exit=$STATUS"'],
        capture_output=True, text=True)
    assert swallowed.stdout.strip() == "exit=1"
    assert swallowed.returncode == 0, (
        "a script ending on an echo no longer exits 0, so this test is no "
        "longer demonstrating the difference"
    )
