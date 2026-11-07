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
    "stale": "F47 and F59: a YAML no longer matches the queue row describing it",
    "folded": "F219: the cached featurisation does not match the YAML",
    "seen['blind']": "the featurisation check could not compare every job",
    "regenerated": "F266: the YAML is not what the current code emits",
    "leaked": "spec 2.1: chemistry whose provenance may not be redistributed",
}
# Named after the first version of this file listed three of the nine
# refusing branches and I only noticed by printing them. The two that were
# missing are the ones at either end: `stale`, which is the F47 check that
# precedes the featurisation one, and `leaked`, which is the licensing guard
# CLAUDE.md states without qualification, that PROTAC-DB is never
# redistributed. A test of "the refusals" that silently covered a third of
# them is the same defect as the gates it was written about (F276).


def _all_refusing_branches() -> list[tuple[str, ast.If]]:
    """Every `If` in the builder whose body returns a non-zero code.

    A list rather than a mapping, because two branches can test the same
    expression. `if leaked:` appears twice, once verifying that redaction
    removed PROTAC-DB's chemistry by searching the written bundle for a known
    fragment, and once comparing the published chemistry against PROTAC-DB's
    own table. Keyed by the condition they collapsed to one entry and this
    file covered a single licensing refusal while believing it covered the
    only one (F276).
    """
    tree = ast.parse(BUILDER.read_text())
    found: list[tuple[str, ast.If]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        returns_failure = any(
            isinstance(inner, ast.Return)
            and isinstance(inner.value, ast.Constant)
            and inner.value.value not in (0, None)
            for inner in ast.walk(node))
        if returns_failure:
            found.append((ast.unparse(node.test), node))
    return sorted(found, key=lambda pair: pair[1].lineno)


def _refusing_branches() -> dict[str, ast.If]:
    """The earliest branch per condition, for the checks that want one."""
    out: dict[str, ast.If] = {}
    for test, node in _all_refusing_branches():
        out.setdefault(test, node)
    return out


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


# The refusals about the inputs, which can all be decided before anything is
# built. `leaked` is not among them: it inspects the built bundle, so it
# necessarily runs after the build, and its own case is below.
BEFORE_THE_BUILD = ("stale", "folded", "seen['blind']", "regenerated")


def test_the_input_refusals_come_before_the_output_directory_is_cleared():
    """Order, because the builder removes the previous slice before writing.

    A refusal after `shutil.rmtree(OUT)` leaves the published slice gone and
    the new one not built. For a refusal that could have been decided from
    the inputs, that is strictly worse than either outcome it chooses
    between.
    """
    tree = ast.parse(BUILDER.read_text())
    clears = [node for node in ast.walk(tree)
              if isinstance(node, ast.Call)
              and "rmtree" in ast.unparse(node.func)]
    assert clears, "the builder no longer clears its output directory"
    first_clear = min(node.lineno for node in clears)
    branches = _refusing_branches()
    for test in BEFORE_THE_BUILD:
        node = branches.get(test)
        assert node is not None, (test, sorted(branches))
        assert node.lineno < first_clear, (
            f"the refusal on {test} is at line {node.lineno}, after the "
            f"output directory is cleared at {first_clear}, so it leaves no "
            "atlas at all when it fires")
    unknown = [test for test in branches if "unavailable" in test]
    for test in unknown:
        assert branches[test].lineno < first_clear, test


def test_both_licensing_refusals_are_present():
    """Two of them, testing the same name and doing different work.

    One searches the written bundle for a known PROTAC-DB fragment, which
    verifies that redaction happened rather than trusting it. The other
    compares the published chemistry against PROTAC-DB's own table, because a
    record whose source is spelled differently would be redacted and then
    pronounced clean. Spec 2.1 is unqualified about this, so losing either to
    a dict key is not acceptable.
    """
    leaked = [node for test, node in _all_refusing_branches()
              if test == "leaked"]
    assert len(leaked) == 2, (
        f"{len(leaked)} branch(es) refuse on `leaked`; there were two, one "
        "verifying the redaction and one checking provenance against "
        "PROTAC-DB's table")
    for node in leaked:
        assert not isinstance(node.test, ast.Constant), ast.unparse(node)


def test_neither_licensing_refusal_implies_nothing_was_written():
    """Both fire after the build, so both leave a bundle on disk.

    They cannot run earlier: one searches the written files for a known
    PROTAC-DB fragment and the other reads the published chemistry. So the
    previous slice is already gone when either fires, and an operator who
    reads only the word REFUSED would reasonably conclude nothing was
    written.

    Each says so in its own way, and this asserts the property rather than
    the sentence. The first names the files inside the bundle that still hold
    the chemistry, which cannot be read as "nothing exists". The second says
    the bundle is on disk and not publishable.

    Written this way after two wrong versions: one asserted every refusal
    precedes the rmtree, which this pair cannot; the other asserted on
    whichever branch came first and so checked the wrong message (F276).
    """
    leaked = [node for test, node in _all_refusing_branches()
              if test == "leaked"]
    assert len(leaked) == 2, len(leaked)
    tree = ast.parse(BUILDER.read_text())
    clears = [node.lineno for node in ast.walk(tree)
              if isinstance(node, ast.Call)
              and "rmtree" in ast.unparse(node.func)]
    for node in leaked:
        assert node.lineno > min(clears), (
            f"the licensing check at line {node.lineno} now runs before the "
            "build, which it cannot do: it reads the written bundle")

    verifying, provenance = leaked
    # The first names what is still in the bundle.
    assert "leaked" in ast.unparse(verifying.body[0]), ast.unparse(verifying)
    assert "still present" in ast.unparse(verifying), ast.unparse(verifying)
    # The second says what state the bundle is left in.
    body = ast.unparse(provenance)
    assert "on disk" in body, (
        "the provenance refusal no longer says the bundle is on disk, so an "
        "operator cannot tell the previous slice was already removed")
    assert "not publishable" in body, body[:200]
