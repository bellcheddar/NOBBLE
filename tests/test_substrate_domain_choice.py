"""Which domain a substrate is submitted as, and why that was nondeterministic.

`domain_context()` collects every annotation enclosing a degron and
`benchmark_substrate_constructs` submits `domains[0]` when the 15-mer cannot
fold alone. The list arrived in InterPro's response order and was never
sorted, so the construct depended on how the API had ordered its records that
day.

That is the whole of the discrepancy F93 recorded as a curation change: the
library was built when CSNK1A1's first enclosing entry was IPR000719 at 269
residues, and a later resolution put PF00069 at 219 first. The caveat it put
on the published conclusion was correct about the disagreement and wrong
about its cause.

Ordered now, by D-NOB-061: longest domain-level entry, InterPro preferred
over a PFAM member signature, accession last. These tests state what each
term of that key is for, because a sort key is the kind of thing that gets
simplified by someone who cannot see what it was holding (F107).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.curate import interpro, numbering  # noqa: E402
from nobble.curate.peptides import (  # noqa: E402
    benchmark_substrate_constructs, domain_context,
)
from nobble.execute.campaign import latest_or_absent as _newest  # noqa: E402

CSNK1A1 = "P48729"


def _folded_domain_plans() -> list[dict]:
    return [plan for plan in benchmark_substrate_constructs()
            if (plan.get("substrate") or {}).get("mode") == "folded_domain"]


def _degron_windows() -> dict[tuple, tuple]:
    """(gene, e3) -> (start, end) for the curated 15-mer.

    The plan carries no degron coordinates, only the substrate it chose. Two
    of the tests below need the window the choice was made for, and taking it
    from `plan["peptide_start"]` is what made them pass without asserting
    anything: the key does not exist, so every iteration hit `continue`.
    """
    from nobble.curate.peptides import benchmark_peptides

    return {(item.gene, item.e3_hint): (item.start_res, item.end_res)
            for item in benchmark_peptides()
            if item.start_res is not None and item.end_res is not None}


def test_the_chosen_domain_is_the_longest_enclosing_one():
    """The term that decides the construct. Every candidate encloses the
    degron, so the longest is the most complete folding unit."""
    windows = _degron_windows()
    checked = 0
    for plan in _folded_domain_plans():
        substrate = plan["substrate"]
        window = windows.get((plan.get("gene"), plan.get("e3")))
        assert window, f"no curated degron for {plan.get('gene')}"
        context = domain_context(substrate["accession"], *window)
        lengths = [item["length"] for item in context["domains"]]
        assert lengths == sorted(lengths, reverse=True), (plan.get("gene"), lengths)
        assert substrate["length"] == lengths[0], (
            f"{plan.get('gene')} submits {substrate['length']} residues but "
            f"the longest enclosing domain is {lengths[0]}"
        )
        checked += 1
    assert checked == 6, f"checked {checked} plans, expected 6"


def test_the_order_is_deterministic_across_calls():
    """The bug was an unsorted list, so the first thing to hold is that the
    same inputs give the same answer."""
    first = [item["accession"] for item in
             domain_context(CSNK1A1, 33, 47)["domains"]]
    for _ in range(3):
        again = [item["accession"] for item in
                 domain_context(CSNK1A1, 33, 47)["domains"]]
        assert again == first, (first, again)


def test_interpro_wins_a_tie_against_a_pfam_signature(monkeypatch):
    """A PFAM match is one member signature of the InterPro entry that
    integrates it, so where both describe the same extent the integrated
    entry is the one to name, as `constructs.py` does for every receptor.

    No real protein in the panel has an exact interpro/pfam length tie, so
    this builds one. Skipping instead left the second term of the sort key
    unexercised, which is the term most likely to be dropped as redundant.
    """
    tie = [
        {"accession": "PF99999", "name": "Made-up domain", "database": "pfam",
         "type": "domain", "start": 10, "end": 109, "length": 100},
        {"accession": "IPR999999", "name": "Made-up domain", "database": "interpro",
         "type": "domain", "start": 10, "end": 109, "length": 100},
    ]
    monkeypatch.setattr(interpro, "domains", lambda accession: tie)
    chosen = domain_context("P00000", 50, 64)["domains"][0]
    assert chosen["accession"] == "IPR999999", chosen

    # And the other way round, so the result is the rule rather than the
    # order the fixture happened to be written in.
    monkeypatch.setattr(interpro, "domains", lambda accession: list(reversed(tie)))
    assert domain_context("P00000", 50, 64)["domains"][0]["accession"] == "IPR999999"


def test_a_longer_pfam_entry_still_beats_a_shorter_interpro_one(monkeypatch):
    """The first term outranks the second. Preferring InterPro is a
    tie-break, not an override: the construct's job is to fold, and a
    database preference that overrode length would submit the shorter
    fragment."""
    records = [
        {"accession": "IPR111111", "name": "Short", "database": "interpro",
         "type": "domain", "start": 40, "end": 99, "length": 60},
        {"accession": "PF11111", "name": "Long", "database": "pfam",
         "type": "domain", "start": 10, "end": 159, "length": 150},
    ]
    monkeypatch.setattr(interpro, "domains", lambda accession: records)
    chosen = domain_context("P00000", 50, 64)["domains"][0]
    assert chosen["accession"] == "PF11111", chosen
    assert chosen["length"] == 150


def test_csnk1a1_resolves_to_the_integrated_kinase_domain():
    """The case D-NOB-061 turns on. PF00069 gives 17-235 and IPR000719 gives
    17-285 for the same domain name, and the shorter one was what the plan
    had come to specify."""
    chosen = domain_context(CSNK1A1, 33, 47)["domains"][0]
    assert chosen["accession"] == "IPR000719", chosen
    assert (chosen["start"], chosen["end"]) == (17, 285), chosen
    assert chosen["length"] == 269


def test_the_longer_boundary_is_the_one_the_crystal_resolves():
    """Not an appeal to authority between two databases. 5FQD chain C
    resolves 10 to 303 with no unmodelled gaps, so the 50 residues PF00069
    drops are ordered structure. This is the evidence the decision rests on,
    so it is checked rather than quoted."""
    from nobble.curate import structures

    amino = set("ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO "
                "SER THR TRP TYR VAL MSE".split())
    model = structures.read_assembly("5FQD")[0]
    chain = next((c for c in model if c.name == "C"), None)
    if chain is None:
        pytest.skip("5FQD chain C not in the cached assembly")

    numbers = sorted(r.seqid.num for r in chain if r.name in amino)
    assert numbers, "no amino acids in chain C"
    gaps = set(range(numbers[0], numbers[-1] + 1)) - set(numbers)
    assert not gaps, f"{len(gaps)} unmodelled residues inside the span"
    beyond = [n for n in numbers if n > 235]
    assert len(beyond) > 40, (
        f"only {len(beyond)} residues resolved beyond PF00069's end, so the "
        "evidence for the longer boundary would need restating"
    )


def test_no_substrate_construct_comes_from_a_pfam_accession():
    """CSNK1A1 was the only one, and it was the one that disagreed with the
    campaign. `constructs.py` names an InterPro entry for every receptor."""
    sourced = {plan["substrate"]["interpro"] for plan in _folded_domain_plans()}
    pfam = sorted(entry for entry in sourced if not str(entry).startswith("IPR"))
    assert pfam == [], pfam


def test_the_reason_quotes_the_domain_it_names():
    """`max_coverage` belongs to the smallest enclosing domain, which is not
    the one submitted, so the sentence used to pair one domain's accession
    with another's percentage."""
    windows = _degron_windows()
    checked = 0
    for plan in _folded_domain_plans():
        substrate = plan["substrate"]
        reason = substrate["reason"]
        assert substrate["interpro"] in reason, reason
        window = windows.get((plan.get("gene"), plan.get("e3")))
        assert window, f"no curated degron for {plan.get('gene')}"
        length = window[1] - window[0] + 1
        expected = f"{length / substrate['length']:.0%}"
        assert expected in reason, (plan.get("gene"), reason, expected)
        checked += 1
    assert checked == 6, f"checked {checked} plans, expected 6"


