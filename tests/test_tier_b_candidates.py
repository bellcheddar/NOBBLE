"""Evidence beside each Tier B choice, and no choosing (F182).

D-NOB-068 keeps `config/tier_b_constructs.toml` a form because which domain
of a ligase binds its substrate is science knowledge, and says what code can
do is make answering cheap. `tools/tier_b_candidates.py` adds two measured
columns to the candidates the form already lists: the mean pLDDT over each
candidate's own range, and how much of it falls inside the frozen selection's
best 200-residue window.

The line it must not cross is ranking. F41 settled that in
`domain_by_accession`'s docstring and D-NOB-068 restates it: picking the
longest domain or the most confident one is the mechanical route that was
rejected. So these tests cover the arithmetic, the two bugs the tool had
while it was being written, and the ordering, which must stay the form's
order rather than become a league table by confidence.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from nobble import paths  # noqa: E402

import tier_b_candidates as tool  # noqa: E402


def test_the_cap_comes_from_config_and_is_not_written_in_the_tool():
    thresholds = paths.thresholds()
    expected = (int(thresholds["manifest"]["token_cap_tier1"])
                - int(thresholds["tier_b"]["construct_peptide_residues"])
                - int(thresholds["tier_b"]["construct_glue_heavy_atoms"]))
    assert tool.cap() == expected
    source = (ROOT / "tools" / "tier_b_candidates.py").read_text()
    assert str(expected) not in source, (
        "the cap is also written into the tool, so it can drift from config"
    )


def test_the_shortest_listed_annotation_comes_from_config():
    """F183: it was a bare 60 in the comparison, and 60 in the form's prose."""
    assert tool.floor() == int(
        paths.thresholds()["tier_b"]["construct_min_residues"])
    source = (ROOT / "tools" / "tier_b_candidates.py").read_text()
    import re
    # Docstrings stripped, because they discuss the literal this forbids.
    # The first version of this line had a stray `]` inside the pattern, so
    # it matched nothing and the check ran against the prose as well: it
    # passed, and would have false-alarmed the moment a docstring quoted
    # `length < 60`. Verified below rather than assumed.
    code = re.sub(r'""".*?"""', "", source, flags=re.S)
    assert '"""' not in code, "docstrings were not stripped"
    assert "Shortest annotation worth listing" not in code
    assert not re.search(r"length\s*<\s*\d+", code), (
        "the minimum length is compared against a literal again"
    )


def test_the_frozen_best_window_is_parsed_from_text_not_iterated():
    """The bug the first run printed: the parquet column is a string.

    `list("[302, 501]")` is ten single characters, and an overlap against
    those is not computable, so every window cell read `n/a`. A string that
    iterates without complaining is the shape F130's NaN had.
    """
    assert tool._window("[302, 501]") == [302, 501]
    assert tool._window([302, 501]) == [302, 501]
    assert tool._window("302, 501") == [302, 501]
    for nonsense in (None, "", "[302]", "not a window", "[1, 2, 3]"):
        assert tool._window(nonsense) is None, nonsense


def test_overlap_is_a_fraction_of_the_candidate_not_of_the_window():
    # A candidate wholly inside the window is 100 per cent of itself.
    assert tool.overlap_fraction((320, 400), [302, 501]) == 1.0
    # Half in, half out.
    assert tool.overlap_fraction((292, 311), [302, 501]) == pytest.approx(0.5)
    # Disjoint, and adjacent-but-disjoint, are both nothing.
    assert tool.overlap_fraction((100, 200), [302, 501]) == 0.0
    assert tool.overlap_fraction((300, 301), [302, 501]) == 0.0
    # A single shared residue is counted, inclusively.
    assert tool.overlap_fraction((301, 302), [302, 501]) == pytest.approx(0.5)
    assert tool.overlap_fraction((320, 400), None) is None


def _row(entry, start, end, label):
    return {"entry": entry, "label": label, "start": start, "end": end,
            "length": end - start + 1}


