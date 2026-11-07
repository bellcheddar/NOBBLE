"""Every tool compiles, and every tool with a CLI answers --help.

Two edits of mine broke working code today without any test noticing: a
mis-indented heredoc that removed the status page's gates section (F260) and
a local shadowing a name fifteen lines above it, which turned the token-cap
check into a substring search and took Tier B's preflight from ok to refusing
(F263). Both were caught by comparing output against a run twenty minutes
earlier.

What those have in common is that nothing exercised the code. A tool that no
test imports can carry a syntax error, a bad import or a broken argparse
indefinitely, and the thing that finds it is someone running it at 3am.

Compiling catches the syntax class. `--help` catches module-level import
time: a tool whose top-level imports are broken cannot print its own usage.

What it does not catch, and the reason the whole suite runs in under a second:
these tools defer their heavy imports into `main` or into the function that
needs them, so `--help` returns in about 30 milliseconds without touching
gemmi, torch or a campaign. An import written inside a function is not
exercised here. Saying so is the point: a smoke test that is believed to cover
more than it does is worse than one whose edges are written down.

Verified by breaking a tool's import by hand and confirming both tests fail
on it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _scripts() -> list[Path]:
    found = sorted((ROOT / "tools").glob("*.py"))
    found += sorted((ROOT / "deploy").glob("*.py"))
    assert len(found) >= 18, f"only found {len(found)}: the glob has moved"
    return found


def _has_cli(path: Path) -> bool:
    source = path.read_text()
    return "argparse" in source and '__name__ == "__main__"' in source


@pytest.mark.parametrize("script", _scripts(), ids=lambda p: p.name)
def test_the_tool_compiles(script):
    # Captured and then asserted, rather than re-raised from the except
    # block. Raising works, but `test_no_assertion_in_the_suite_can_pass
    # _unconditionally` reads the suite structurally and a test with no
    # `assert` in it looks exactly like one that cannot fail. It caught this,
    # which is the guard doing its job, so the test changes and the guard
    # does not.
    problem = None
    try:
        compile(script.read_text(), str(script), "exec")
    except SyntaxError as failure:
        problem = failure
    assert problem is None, f"{script.name} does not compile: {problem}"


@pytest.mark.parametrize(
    "script", [p for p in _scripts() if _has_cli(p)], ids=lambda p: p.name)
def test_the_tool_answers_help(script):
    """A tool that cannot print its usage cannot be run at all.

    PYTHONPATH is set because these tools insert the project root themselves
    and a few import `nobble` before doing so; the point here is the tool, not
    the invocation.
    """
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    out = subprocess.run([sys.executable, str(script), "--help"],
                         capture_output=True, text=True, timeout=180,
                         cwd=ROOT, env=env)
    assert out.returncode == 0, (
        f"{script.name} --help exited {out.returncode}\n"
        f"stdout: {out.stdout[-600:]}\nstderr: {out.stderr[-900:]}")
    assert "usage" in (out.stdout + out.stderr).lower(), out.stdout[-400:]


def test_the_cli_filter_finds_the_tools_it_should():
    """A filter that matches nothing passes every tool silently."""
    with_cli = [p.name for p in _scripts() if _has_cli(p)]
    assert len(with_cli) >= 12, with_cli
    for expected in ("preflight.py", "check_registered.py", "build_atlas.py"):
        assert expected in with_cli, (expected, with_cli)
