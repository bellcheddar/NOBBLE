"""Tier A and Tier B receptor selection (spec 3.2 and 3.3).

Tier A is the chemically validated repertoire: the ligases that already have
chemical matter, which is what makes them a calibration set.

Tier B is the discovery arm, and it is in the first campaign rather than
deferred (D-NOB-002). Its selection function is applied to BINMAN's E3 Triage
and frozen to disk at build time so a campaign is reproducible against a fixed
ranking even after BINMAN's triage is re-run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from nobble import paths
from nobble.curate import binman_store as store
from nobble.curate import plddt

# Spec 3.2 names these twelve. cIAP1 is BIRC2 in gene-symbol terms.
TIER_A_NAMED = (
    "CRBN", "VHL", "DCAF15", "DCAF16", "KEAP1", "MDM2",
    "BIRC2", "XIAP", "FEM1B", "DCAF11", "RNF114", "DDB1",
)

VALIDATED = ("chemically validated", "clinically validated")


@dataclass
class Candidate:
    uniprot_acc: str
    gene: str
    family: str
    exploitation_status: str
    pocket_score: float | None
    triage_score: float | None
    triage_rank: int | None
    tumour_enriched: int | None
    expression_breadth: int | None
    best_structure: str | None
    pdb_entries: int | None
    plddt: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        record = {
            key: getattr(self, key)
            for key in (
                "uniprot_acc", "gene", "family", "exploitation_status", "pocket_score",
                "triage_score", "triage_rank", "tumour_enriched", "expression_breadth",
                "best_structure", "pdb_entries",
            )
        }
        record["mean_plddt"] = self.plddt.get("mean_plddt")
        record["best_window_mean_plddt"] = self.plddt.get("best_window_mean_plddt")
        record["best_window"] = self.plddt.get("best_window")
        record["plddt_status"] = self.plddt.get("status")
        record["reasons"] = list(self.reasons)
        return record


def _candidates(where: str, parameters: tuple = ()) -> list[Candidate]:
    rows = store.atlas_rows(
        "select uniprot_acc, gene, family, exploitation_status, pocket_score, "
        "       triage_score, triage_rank, tumour_enriched, expression_breadth, "
        "       best_structure, pdb_entries "
        f"from ligase where status = 'ok' and {where}",
        parameters,
    )
    return [Candidate(**row) for row in rows]


def tier_a() -> dict:
    """Tier A: the validated repertoire, plus any spec-named ligase BINMAN lacks.

    Spec 3.2 filters BINMAN's triage to the validated status and then names twelve
    ligases. Those two definitions do not quite agree: the validated set holds 17
    ligases, and two of the twelve named (FEM1B and DDB1) are absent from BINMAN's
    triage table altogether. Both are carried anyway, because the spec names them
    and spec 1.1 gives both a token budget and a receptor construct, so excluding
    them would drop receptors the spec treats as tier-1 eligible.
    """
    selected = _candidates("exploitation_status in (?, ?)", VALIDATED)
    for candidate in selected:
        candidate.plddt = plddt.summary(candidate.uniprot_acc)
        candidate.reasons.append(f"validated: {candidate.exploitation_status}")
        if candidate.gene in TIER_A_NAMED:
            candidate.reasons.append("named in spec 3.2")

    present = {candidate.gene for candidate in selected}
    missing = [gene for gene in TIER_A_NAMED if gene not in present]

    return {
        "selected": [candidate.to_dict() for candidate in
                     sorted(selected, key=lambda item: item.triage_rank or 10**6)],
        "count": len(selected),
        "named_in_spec": list(TIER_A_NAMED),
        "named_but_absent_from_binman_triage": missing,
        "note": (
            "FEM1B and DDB1 are named by spec 3.2 but carry no row in BINMAN's E3 "
            "Triage. Both have receptor constructs and token budgets in spec 1.1, "
            "so they are campaign members without a triage score rather than "
            "exclusions."
        ) if missing else "",
    }


def tier_b() -> dict:
    """Tier B: ligandable but unproven, by the spec 3.3 selection function.

    Each filter is applied in the stated order and every rejection is counted, so
    the funnel is auditable rather than a single surviving list.
    """
    limits = paths.thresholds()["tier_b"]
    pocket_min = float(limits["pocket_druggability_min"])
    plddt_min = float(limits["mean_plddt_min"])
    take = int(limits["take_top"])

    pool = _candidates("exploitation_status = ?", ("ligandable unproven",))
    funnel = {"ligandable_unproven": len(pool)}

    # Filter 2: fpocket druggability.
    stage = [item for item in pool if (item.pocket_score or 0.0) >= pocket_min]
    funnel[f"pocket_score_ge_{pocket_min}"] = len(stage)

    # Filter 4's reference value is the median over the whole repertoire, so it is
    # computed before any filtering narrows the distribution.
    #
    # It is also inoperative against this store, and that has to be established
    # rather than assumed: `tumour_enriched` is 0 for all 650 rows in BINMAN's
    # ligase table, so the column carries no variance and "above the median"
    # selects nothing at all. Applied literally the funnel collapses to zero
    # candidates, which would fail the Phase 1 gate on a column that was never
    # populated. The three ligases spec 3.3 itself expects to see at the top of
    # this ranking (DCAF8L1, CCNF and ASB8, triage ranks 2, 3 and 4) are all 0
    # on it too, which settles the question: the filter is unpopulated, not
    # discriminating. So it is skipped and the skip is recorded, exactly as the
    # ProtCID veto is in D-NOB-010. Nothing is reported as enriched or not
    # enriched. See D-NOB-017.
    enrichment = [
        item.tumour_enriched for item in pool if item.tumour_enriched is not None
    ]
    enrichment_median = median(enrichment) if enrichment else 0
    distinct_enrichment = {value for value in enrichment}
    enrichment_usable = len(distinct_enrichment) > 1
    funnel["tumour_enrichment_median"] = enrichment_median
    funnel["tumour_enrichment_distinct_values"] = len(distinct_enrichment)
    funnel["tumour_enrichment_filter_applied"] = enrichment_usable

    # Filter 3: structural coverage with a well-ordered domain.
    for item in stage:
        item.plddt = plddt.summary(item.uniprot_acc)
    stage = [
        item for item in stage
        if (item.plddt.get("best_window_mean_plddt") or 0.0) >= plddt_min
    ]
    funnel[f"best_window_plddt_ge_{plddt_min}"] = len(stage)

    # Filter 4: tumour enrichment above the repertoire median, where usable.
    if enrichment_usable:
        stage = [
            item for item in stage
            if (item.tumour_enriched or 0) > enrichment_median
        ]
        funnel["tumour_enriched_above_median"] = len(stage)
    else:
        funnel["tumour_enriched_above_median"] = "not_computed: column unpopulated"

    # Rank by the existing E3 Triage composite, highest first.
    ranked = sorted(
        stage,
        key=lambda item: (-(item.triage_score or 0.0), item.triage_rank or 10**6),
    )
    for position, item in enumerate(ranked, start=1):
        item.reasons = [
            f"pocket_score {item.pocket_score}",
            f"best-window pLDDT {item.plddt.get('best_window_mean_plddt')}",
            (f"tumour_enriched {item.tumour_enriched}" if enrichment_usable
             else "tumour enrichment not computed: Open Targets column unpopulated"),
            f"triage_score {item.triage_score}",
            f"tier B rank {position}",
        ]

    selected = ranked[:take]
    expected = {"DCAF8L1", "CCNF", "ASB8"}
    chosen_genes = {item.gene for item in selected}

    return {
        "selected": [item.to_dict() for item in selected],
        "count": len(selected),
        "funnel": funnel,
        "tumour_enrichment_status": (
            "applied" if enrichment_usable
            else "not_computed: open_targets_enrichment_unpopulated"
        ),
        "candidates_after_filters": len(ranked),
        "spec_expected_members": sorted(expected),
        "spec_expected_present": sorted(expected & chosen_genes),
        "spec_expected_absent": sorted(expected - chosen_genes),
        "passes_gate": len(selected) >= int(limits["min_ligases_for_gate"]),
    }