def test_the_verdict_still_uses_the_smallest_enclosing_domain():
    """Deliberately not reordered with the construct choice. "Can this window
    fold alone" is answered most conservatively by the domain it fills most
    of: a 23-residue zinc finger covering all of a 23-residue annotation is
    self-sufficient however many larger domains contain it."""
    context = domain_context(CSNK1A1, 33, 47)
    coverages = [item["coverage"] for item in context["domains"]]
    assert context["max_coverage"] == max(coverages), (
        context["max_coverage"], coverages
    )
    assert context["max_coverage"] > context["domains"][0]["coverage"], (
        "the chosen domain is no longer the longest, or the maximum is no "
        "longer taken over all of them"
    )


def test_the_plan_matches_what_the_corrected_campaign_submitted():
    """End to end, and the point of the whole fix: the plan and the campaign
    agree about CSNK1A1 again, so there is nothing left to caveat."""
    from nobble.validate import inputs

    corrected = _newest("corrected")
    if not (corrected / "yaml").exists():
        pytest.skip("no corrected campaign on this checkout")

    planned = numbering.canonical_sequence(CSNK1A1)
    chosen = domain_context(CSNK1A1, 33, 47)["domains"][0]
    expected = planned[chosen["start"] - 1:chosen["end"]]

    for path in sorted((corrected / "yaml").glob("*CSNK1A1*ternary*.yaml")):
        submitted = inputs.substrate_sequence(path.read_text())
        assert submitted == expected, (
            path.name, len(submitted or ""), len(expected)
        )
        break
    else:
        pytest.skip("no CSNK1A1 ternary YAML")


