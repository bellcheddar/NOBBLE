"""A domain entry annotated twice has two answers, and one was being taken.

CLAUDE.md: construct boundaries come from InterPro named entries, never
hardcoded ranges. The lookup was doing that, and resolving a case the
lookup cannot resolve on its own.

FEM1B carries IPR036770, the ankyrin repeat superfamily, at residues 5-301
and again at 424-610. `domain_by_accession` returned whichever InterPro
listed first, so "the ankyrin domain of FEM1B" meant 297 residues or 187
residues depending on an ordering nobody here controls. Had that ordering
changed, the construct would have become a different protein region with
nothing failing: no error, no warning, a campaign folded against the wrong
half of a ligase.

The same reasoning was already applied one level down. Fragments within a
location are taken by min and max rather than by position, with a comment
saying that relying on InterPro's ordering would be relying on an
undocumented property of someone else's API. It simply had not been
applied to which location.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.curate import constructs as C  # noqa: E402
from nobble.curate import interpro  # noqa: E402

AMBIGUOUS = ("Q9UK73", "IPR036770")       # FEM1B, ankyrin superfamily, twice


def _available():
    try:
        return bool(interpro.domains(AMBIGUOUS[0]))
    except Exception:                       # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(
    not _available(), reason="InterPro cache not available on this checkout"
)


def test_an_entry_annotated_twice_refuses_without_an_occurrence():
    with pytest.raises(interpro.AmbiguousEntry) as caught:
        interpro.domain_by_accession(*AMBIGUOUS)
    message = str(caught.value)
    # The refusal has to name the alternatives, or the caller cannot act on it.
    assert "5-301" in message and "424-610" in message, message
    assert "annotated 2 times" in message


def test_an_occurrence_selects_from_the_n_terminus():
    first = interpro.domain_by_accession(*AMBIGUOUS, 0)
    second = interpro.domain_by_accession(*AMBIGUOUS, 1)
    assert (first["start"], first["end"]) == (5, 301)
    assert (second["start"], second["end"]) == (424, 610)
    assert first["start"] < second["start"]


def test_an_occurrence_past_the_end_is_refused():
    with pytest.raises(KeyError, match="does not exist"):
        interpro.domain_by_accession(*AMBIGUOUS, 2)


def test_an_unambiguous_entry_needs_no_occurrence():
    """So the refusal cannot be satisfied by refusing everything."""
    record = interpro.domain_by_accession("Q96SW2", "IPR034750")
    assert record["start"] < record["end"]


def test_records_are_returned_in_a_deterministic_order():
    """Which the occurrence index depends on. Sorted by position, so it does
    not inherit the order InterPro happened to list them in."""
    records = interpro.domains(AMBIGUOUS[0])
    starts = [(r["start"], r["end"]) for r in records]
    assert starts == sorted(starts), "domains() is no longer position-ordered"


def test_every_construct_segment_resolves_unambiguously():
    """The invariant. A construct whose entry becomes ambiguous, because
    InterPro reannotates the protein, now fails here rather than silently
    taking one of the two."""
    unresolved = []
    for name, construct in C.CONSTRUCTS.items():
        for index, segment in enumerate(construct.segments):
            try:
                segment.range()
            except interpro.AmbiguousEntry as problem:
                unresolved.append(f"{name} segment {index}: {problem}")
            except Exception:               # noqa: BLE001
                continue                    # a lookup failure is another test's
    assert not unresolved, unresolved


def test_the_construct_boundaries_are_what_they_were():
    """Pinned values, so a reordering upstream cannot move a boundary
    quietly. These are measured, not asserted: each came from the lookup
    and is recorded here so a change has to be deliberate."""
    expected = {
        ("CRBN_CULT", 0): (318, 426),
        ("VHL_VCB", 0): (64, 203),
        ("DCAF15_DDB1_DDA1", 0): (35, 259),
        ("DCAF15_DDB1_DDA1", 1): (387, 599),
        ("DCAF15_DDB1_DDA1", 2): (15, 348),
        ("DCAF15_DDB1_DDA1", 3): (790, 1099),
        ("DDB1_BPC", 0): (790, 1099),
        ("KEAP1_KELCH", 0): (309, 624),
        ("FEM1B_ANK", 0): (5, 301),
    }
    for (name, index), bounds in expected.items():
        segment = C.CONSTRUCTS[name].segments[index]
        assert segment.range() == bounds, (
            f"{name} segment {index} moved from {bounds} to {segment.range()}"
        )


def test_fem1b_declares_which_ankyrin_region_it_means():
    """The declaration is the fix. Without it the lookup refuses, which is
    better than guessing and still not a construct."""
    segment = C.CONSTRUCTS["FEM1B_ANK"].segments[0]
    assert segment.interpro_occurrence == 0, (
        "FEM1B no longer says which of its two ankyrin regions it means"
    )
    assert len(segment.sequence()) == 297
