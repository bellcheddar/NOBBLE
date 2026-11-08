"""Every tool is named somewhere that could lead you to run it.

F250 found orphaned functions and F296 found a command the chain told you to
run that did nothing. The same question for `tools/`: a script nothing names
is dead weight, and with 36 of them nobody notices one going cold.

**Being mentioned in a log does not count.** `FINDINGS.md` and `BUILD_LOG.md`
record what was done, including by tools since deleted, so a mention there
says a tool existed rather than that anything reaches it now. The places
that count are code, other scripts, the README, `CLAUDE.md`, `PROGRESS.md`
and the tests.

Checked by a sweep that came back clean on 2026-11-08, which is why this is a
test rather than a finding: the sweep is worth less than the test it should
have left behind (F295).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Logs record history, not reachability.
HISTORY = {"FINDINGS.md", "BUILD_LOG.md"}


def _tools() -> list[Path]:
    return sorted(path for pattern in ("*.py", "*.sh")
                  for path in (ROOT / "tools").glob(pattern))


def _named_by(name: str) -> list[str]:
    """Files that mention this tool, excluding itself and the logs."""
    done = subprocess.run(
        ["git", "grep", "-l", "--", name],
        cwd=ROOT, capture_output=True, text=True)
    out = []
    for line in done.stdout.splitlines():
        if not line.strip():
            continue
        if line == f"tools/{name}" or Path(line).name in HISTORY:
            continue
        out.append(line)
    return out


def test_the_sweep_has_something_to_sweep():
    """Otherwise the test below passes by checking nothing, which is F152."""
    found = _tools()
    assert len(found) >= 20, f"only {len(found)} tool(s) found under tools/"


def test_every_tool_is_named_outside_its_own_file_and_the_logs():
    orphans = {}
    for tool in _tools():
        if not _named_by(tool.name):
            orphans[tool.name] = "named only by itself or by a log"
    assert not orphans, (
        f"{len(orphans)} tool(s) nothing reaches: {sorted(orphans)}. Either "
        "something should call it, a document should tell you to, or it "
        "should go"
    )


def test_a_log_mention_alone_does_not_count():
    """The exclusion is the whole point of the check, so it is asserted
    rather than trusted: a tool named only in FINDINGS would pass a naive
    grep and reach nothing."""
    assert HISTORY == {"FINDINGS.md", "BUILD_LOG.md"}
    sample = _named_by("findings.py")
    assert sample, "findings.py is named nowhere outside the logs"
    assert all(Path(path).name not in HISTORY for path in sample)