# --------------------------------------------------------------------------- #
# The same defect on the receptor side.
# --------------------------------------------------------------------------- #

def test_an_occurrence_is_counted_from_the_n_terminus(monkeypatch):
    """`domain_by_accession` promises N-terminal counting and indexed the
    response list, so F41's fix replaced "whichever InterPro listed first"
    with "whichever InterPro listed Nth" and kept the failure mode.

    Response order and N-terminal order agree for FEM1B today, so the only
    way to test the contract is to disagree with it deliberately.
    """
    reversed_response = [
        {"accession": "IPR036770", "name": "Ankyrin repeat-containing",
         "database": "interpro", "type": "homologous_superfamily",
         "start": 424, "end": 610, "length": 187},
        {"accession": "IPR036770", "name": "Ankyrin repeat-containing",
         "database": "interpro", "type": "homologous_superfamily",
         "start": 5, "end": 301, "length": 297},
    ]
    monkeypatch.setattr(interpro, "domains", lambda accession: reversed_response)

    first = interpro.domain_by_accession("Q9UK73", "IPR036770", 0)
    assert (first["start"], first["end"]) == (5, 301), (
        f"occurrence 0 gave {first['start']}-{first['end']}: the response "
        "order was followed rather than the N-terminus"
    )
    second = interpro.domain_by_accession("Q9UK73", "IPR036770", 1)
    assert (second["start"], second["end"]) == (424, 610), second


def test_the_fem1b_receptor_construct_is_the_n_terminal_ankyrin_region():
    """The construct that depends on it. FEM1B_ANK declares occurrence 0 and
    spec 1.1's substrate-binding region is the N-terminal one."""
    from nobble.curate import constructs

    segment = constructs.CONSTRUCTS["FEM1B_ANK"].segments[0]
    start, end = segment.range()
    assert (start, end) == (5, 301), (
        f"FEM1B_ANK resolves to {start}-{end}, not the N-terminal 5-301"
    )


def test_an_unambiguous_entry_is_unaffected():
    """One annotation needs no ordering, and the sort must not change what a
    single match returns."""
    record = interpro.domain_by_accession("P48729", "IPR000719")
    assert (record["start"], record["end"]) == (17, 285), record


def test_an_ambiguous_entry_with_no_occurrence_still_refuses():
    """F41's other half. Sorting makes the index meaningful; it does not
    make guessing acceptable."""
    with pytest.raises(interpro.AmbiguousEntry):
        interpro.domain_by_accession("Q9UK73", "IPR036770")


def test_which_constructs_any_campaign_actually_submits():
    """Recorded because F108 got this wrong in writing.

    `interpro_occurrence` exists for one construct, `FEM1B_ANK`, and the
    severity of a defect in it depends on whether anything submits that
    construct. Nothing does: the benchmark E3s are CRBN, DCAF15, DDB1 and
    VHL, and `FEM1B_ANK` and `KEAP1_KELCH` are declared, budgeted and tested
    without appearing in any queue.

    Pinned rather than left as prose, so a campaign that starts using either
    one changes the reading of F108 here instead of in a sentence nobody
    rechecks.
    """
    import json

    from nobble.curate import constructs as C
    from nobble.curate import peptides as P

    assert {member["e3"] for member in P.BENCHMARK_CHAINS} == {
        "CRBN", "DCAF15", "DDB1", "VHL"}

    occurrence_users = {
        name for name, construct in C.CONSTRUCTS.items()
        if any(segment.interpro_occurrence is not None
               for segment in construct.segments)
    }
    assert occurrence_users == {"FEM1B_ANK"}, occurrence_users

    submitted = set()
    for campaign in sorted((ROOT / "campaigns").glob("*/queue.jsonl")):
        for line in campaign.read_text().splitlines():
            if line.strip():
                name = json.loads(line).get("construct")
                if name:
                    submitted.add(name)
    if not submitted:
        pytest.skip("no assembled queue on this checkout")
    assert not (occurrence_users & submitted), (
        f"{sorted(occurrence_users & submitted)} is submitted now, so F108's "
        "blast radius is no longer nothing"
    )