def test_one_region_annotated_twice_collapses_to_the_specific_entry():
    """InterPro lists a domain and its containing superfamily separately."""
    rows = [_row("IPR004367", 408, 531, "Cyclin, C-terminal domain"),
            _row("IPR036915", 407, 530, "Cyclin-like superfamily")]
    collapsed = tool._collapse(rows)
    assert len(collapsed) == 1
    assert collapsed[0]["entry"] == "IPR004367", "the superfamily label won"
    assert collapsed[0]["aliases"] == ["IPR036915"], (
        "the collapsed entry number vanished, which looks like missing data "
        "to anyone comparing this against InterPro"
    )


def test_the_specific_entry_wins_whichever_order_they_arrive_in():
    specific = _row("IPR004367", 408, 531, "Cyclin, C-terminal domain")
    vague = _row("IPR036915", 407, 530, "Cyclin-like superfamily")
    for rows in ([specific, vague], [vague, specific]):
        collapsed = tool._collapse([dict(r) for r in rows])
        assert len(collapsed) == 1
        assert collapsed[0]["entry"] == "IPR004367"


def test_two_copies_of_one_domain_in_different_places_stay_separate():
    """CCNF carries IPR013763 at 315-399 and again at 416-494.

    Those are two choices, not one annotated twice, and collapsing them
    would hide a real option. This is the case that decides how wide the
    slack may be.
    """
    rows = [_row("IPR013763", 315, 399, "Cyclin-like domain"),
            _row("IPR013763", 416, 494, "Cyclin-like domain")]
    assert len(tool._collapse(rows)) == 2


def test_the_slack_is_narrow_enough_to_keep_neighbouring_domains_apart():
    slack = tool.SAME_REGION_SLACK
    assert slack < 10, (
        f"a slack of {slack} residues will merge domains that genuinely abut"
    )
    just_outside = [_row("IPR000001", 100, 200, "A domain"),
                    _row("IPR000002", 100 + slack + 1, 200 + slack + 1, "B superfamily")]
    assert len(tool._collapse(just_outside)) == 2


def test_a_missing_model_gives_no_measurement_rather_than_zero():
    """Zero pLDDT would read as a disordered domain, which is a claim."""
    assert tool.window_mean_plddt("NOT_AN_ACCESSION", 1, 50) is None


def test_candidates_are_ordered_by_length_not_by_confidence():
    """The tool reports evidence; it must not rank by it (D-NOB-068, F41).

    Ordering by pLDDT would be a recommendation in all but name: the
    most-confident domain would sit at the top of every list, which is the
    mechanical route the decision record rejects.
    """
    rows = tool.selection()
    if not rows:
        pytest.skip("no frozen Tier B selection")
    gene = next((row for row in rows if row["gene"] == "CCNF"), rows[0])
    found = tool.candidates(gene["accession"], tool.cap())
    if len(found) < 2:
        pytest.skip("this accession offers no choice to order")
    lengths = [row["length"] for row in found]
    assert lengths == sorted(lengths, reverse=True)


def test_every_listed_candidate_fits_the_cap_and_is_an_interpro_entry():
    rows = tool.selection()
    if not rows:
        pytest.skip("no frozen Tier B selection")
    limit = tool.cap()
    seen = 0
    for row in rows:
        for candidate in tool.candidates(row["accession"], limit):
            seen += 1
            assert tool.floor() <= candidate["length"] <= limit, candidate
            assert candidate["entry"].startswith("IPR"), (
                f"{candidate['entry']} is a member database signature, which "
                "is the duplicate the form says it collapsed"
            )
    assert seen > 0, "the listing found nothing to judge"


def test_it_names_the_ligases_still_without_a_construct():
    """The form's own refusal, surfaced by the tool rather than restated."""
    from nobble.curate import tier_b_constructs as form
    outstanding = form.missing()
    assert isinstance(outstanding, list)
    # While the form is empty this is all fifteen; once it is filled it is
    # fewer. Either way the tool must read it from the loader and not count
    # for itself.
    source = (ROOT / "tools" / "tier_b_candidates.py").read_text()
    assert "form.missing()" in source
