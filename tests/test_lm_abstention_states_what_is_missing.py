"""Head C has to say what is missing, not what is present (F141).

Spec 5: "Head C abstains when the campaign has not run the pair in question
and states what is missing."

`Answer.missing` was being set from `_named_pairs`, which scanned the
question for tokens that looked like gene names, intersected them with the
campaign's own values, and returned the intersection: the names the campaign
*does* hold. A question about BRD4 and VHL against a campaign holding both
was answered "missing: BRD4, VHL". The field is serialised to the browser by
`/api/ask`, and no page renders it, which is why nobody saw it.

The function's own signature said it returned names "split into present and
absent" and the absent half was `[]` on every path, with the reasoning for
the half that was never written sitting in a comment above the return.

It is now derived from the query's filters, which needs no rule for what a
gene name looks like. The old one's rule was "three characters or more", so
"the" and "and" were candidates for being gene names.
"""
from __future__ import annotations

from nobble.app import lm

ROWS = [
    {"pair_id": "a", "e3_gene": "VHL", "peptide_gene": "BRD4", "delta_iptm": -0.1},
    {"pair_id": "b", "e3_gene": "CRBN", "peptide_gene": "IKZF1", "delta_iptm": 0.2},
]


def test_a_filter_the_campaign_cannot_satisfy_is_named():
    query = {"filter": [["e3_gene", "eq", "KEAP1"]]}
    assert lm.unmatched(query, ROWS) == ["e3_gene eq 'KEAP1'"]


def test_a_threshold_nothing_reaches_is_named():
    query = {"filter": [["delta_iptm", "gt", 0.9]]}
    assert lm.unmatched(query, ROWS) == ["delta_iptm gt 0.9"]


def test_present_parts_with_an_absent_combination_say_so():
    """The case the old code got exactly backwards.

    Both genes are in the campaign and no pair has both. "Missing: VHL,
    IKZF1" is false about the campaign; what is missing is the pair.
    """
    query = {"filter": [["e3_gene", "eq", "VHL"],
                        ["peptide_gene", "eq", "IKZF1"]]}
    missing = lm.unmatched(query, ROWS)
    assert len(missing) == 1
    assert "though each holds on its own" in missing[0]
    assert "VHL" in missing[0] and "IKZF1" in missing[0]


def test_nothing_is_missing_when_the_query_matches():
    query = {"filter": [["e3_gene", "eq", "VHL"]]}
    assert lm.unmatched(query, ROWS) == []


def test_a_query_with_no_filter_claims_nothing():
    """An unfiltered query that returns nothing means an empty campaign, and
    `ask` has already abstained for that reason further up."""
    assert lm.unmatched({}, ROWS) == []
    assert lm.unmatched({"sort": ["delta_iptm", "desc"]}, ROWS) == []


def test_it_never_reports_a_value_the_campaign_holds():
    """The defect as a property rather than as a case.

    Every string in `missing` describes a filter that matched nothing. So no
    entry may consist solely of a value the campaign has, which is what the
    old output was made of.
    """
    held = {str(row[key]) for row in ROWS
            for key in ("e3_gene", "peptide_gene") if row.get(key)}
    for query in (
        {"filter": [["e3_gene", "eq", "VHL"], ["peptide_gene", "eq", "IKZF1"]]},
        {"filter": [["e3_gene", "eq", "KEAP1"]]},
    ):
        for entry in lm.unmatched(query, ROWS):
            assert entry not in held, (
                f"{entry!r} is a value the campaign holds, reported as missing"
            )


def test_ask_uses_it_and_the_old_guesser_is_gone():
    import inspect

    source = inspect.getsource(lm)
    assert "_named_pairs" not in source, (
        "the token guesser is still present, so a future caller can reach it"
    )
    assert "answer.missing = unmatched(" in source


def test_the_field_reaches_the_api_response():
    """It is published whether or not a page renders it.

    `/api/ask` returns `asdict`, so a wrong value here is wrong on the wire.
    That is how this survived: no template reads `missing`, so the only
    reader was a client nobody had written yet.
    """
    answer = lm.Answer(status="abstained", question="q")
    assert "missing" in answer.to_dict()
