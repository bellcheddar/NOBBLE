"""`bash -n` cannot see inside a heredoc.

tools/status.sh carries its Python in `<<'PY'` heredocs. An edit to one of
those left a block at four spaces where it belonged at eight, and the shell
check passed: `bash -n` validates the shell and treats the heredoc as opaque
text, so the gates section of the status page raised IndentationError at
runtime and the G1 and G5 lines simply stopped printing. Everything either
side of it still printed, which is what let it through a visual check of the
output (F260).

Every script that embeds Python is compiled here. Compiling is not running:
it catches the syntax and indentation class of error, which is exactly the
class a shell syntax check cannot reach.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HEREDOC = re.compile(r"<<-?'(PY|PYTHON)'\n(.*?)\n\s*\1\n", re.S)
# And `python -c "..."`, which is how tools/run_chain.sh embeds its Python.
# Those matter more than the heredocs, not less: each chain stage runs behind
# `|| true`, so a syntax error there fails the stage and the chain carries on
# to the next one without the stage having done anything.
DASH_C = re.compile(r'bin/python"? -c "\n(.*?)\n"', re.S)
# A shell interpolation inside the Python is a value the shell substitutes
# before python sees it, almost always a path in a string literal. Replaced
# with a placeholder so the block parses as the shell will present it, rather
# than skipped, which would exempt every block that uses one.
INTERPOLATION = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?")


def _scripts() -> list[Path]:
    found = [path for directory in ("tools", "deploy")
             for path in sorted((ROOT / directory).glob("*.sh"))]
    assert found, "no shell scripts found: the glob has stopped matching"
    return found


def _blocks(path: Path) -> list[tuple[int, str]]:
    source = path.read_text()
    out = []
    for match in HEREDOC.finditer(source):
        line = source[:match.start()].count("\n") + 1
        out.append((line, match.group(2)))
    for match in DASH_C.finditer(source):
        line = source[:match.start()].count("\n") + 1
        block = INTERPOLATION.sub("SHELL_VALUE", match.group(1))
        # A `-c` block is a double-quoted shell string, so an escaped quote
        # inside it reaches python unescaped.
        out.append((line, block.replace('\\"', '"')))
    return out


@pytest.mark.parametrize("script", _scripts(), ids=lambda p: p.name)
def test_every_embedded_python_block_compiles(script):
    blocks = _blocks(script)
    if not blocks:
        pytest.skip(f"{script.name} embeds no Python heredoc")
    for line, block in blocks:
        try:
            compile(block, f"{script.name}:{line}", "exec")
        except SyntaxError as problem:
            raise AssertionError(
                f"{script.name} line {line}: the embedded Python does not "
                f"compile, so this block raises at runtime while the lines "
                f"either side of it still print. {type(problem).__name__}: "
                f"{problem}") from problem


def test_the_scan_finds_the_blocks_it_is_supposed_to_check():
    """A regex that matches nothing passes every script silently.

    Both forms are named rather than left to the glob: status.sh carries
    three heredocs and is the script this test was written for, and
    run_chain.sh carries three `python -c` blocks, which is the form the
    heredoc pattern alone does not see.
    """
    heredocs = _blocks(ROOT / "tools" / "status.sh")
    assert len(heredocs) >= 3, (
        f"found {len(heredocs)} heredoc(s) in status.sh, so the pattern has "
        "stopped matching and this test checks nothing")
    chain = _blocks(ROOT / "tools" / "run_chain.sh")
    assert len(chain) >= 3, (
        f"found {len(chain)} embedded block(s) in run_chain.sh, so the "
        "`python -c` pattern has stopped matching")


def test_a_mis_indented_block_is_caught():
    """The mutation, so the check is known to bite.

    This is the exact shape of the defect: a line at four spaces inside a
    branch indented to eight, which is what a text replacement produces when
    the pattern it matched was a substring of the more deeply indented copy.
    """
    broken = "if True:\n        print(1)\n    print(2)\n        raise SystemExit(0)\n"
    with pytest.raises(SyntaxError):
        compile(broken, "mutation", "exec")
