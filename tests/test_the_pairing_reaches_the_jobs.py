"""The matching travels from the peptide to the score row (F317b).

Both of the project's paired designs are built at curation time. A
composition-matched scramble records the peptide it scrambles, and every
Sievers matched control records the positive it was matched to, both as
`Peptide.parent_peptide_id`. `metrics.aggregate` already reads
`parent_peptide_id` off the job row into the score row.

`manifest.py` was the only link that did not copy it. So the queue had no
such key, the score rows carried it as None, and `matched_control_roc` and
every analysis after it could only be unpaired, while the pairing sat intact
in `data/manifests/library.jsonl`.

These assert the link rather than the plumbing: a scramble and a matched
control both arrive at a job record naming their parent.
"""
from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.curate import manifest as M                    # noqa: E402


def test_the_job_record_carries_the_parent():
    # `Job`, not `Member`: the dataclass that becomes a queue row is called
    # Job here. Guessing the name is how a test asserts nothing.
    names = {f.name for f in fields(M.Job)}
    assert "parent_peptide_id" in names, (
        "the manifest member drops the matching, so the queue cannot carry "
        "it and every analysis downstream is forced to be unpaired"
    )


def test_the_builder_copies_it_from_the_peptide():
    """A field that exists and is never assigned is worse than no field: it
    reads as a measured absence."""
    source = (ROOT / "nobble" / "curate" / "manifest.py").read_text()
    assert "parent_peptide_id=peptide.parent_peptide_id" in source


def test_the_score_row_reads_the_same_key():
    """One spelling across the three files, or the copy lands somewhere the
    scorer does not look."""
    metrics = (ROOT / "nobble" / "score" / "metrics.py").read_text()
    assert 'parent_peptide_id=first.get("parent_peptide_id")' in metrics


def test_a_scramble_and_a_matched_control_both_name_a_parent():
    """The two designs, checked on the frozen library rather than argued
    from the code. A scramble names the peptide it scrambles and a Sievers
    control names the positive it was matched to."""
    import pytest

    from nobble import paths

    library = ROOT / "data" / "manifests" / "library.jsonl"
    if not library.exists():
        pytest.skip("no library manifest on this checkout")
    rows = paths.read_jsonl(library, tolerate_torn=True)

    scrambles = [row for row in rows if row.get("source") == "scramble"]
    controls = [row for row in rows if row.get("source") == "sievers_zf"
                and row.get("label") == "not_degraded"]
    if not scrambles or not controls:
        pytest.skip("the library holds neither design")

    for name, group in (("scramble", scrambles), ("matched control", controls)):
        orphans = [row.get("peptide_id") for row in group
                   if not row.get("parent_peptide_id")]
        assert not orphans, (
            f"{len(orphans)} {name}(s) name no parent, so they can only "
            f"enter an unpaired test: {orphans[:3]}")


def test_every_named_parent_is_itself_in_the_library():
    """A parent id pointing at nothing is a pairing that cannot be joined."""
    import pytest

    from nobble import paths

    library = ROOT / "data" / "manifests" / "library.jsonl"
    if not library.exists():
        pytest.skip("no library manifest on this checkout")
    rows = paths.read_jsonl(library, tolerate_torn=True)
    present = {row.get("peptide_id") for row in rows}
    dangling = sorted({row["parent_peptide_id"] for row in rows
                       if row.get("parent_peptide_id")
                       and row["parent_peptide_id"] not in present})
    assert not dangling, f"parent ids with no peptide: {dangling[:3]}"
