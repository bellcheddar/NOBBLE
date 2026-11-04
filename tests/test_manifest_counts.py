"""Three findings from the third mutation sweep.

Each is logic whose mutation the whole suite ignored, because the data it
runs on makes the right and wrong answers coincide.

The validation counts are the clearest. Four places compute

    "errors":   sum(1 for issue in issues if issue.severity == "error")
    "warnings": sum(1 for issue in issues if issue.severity == "warning")

and `errors` is a gate: assemble.py and campaign.py both refuse to emit a
campaign when it is non-zero. Swapping the two severities went unnoticed
because the design manifest carries no issues at all, and the existing
assertion is `errors == 0`, which holds either way when both are zero.

The main campaign's manifest carries 20 warnings and no errors, so there
the same swap would have refused a perfectly good 2,360-job campaign.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.curate import manifest as M  # noqa: E402


def _issues(errors: int, warnings: int):
    out = []
    for index in range(errors):
        out.append(M.ValidationIssue(
            severity="error", code="deliberate", detail="an error",
            job_id=f"e{index}"))
    for index in range(warnings):
        out.append(M.ValidationIssue(
            severity="warning", code="deliberate", detail="a warning",
            job_id=f"w{index}"))
    return out


def test_the_issue_type_separates_the_two_severities():
    made = _issues(2, 3)
    assert [i.severity for i in made] == ["error", "error",
                                          "warning", "warning", "warning"]


def test_the_campaign_manifest_counts_each_severity_on_its_own_key(monkeypatch):
    """Two errors and three warnings must not come back as three and two."""
    from nobble.curate import library as LM

    lib = LM.load()
    if lib is None:
        pytest.skip("library manifest missing: run nobble.curate.library")

    monkeypatch.setattr(M, "validate", lambda jobs: _issues(2, 3))
    built = M.build_campaign_manifest(library=lib["peptides"])
    assert built["errors"] == 2, built["errors"]
    assert built["warnings"] == 3, built["warnings"]


def test_the_design_manifest_counts_each_severity_on_its_own_key(monkeypatch):
    from nobble.design import assemble as A

    monkeypatch.setattr(A.M, "validate", lambda jobs: _issues(2, 3))
    built = A.build_manifest(_a_scannable_parent())
    if built.get("status"):
        pytest.skip(built["status"])
    assert built["errors"] == 2, built["errors"]
    assert built["warnings"] == 3, built["warnings"]


def _a_scannable_parent():
    from nobble.app import data
    from nobble.design import report

    data.configure(str(ROOT / "deploy" / "atlas"))
    parent = (report.build().get("preview") or {}).get("parent")
    if not parent:
        pytest.skip("no scannable parent on this checkout")
    return parent["peptide_id"]


def test_assemble_refuses_to_emit_a_campaign_with_validation_errors(monkeypatch):
    """The gate the count feeds. Nothing is written: the refusal comes
    before the directory is created."""
    from nobble.design import assemble as A

    monkeypatch.setattr(
        A, "build_manifest",
        lambda *a, **k: {"errors": 2, "warnings": 0, "pairs": [], "jobs": []},
    )
    with pytest.raises(RuntimeError, match="validation errors"):
        A.assemble("whatever")


def test_a_design_manifest_has_exactly_one_parent_among_its_pairs():
    """What the campaign writer's role branch depends on. The writer builds
    the parent's peptide from the library row and carries its cofactor
    across, and builds each variant from the pair itself; conflating the two
    would drop a zinc finger's zinc, which D-NOB-034 says invalidates
    Delta-ipTM outright."""
    from nobble.design import assemble as A

    built = A.build_manifest(_a_scannable_parent())
    if built.get("status"):
        pytest.skip(built["status"])

    roles = [pair["role"] for pair in built["pairs"]]
    assert roles.count("parent") == 1, f"{roles.count('parent')} parents"
    assert roles.count("variant") == len(roles) - 1
    # Only the parent has a library row to be rebuilt from.
    assert list(built["peptides"]) == [
        pair["peptide_id"] for pair in built["pairs"] if pair["role"] == "parent"
    ]
    # Every pair carries a cofactor decision, so neither branch has to guess.
    assert all("cofactor" in pair for pair in built["pairs"])


def test_every_scramble_sits_immediately_behind_its_parent():
    """A control that runs without its positive, or a positive whose control
    was trimmed off the end of the queue, measures nothing. The ordering is
    what keeps them together when a budget truncates the queue.

    Checked against the library manifest the pipeline actually wrote rather
    than by calling reduce_library, which loads an ESM checkpoint: a unit
    test should not need a language model to verify a sort order.
    """
    import json

    path = ROOT / "data" / "manifests" / "library.jsonl"
    if not path.exists():
        pytest.skip("no library manifest: run nobble.curate.library")

    rows = [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]
    order = [row["peptide_id"] for row in rows]
    position = {peptide_id: index for index, peptide_id in enumerate(order)}

    scrambles = [row for row in rows if row.get("parent_peptide_id")
                 and row["peptide_id"].startswith("scr")]
    assert scrambles, "no scrambles in the library manifest"

    misplaced = []
    for row in scrambles:
        parent = row["parent_peptide_id"]
        if parent not in position:
            misplaced.append((row["peptide_id"], "parent not in the library"))
        elif position[row["peptide_id"]] != position[parent] + 1:
            misplaced.append((
                row["peptide_id"],
                f"at {position[row['peptide_id']]}, parent at {position[parent]}",
            ))
    assert not misplaced, (
        f"{len(misplaced)} scramble(s) are not immediately behind their "
        f"parent: {misplaced[:4]}"
    )
