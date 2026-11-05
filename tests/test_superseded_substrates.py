"""A campaign's substrate domain against the one the plan now specifies.

The corrected campaign exists to test one claim: that a folded domain
recovers the pose better than a 15-mer fragment. Its substrate boundaries
come from an InterPro lookup, so a fix to how an ambiguous entry is resolved
moves them, and nothing recorded which domain each job actually used.

One had moved, and the reason turned out to be a defect rather than a
curation change. `corr05_CSNK1A1_CRBN` submitted 269 residues and the plan
came to specify 219, P48729 17-235. The plan's domain was
`domain_context()["domains"][0]`, the first entry of a list in InterPro's
response order, so which boundary the plan gave depended on how the API had
sorted its records that day. The list is ordered now, longest domain-level
entry first with InterPro preferred over a PFAM member signature, and
CSNK1A1 resolves to IPR000719 17-285, which is the 269 residues the campaign
ran (F107).

So there is no superseded substrate to find any more. These tests keep the
detector covered on a synthetic case, because an absent instance must not
quietly become an absent test.

`stale_inputs` cannot see this. It compares a YAML against the queue row
beside it and both were written by one assembly, so they agree about a
boundary that has since moved. This compares the YAML against the plan
(F93).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.validate import inputs  # noqa: E402
from nobble.execute.campaign import latest_or_absent as _newest  # noqa: E402

CORRECTED = _newest("corrected")


def test_the_substrate_is_found_by_chain_id_not_by_length():
    """The receptor is usually the longest chain, so taking the longest
    sequence reads the receptor for most pairs. That mistake made five of
    seven look as though no current domain matched them."""
    yaml_text = (
        "sequences:\n"
        "- protein:\n"
        "    id: A\n"
        "    sequence: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"
        "- protein:\n"
        "    id: P\n"
        "    sequence: PPPPPPPPPP\n"
        "- ligand:\n"
        "    id: L\n"
        "    ccd: Y70\n"
    )
    assert inputs.substrate_sequence(yaml_text) == "PPPPPPPPPP"


def test_a_yaml_with_no_substrate_chain_returns_nothing():
    assert inputs.substrate_sequence("sequences:\n- protein:\n    id: A\n"
                                     "    sequence: AAAA\n") is None


def test_no_campaign_has_a_superseded_substrate_any_more():
    """This asserted exactly one, `corr05_CSNK1A1_CRBN` at 269 against a
    planned 219. The plan was the thing that was wrong: its boundary came
    from an unordered list and moved with InterPro's response order. With the
    list ordered, the plan gives IPR000719 17-285, the 269 residues the
    campaign ran, and the discrepancy is gone rather than caveated (F107)."""
    if not CORRECTED.exists():
        pytest.skip("no corrected campaign on this checkout")
    assert inputs.superseded_substrates(CORRECTED) == [], (
        "a superseded substrate is back: either the ordering regressed or a "
        "boundary genuinely moved, and the two need telling apart"
    )


def test_the_detector_still_reports_a_genuinely_superseded_substrate(monkeypatch):
    """The instance is gone; the machinery must not be.

    Replayed rather than mocked up: the plan is put back to the boundary it
    gave before the ordering fix, PF00069 17-235, against the corrected
    campaign's real YAMLs. That is exactly the case F93 found, so if the
    detector stops seeing it the loss is visible here rather than in a
    campaign a year from now.
    """
    if not CORRECTED.exists():
        pytest.skip("no corrected campaign on this checkout")

    from nobble.curate import peptides as peptide_module

    honest = peptide_module.benchmark_substrate_constructs

    def with_the_old_boundary():
        plans = honest()
        for plan in plans:
            substrate = plan.get("substrate") or {}
            if substrate.get("accession") == "P48729":
                substrate["interpro"] = "PF00069"
                substrate["start"], substrate["end"] = 17, 235
                substrate["length"] = 219
        return plans

    monkeypatch.setattr(
        peptide_module, "benchmark_substrate_constructs", with_the_old_boundary)
    rows = inputs.superseded_substrates(CORRECTED)

    assert [row["pair_id"] for row in rows] == ["corr05_CSNK1A1_CRBN"], rows
    (row,) = rows
    assert row["submitted_length"] == 269
    assert row["planned_length"] == 219
    assert row["accession"] == "P48729"
    assert row["planned_range"] == "17-235"


def test_the_fix_is_what_removed_it_and_not_a_blinded_detector():
    """The two look identical from the outside: no rows reported. The
    difference is whether the plan now agrees with the campaign, so this
    checks the agreement directly rather than the absence of a complaint."""
    if not CORRECTED.exists():
        pytest.skip("no corrected campaign on this checkout")

    from nobble.curate import numbering
    from nobble.curate import peptides as peptide_module

    planned = {}
    for plan in peptide_module.benchmark_substrate_constructs():
        substrate = plan.get("substrate") or {}
        if substrate.get("mode") != "folded_domain":
            continue
        planned[substrate["accession"]] = numbering.canonical_sequence(
            substrate["accession"])[substrate["start"] - 1:substrate["end"]]

    csnk = planned.get("P48729")
    assert csnk and len(csnk) == 269, (
        f"the plan gives CSNK1A1 {len(csnk) if csnk else 0} residues, not 269"
    )

    submitted = None
    for path in sorted((CORRECTED / "yaml").glob("*CSNK1A1*ternary*.yaml")):
        submitted = inputs.substrate_sequence(path.read_text())
        break
    assert submitted == csnk, (
        "the corrected campaign's CSNK1A1 chain P is not the sequence the "
        "plan now specifies"
    )


def test_the_other_campaigns_have_none():
    """The benchmark panel submits 15-mers, and the main campaign was
    assembled from the same lookup, so a finding in either would mean
    something different again."""
    from nobble.execute.campaign import latest

    for campaign in (latest("benchmark"), latest("campaign")):
        if campaign is None:
            continue
        assert inputs.superseded_substrates(campaign) == [], campaign.name


def test_a_fifteen_mer_substrate_is_not_reported():
    """IKZF1 keeps its 15-mer in both campaigns deliberately, as the
    control that nothing else changed. Reporting it as superseded would
    bury the one real case in a false one."""
    if not CORRECTED.exists():
        pytest.skip("no corrected campaign on this checkout")
    rows = inputs.superseded_substrates(CORRECTED)
    assert not any("IKZF1" in row["pair_id"] for row in rows), rows


def test_the_conclusion_no_longer_carries_the_superseded_caveat():
    """The caveat was correct while the plan disagreed with the campaign.
    The plan was what was wrong, so the right outcome is the caveat going
    away rather than being reworded: CSNK1A1 is in the published `improved`
    list, 12.24 angstrom to 6.189, and that measurement now has the plan
    beside it agreeing (F107)."""
    from nobble.validate import compare

    baseline = _newest("benchmark")
    if not (baseline.exists() and CORRECTED.exists()):
        pytest.skip("both campaigns are needed")
    report = compare.run(baseline, CORRECTED)
    assert not report["superseded_substrates"], report["superseded_substrates"]
    assert "no longer specifies" not in report["conclusion"], report["conclusion"]


def test_the_conclusion_would_still_carry_it_if_one_appeared():
    """The wiring, not the instance. A caveat that has nothing to report is
    indistinguishable from a caveat that cannot report, which is the F96 and
    F105 failure, so the branch that writes it is checked directly."""
    source = (ROOT / "nobble" / "validate" / "compare.py").read_text()
    # Matched on a fragment that sits inside one literal. The sentence is
    # built from two adjacent f-strings, "...the plan no " and "longer
    # specifies (...)", so a grep for the whole phrase finds nothing even
    # when the branch is there.
    assert "longer specifies (" in source, (
        "the superseded-substrate caveat has been removed from compare.py "
        "rather than merely having nothing to say"
    )
    assert "the measurement stands" in source


def test_a_corrected_campaign_records_the_plan_it_ran_under():
    """The preventive half of F93. A campaign that records only its job
    count cannot be checked against the plan it used, which is how a
    boundary moved 50 residues with nothing noticing (F94)."""
    from nobble.execute import corrected

    plans = corrected._substrate_plans()
    assert plans, "the substrate plan is empty, so nothing would be recorded"
    recorded = [
        {"gene": plan.get("gene"),
         "interpro": (plan.get("substrate") or {}).get("interpro"),
         "start": (plan.get("substrate") or {}).get("start"),
         "end": (plan.get("substrate") or {}).get("end")}
        for plan in plans
    ]
    assert all(row["gene"] for row in recorded), (
        "a recorded entry has no gene, so the keys are guessed rather than "
        f"read: {recorded[:2]}"
    )
    assert any(row["interpro"] for row in recorded)


def test_the_recorded_plan_names_the_entry_the_boundary_came_from():
    """The InterPro or PFAM entry is the thing that moves, so recording the
    range without it would leave the next reader unable to tell whether a
    boundary changed or a different entry was chosen."""
    from nobble.execute import corrected

    folded = [plan for plan in corrected._substrate_plans()
              if (plan.get("substrate") or {}).get("mode") == "folded_domain"]
    assert folded
    assert all((plan.get("substrate") or {}).get("interpro")
               for plan in folded), folded


def test_the_superseded_domain_is_the_one_sourced_differently():
    """Recorded as a signal rather than a cause. Five folded domains
    resolve from an InterPro entry and CSNK1A1 from a PFAM accession, and
    CSNK1A1 is the one whose boundary moved. That does not prove the
    sourcing is why, and it is where someone resolving which boundary is
    correct should start."""
    from nobble.execute import corrected

    by_gene = {}
    for plan in corrected._substrate_plans():
        substrate = plan.get("substrate") or {}
        if substrate.get("mode") == "folded_domain":
            by_gene[plan["gene"]] = str(substrate.get("interpro") or "")

    pfam = sorted(gene for gene, entry in by_gene.items()
                  if entry.startswith("PF"))
    interpro = sorted(gene for gene, entry in by_gene.items()
                      if entry.startswith("IPR"))
    assert interpro, by_gene
    assert pfam == [], (
        f"a substrate domain resolves from a PFAM accession again: {pfam}. "
        "CSNK1A1 was the only one, and it was the one whose boundary "
        "disagreed with the campaign: a PFAM match is one member signature "
        "of an InterPro entry and clips the fold where its HMM alignment "
        "ends. For CSNK1A1 that cost 50 residues the crystal resolves "
        "(F107). constructs.py names an InterPro entry for every receptor "
        "and substrates now do the same"
    )
