"""The third link: the YAML against the code that emits it.

An input's provenance has three links and only two were checked.
`inputs.stale_inputs` compares a YAML against the job record that describes
it. `tools/stale_featurisation.py` compares the cached featurisation against
the YAML, which is F219. Nothing compared the YAML against the assembler that
wrote it.

That is the link F262 broke. The ligand resolution dropped a SMILES-only
glue, so scr_bench03_BRD4_CRBN's ternary YAMLs were wrong from the moment
they were written, and they agreed with their own record and their own cache
all the way down: every guard reported the campaign clean (F266).

The scan costs about two seconds for 2,360 jobs, because `regenerate_all`
builds the manifest once and writes nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.validate import inputs


def _main_campaign() -> Path | None:
    from nobble.execute.campaign import latest

    found = latest("campaign")
    return Path(found) if found else None


def test_the_scan_finds_the_f262_jobs():
    campaign = _main_campaign()
    if campaign is None:
        pytest.skip("no campaign assembled")
    rows, status = inputs._regenerated_scan(campaign)
    if not rows:
        pytest.skip(f"the campaign's inputs now match the code: {status}")
    assert all("scr_bench03" in row["job_id"] for row in rows), rows
    assert all("__ternary__" in row["job_id"] for row in rows), rows
    assert "would not write" in status, status


def test_a_campaign_from_another_assembler_is_unavailable_not_clean():
    """Tier B comes from a different builder.

    Compared against the campaign manifest it reported all 154 of its pairs
    as work the code would not emit, which is a confident answer to a
    question nobody asked. The benchmark campaign's job ids happen to
    coincide with the main manifest's and compared clean, which is luck and
    not a basis for a check, so both are out of scope by name.
    """
    # Neither `tier_b_` nor `design_` is among them any longer: each has a
    # regenerator of its own since F340 and F341, and the scan reports both
    # clean rather than out of scope. The two that remain are complete
    # campaigns the chain does not run again.
    # The reason this test gives still holds and is why that regenerator
    # was written instead of widening the campaign one: compared against
    # the *campaign* manifest, Tier B reports all 154 of its pairs as work
    # the code would not emit.
    for prefix in ("benchmark_", "corrected_"):
        found = sorted((ROOT / "campaigns").glob(prefix + "*"))
        if not found:
            continue
        rows, status = inputs._regenerated_scan(found[-1])
        assert rows == [], (found[-1].name, rows[:3])
        # `not_applicable`, which the publish gate must not refuse on: the
        # atlas is legitimately built from the benchmark campaign, and
        # reporting this as `unavailable` refused that build.
        assert status.startswith("not_applicable"), (found[-1].name, status)
        assert "assembler" in status, status


def test_an_unreadable_campaign_is_unavailable_not_clean(tmp_path):
    """F216's mistake in whichever file repeats it.

    A failure in the scan must not read as "every input matches". The name
    has to start with `campaign_` to get past the scope check, so the
    fixture's does.
    """
    directory = tmp_path / "campaign_broken"
    directory.mkdir()
    (directory / "queue.jsonl").write_text("not json at all\n")
    rows, status = inputs._regenerated_scan(directory)
    assert status.startswith("unavailable"), status
    assert rows == [], rows


def test_a_campaign_with_no_queue_is_unavailable(tmp_path):
    directory = tmp_path / "campaign_empty"
    directory.mkdir()
    rows, status = inputs._regenerated_scan(directory)
    assert status.startswith("unavailable"), status


def test_the_publish_gate_refuses_on_it():
    """The refusal has to be in the builder, not only reported.

    This is the guard between a superseded input and a published pose, so a
    warning would not do. Read from the builder rather than run, because
    running it refuses earlier on F219 today and would pass for the wrong
    reason.

    Parsed rather than searched. The first version asserted that the strings
    "_regenerated_scan" and "return 1" appear in the source, and
    `tools/mutate.py` walked straight through it: replacing the condition
    with `if False:` leaves both strings exactly where they were, so the
    guard was removed and the test passed. Asserting on the parse tree
    costs the same and cannot be satisfied by text that is no longer
    reachable.
    """
    import ast

    source = (ROOT / "deploy" / "build_atlas.py").read_text()
    tree = ast.parse(source)
    assigned = [node for node in ast.walk(tree)
                if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Tuple) for t in node.targets)
                and "_regenerated_scan" in ast.unparse(node.value)]
    assert assigned, "build_atlas never calls _regenerated_scan"

    # The `if` that decides the refusal must test the rows the scan returned,
    # and its body must return non-zero.
    refusals = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if ast.unparse(node.test) != "regenerated":
            continue
        returns = [inner for inner in ast.walk(node)
                   if isinstance(inner, ast.Return)
                   and isinstance(inner.value, ast.Constant)
                   and inner.value.value == 1]
        if returns:
            refusals.append(node)
    assert refusals, (
        "no branch tests the scan's findings and returns 1, so a job holding "
        "a YAML the code would not write no longer stops the build")

    # And the unknown case refuses too, while the out-of-scope case does not.
    unknown = [node for node in ast.walk(tree)
               if isinstance(node, ast.If)
               and "unavailable" in ast.unparse(node.test)
               and any(isinstance(inner, ast.Return)
                       and isinstance(inner.value, ast.Constant)
                       and inner.value.value == 1
                       for inner in ast.walk(node))]
    assert unknown, (
        "the builder does not refuse when the check cannot run, so a failed "
        "comparison would read as a pass")
    assert "not_applicable" not in source, (
        "the builder mentions not_applicable, which is not an unknown: the "
        "atlas is legitimately built from the benchmark campaign")


def test_provenance_reports_the_link():
    source = (ROOT / "tools" / "provenance.py").read_text()
    assert "regenerated_status" in source, (
        "the status page does not show whether inputs match the code")
