#!/usr/bin/env python
"""Which assertions never ran? (F152)

The failure that keeps recurring in this project is a test that cannot fail.
F107 had two tests looping on a key the plan does not carry, so every
iteration hit `continue`. F111's strict-side test filtered on a line that
never matched. F122's asserted the wrong check. F131's permitted the defect
it existed to catch. One of mine this session asserted the right outcome for
the wrong reason. Every one of them passed, and passing is what made them
invisible.

Some of that shape is detectable statically, and most of what it detects is
innocent: 68 tests have every assertion inside a loop, and nearly all of them
loop over something that cannot be empty, such as every template or every
construct. A static sweep that names 68 tests to read is not a sweep anyone
runs twice.

The measurement that is actually decisive is whether each assertion
*executed*. An assertion that never runs cannot fail, whatever it says, and
that is true whether it sits behind an empty loop, an early return, a skip, a
branch that is never taken, or a filter that matches nothing.

So this runs the suite under a line tracer and reports the assertions no run
reached. `coverage` is not in the environment and this needs one number, not
a report, so the tracer is twenty lines.

What it cannot tell you is whether an assertion that did run is *about*
anything. F122's test ran its assertion and asserted the wrong thing. This
narrows where to look; it does not do the looking.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"


def assertion_lines() -> dict[str, dict[int, str]]:
    """Every assert in tests/, by file and line, with the function it is in.

    Every function, not only the ones called `test_*`. The first version of
    this walked `test_*` definitions alone, and 37 assertions live in
    module-level helpers: `_published_names`, `_run_panel`, `_page`,
    `check`. Those are where a test's real check often sits, and a helper
    that is never called because every caller skips has assertions that
    never run, which is exactly what this exists to find. It could not see
    them (F166).

    Assertions outside any function are attributed to the module, since one
    at import time runs or the file does not load.
    """
    found: dict[str, dict[int, str]] = {}
    for path in sorted(TESTS.glob("test_*.py")):
        tree = ast.parse(path.read_text())
        owner: dict[int, str] = {}

        def claim(node: ast.AST, name: str) -> None:
            for inner in ast.walk(node):
                if isinstance(inner, ast.Assert):
                    owner.setdefault(inner.lineno, name)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                claim(node, node.name)
        # Anything left is at module level or inside a class body.
        claim(tree, "(module level)")
        if owner:
            found[str(path)] = owner
    return found


def main() -> int:
    wanted = assertion_lines()
    seen: set[tuple[str, int]] = set()
    files = set(wanted)

    def trace(frame, event, arg):
        name = frame.f_code.co_filename
        if name not in files:
            return None
        if event == "line":
            seen.add((name, frame.f_lineno))
        return trace

    import pytest

    sys.settrace(trace)
    try:
        code = pytest.main(["-q", "-p", "no:cacheprovider", str(TESTS)])
    finally:
        sys.settrace(None)

    total = sum(len(lines) for lines in wanted.values())
    missed: dict[str, list[tuple[int, str]]] = {}
    for path, lines in wanted.items():
        for line, test in sorted(lines.items()):
            if (path, line) not in seen:
                missed.setdefault(path, []).append((line, test))

    print(f"\n{total} assertion(s) in {len(wanted)} test file(s); "
          f"{total - sum(len(v) for v in missed.values())} executed")
    if not missed:
        print("every assertion ran")
        return 0
    print(f"\n{sum(len(v) for v in missed.values())} assertion(s) never ran:")
    for path in sorted(missed):
        print(f"  {pathlib.Path(path).name}")
        for line, test in missed[path]:
            print(f"    line {line:5d}  {test}")
    print("\nAn assertion that never runs cannot fail. Each is a skip, an "
          "empty loop, an untaken branch or a filter that matches nothing: "
          "the first three may be deliberate and the fourth is the bug this "
          "exists to find.")
    return 1 if code == 0 else int(code)


if __name__ == "__main__":
    raise SystemExit(main())
