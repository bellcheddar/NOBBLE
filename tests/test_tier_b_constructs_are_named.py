"""The fifteen Tier B ligases, answered: eleven named and four excluded.

Spec 3.3 selects fifteen Tier B ligases and names no receptor construct for
any of them, so the arm was selected, frozen, gate-passed and unrunnable.
F163 built the form; this is the form filled in, from Marc's answers on
2026-11-05 against the candidate evidence. D-NOB-072 records what was
offered and declined for each.

Four cannot have a construct, which the form could not previously express.
`missing()` returned every uncovered gene, so dropping one left Tier B
permanently unassemblable. Exclusions now carry a required reason, because
without one the table would be a way to make the gate pass by deleting the
genes that fail it.

The occurrence indices are the part worth testing hardest. Three constructs
name an InterPro entry that is annotated more than once, and `occurrence` is
counted from the N-terminus rather than in the order the shortlist printed.
The shortlist is ordered by length, so taking its index would have given
FBXW4 the wrong half of its propeller and SMURF2 a WW domain modelled in
disorder. That is F41 and F107 exactly, and the residue counts below are
what catch it.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402
from nobble.curate import constructs as C  # noqa: E402
from nobble.curate import tier_b_constructs as T  # noqa: E402

# Gene, construct name, and the residue count the choice implies. The count
# is the assertion: it only comes out right if the accession, the InterPro
# entry and the occurrence are all correct.
EXPECTED = {
    "ASB8": ("ASB8_ANKYRIN", 207),
    "CCNF": ("CCNF_CYCLIN_N", 116),
    "DCAF8L1": ("DCAF8L1_WD40", 326),
    "FBXO11": ("FBXO11_BETA_HELIX", 156),
    "FBXW4": ("FBXW4_WD40", 133),
    "KCTD4": ("KCTD4_C_TERMINAL", 122),
    "NEURL2": ("NEURL2_NHR", 218),
    "SMURF2": ("SMURF2_WW", 41),
    "TRIM17": ("TRIM17_SPRY", 199),
    "TRIM55": ("TRIM55_SPRY", 183),
    "TRIP12": ("TRIP12_WWE", 76),
}
EXCLUDED = {"KCNC1", "KCND2", "RAG1", "RNF175"}


def test_every_tier_b_gene_is_either_named_or_excluded():
    report = T.report()
    assert report["genes_without_a_construct"] == [], report
    assert report["status"] == "ready", report["status"]
    assert report["assemblable"] is True, report


def test_the_constructs_are_the_ones_that_were_chosen():
    defined = T.load()
    assert set(defined) == {name for name, _ in EXPECTED.values()}, sorted(defined)
    for gene, (name, residues) in sorted(EXPECTED.items()):
        construct = defined[name]
        assert construct.e3_gene == gene, (name, construct.e3_gene)
        assert construct.residue_count() == residues, (
            f"{name} resolves to {construct.residue_count()} residues, not "
            f"{residues}: the accession, the InterPro entry or the occurrence "
            "is wrong"
        )


def test_the_ambiguous_entries_resolve_from_the_n_terminus():
    """The three that name a multiply-annotated entry. Indexing the
    shortlist instead, which is ordered by length, would give FBXW4 266-412
    rather than 133-265 and SMURF2 245-286 rather than 291-331."""
    from nobble.curate import interpro

    for name, entry, occurrence, residues in (
        ("FBXO11_BETA_HELIX", "IPR039448", 0, 156),
        ("FBXW4_WD40", "IPR015943", 0, 133),
        ("SMURF2_WW", "IPR036020", 2, 41),
    ):
        construct = T.load()[name]
        segment = construct.segments[0]
        assert segment.interpro_entry == entry, name
        assert segment.interpro_occurrence == occurrence, name
        domain = interpro.domain_by_accession(
            segment.accession, entry, occurrence)
        span = int(domain["end"]) - int(domain["start"]) + 1
        assert span == residues, (name, domain["start"], domain["end"])


def test_every_exclusion_carries_a_reason():
    excluded = T.exclusions()
    assert set(excluded) == EXCLUDED, sorted(excluded)
    for gene, reason in sorted(excluded.items()):
        assert len(reason) > 40, (gene, reason)
        assert "offered and declined" in reason or "declined" in reason, (
            f"{gene}'s exclusion does not say what was offered instead, so a "
            "reader cannot tell a judgement from an oversight"
        )


def test_an_exclusion_without_a_reason_is_a_problem_not_a_pass(monkeypatch):
    """The property that stops this table being a way to delete the genes
    that fail the gate."""
    monkeypatch.setattr(T, "exclusions", lambda: {"KCNC1": "", "KCND2": "x" * 50,
                                                  "RAG1": "y" * 50, "RNF175": "z" * 50})
    report = T.report()
    assert any(p.get("exclusion") == "KCNC1" for p in report["problems"]), report
    assert report["assemblable"] is False


def test_the_arm_clears_the_configured_ligase_floor():
    floor = int(paths.thresholds()["tier_b"]["min_ligases_for_gate"])
    assert len(T.load()) >= floor, (
        f"{len(T.load())} constructs against spec 3.3's floor of {floor}"
    )
    assert T.report()["ligase_floor"] == floor


def test_falling_below_the_floor_is_reported(monkeypatch):
    """Red-green on the floor check, which exists because excluding genes
    shrinks the arm and a short arm answers a narrower question."""
    kept = dict(list(T.load().items())[:3])
    monkeypatch.setattr(T, "load", lambda: kept)
    monkeypatch.setattr(T, "missing", lambda: [])
    report = T.report()
    assert any("floor" in str(p.get("problem", "")) for p in report["problems"]), report
    assert report["assemblable"] is False


def test_one_lookup_reaches_both_tiers():
    """Recorded and unreachable was the state before this: campaign.py
    indexed the Tier A dict directly."""
    for name in ("CRBN_CULT", "VHL_VCB"):
        assert C.by_name(name).e3_gene
    for name, _ in EXPECTED.values():
        assert C.by_name(name).e3_gene
    try:
        C.by_name("NO_SUCH_CONSTRUCT")
    except KeyError as problem:
        assert "tier_b_constructs.toml" in str(problem), problem
    else:
        raise AssertionError("an unknown construct name did not raise")


def test_the_two_registries_do_not_collide():
    """by_name lets Tier A win a clash rather than checking there is none,
    so the check lives here."""
    overlap = set(C.CONSTRUCTS) & set(T.load())
    assert not overlap, overlap


def test_the_campaign_assembler_uses_the_shared_lookup():
    source = (ROOT / "nobble" / "execute" / "campaign.py").read_text()
    assert "C.CONSTRUCTS[construct_name]" not in source, (
        "the assembler indexes the Tier A dict again, so a Tier B receptor "
        "would raise KeyError"
    )
    assert "C.by_name(construct_name)" in source
