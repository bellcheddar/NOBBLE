"""Every refusal in the atlas build still refuses.

`deploy/build_atlas.py` stands between a superseded input and a published
pose, and it does so with four branches: the cached featurisation disagreeing
with the YAML (F219), that check being blind (F218's shape), the YAML
disagreeing with the code that emits it (F266), and that check being
unavailable.

`tools/mutate.py` showed that replacing the first with `if False:` is caught
by nothing in the suite. The tool's own docstring records the consequence of
exactly that mutation happening once before: a test then rebuilt the published
atlas from a campaign with 54 of 2,360 jobs scored. So the danger was known,
the instance had happened, and no test had been written for it (F273).

Parsed rather than searched, for F272's reason: a guard replaced by
`if False:` leaves every string in place, so a test that greps for the call or
the message passes while the refusal is gone. An `If` whose test is the right
expression and whose body returns non-zero is the thing that cannot be
satisfied by unreachable text.

What this does not do is run the builder. Running it refuses on the first
branch today, so every later branch would be untested and the suite would be
asserting the order of refusals rather than their presence.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BUILDER = ROOT / "deploy" / "build_atlas.py"

# The expression each refusal tests, as `ast.unparse` renders it, against the
# finding that put it there. Named individually rather than counted: a count
# passes when one refusal is deleted and another duplicated.
REFUSALS = {
    "folded": "F219: the cached featurisation does not match the YAML",
    "seen['blind']": "the featurisation check could not compare every job",
    "regenerated": "F266: the YAML is not what the current code emits",
}


def _refusing_branches() -> dict[str, ast.If]:
    """Every `If` in the builder whose body returns a non-zero code."""
    tree = ast.parse(BUILDER.read_text())
    found: dict[str, ast.If] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        returns_failure = any(
            isinstance(inner, ast.Return)
            and isinstance(inner.value, ast.Constant)
            and inner.value.value not in (0, None)
            for inner in ast.walk(node))
        if returns_failure:
            found[ast.unparse(node.test)] = node
    return found


def test_every_known_refusal_is_present_and_returns_failure():
    branches = _refusing_branches()
    missing = {test: why for test, why in REFUSALS.items()
               if test not in branches}
    assert not missing, (
        "the atlas build no longer refuses on: "
        + "; ".join(f"{test} ({why})" for test, why in missing.items())
        + f". Branches that do refuse: {sorted(branches)}")


def test_the_unknown_cases_refuse_too():
    """A check that cannot run must not read as a check that passed.

    Two of the four branches are about the guard being blind rather than the
    campaign being wrong, and both exist because F216 and F218 are the same
    mistake: reading "could not compare" as "nothing to report".
    """
    branches = _refusing_branches()
    unknown = [test for test in branches
               if "blind" in test or "unavailable" in test]
    assert len(unknown) >= 2, (
        f"only {unknown} refuse on an unknown, so a failed comparison can "
        "read as a pass")


def test_a_refusal_cannot_be_satisfied_by_unreachable_text():
    """The mutation this file exists for, asserted as a property.

    Every refusal's test must be a real expression rather than a constant.
    `if False:` and `if 0:` both leave the call, the message and the return
    exactly where they were.
    """
    branches = _refusing_branches()
    constant = [test for test, node in branches.items()
                if isinstance(node.test, ast.Constant)]
    assert not constant, (
        f"these refusals test a constant and so never fire: {constant}")


def test_the_refusals_come_before_the_output_directory_is_cleared():
    """Order, because the builder removes the previous slice before writing.

    A refusal after `shutil.rmtree(OUT)` would leave no atlas at all: the
    published slice gone and the new one not built, which is worse than
    either outcome the refusal chooses between.
    """
    source = BUILDER.read_text()
    tree = ast.parse(source)
    clears = [node for node in ast.walk(tree)
              if isinstance(node, ast.Call)
              and "rmtree" in ast.unparse(node.func)]
    assert clears, "the builder no longer clears its output directory"
    first_clear = min(node.lineno for node in clears)
    for test, node in _refusing_branches().items():
        if test in REFUSALS or "unavailable" in test or "blind" in test:
            assert node.lineno < first_clear, (
                f"the refusal on {test} is at line {node.lineno}, after the "
                f"output directory is cleared at {first_clear}")
