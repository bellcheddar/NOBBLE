"""Confidence aggregation: Delta-ipTM, convergence and ipTM-min (spec 4.3 to 4.5).

The headline number is

    delta_iptm = iptm_min_ternary - iptm_min_binary

taking the **minimum** across the five seeds in each condition rather than the
mean, per spec 4.3. The minimum is the right statistic for a claim about whether
an interface forms at all: a mean lets one confident seed carry four
unconvinced ones.

Which ipTM, though, matters more than the spec says. Boltz reports a global
`iptm` over all chain pairs, and a `pair_chains_iptm` matrix per pair. For a
ternary complex the global figure mixes the receptor-peptide interface with the
receptor-ligand and peptide-ligand ones, so a glue that binds its pocket
beautifully while the peptide drifts can raise the global ipTM without the
degron interface existing at all. NOBBLE therefore reads the
**receptor-to-peptide pair** specifically, and reports the global value beside
it as a separate column. See D-NOB-022.

Chain order is fixed by the YAML generator: receptor segments first in construct
order, then the peptide, then the ligand. So the peptide's chain index is the
segment count, which is read from the construct rather than assumed.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from nobble.curate import constructs as C
from nobble import paths
from nobble.numeric import finite, finite_values

COLLAPSE_MINIMUM_SEEDS = int(paths.thresholds()["scoring"]["collapse_minimum_seeds"])

MISSING = None


@dataclass
class SeedRecord:
    """One inference: the confidence numbers for a single seed."""

    job_id: str
    seed: int
    complex_type: str
    conditioning: str
    iptm_global: float | None
    iptm_receptor_peptide: float | None
    ptm: float | None
    complex_plddt: float | None
    # Boltz's own field, carried through unchanged and read by nothing. The
    # name is Boltz's and it means "whichever het group was in the job", not
    # "the glue". On a Sievers pair it is the structural zinc: measured on
    # sv_neg_ZN346_d5063d__binary__unconstrained__seed1, `ligand_iptm` is
    # 0.9946, which is exactly the zinc's row in `pair_chains_iptm`, and that
    # job has no glue in it at all because it is the binary arm. Across the
    # 120-pair Sievers arm it would describe the finger holding itself
    # together, on both arms, which is the same mistake F14 found in the
    # geometry consumers and F81 in PLIP: every consumer classifies chains
    # itself, and "not receptor, not peptide, not the cofactor" is only
    # correct where that branch exists. Here it does not, so the field is
    # kept as a record of what Boltz reported and not used as a measurement.
    # `tests/test_ligand_iptm_is_not_the_glue.py` fails if anything starts
    # reading it (F102).
    ligand_iptm: float | None
    confidence_score: float | None
    affinity_pred_value: float | None
    structure: str | None
    # Which chains the receptor-peptide ipTM was taken over, and what the
    # previous definition (chain 0 alone) gave, so the change is auditable
    # from the record rather than only from the commit (D-NOB-044).
    iptm_receptor_chains: list = field(default_factory=list)
    iptm_receptor_peptide_first_chain_only: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PairMetrics:
    """Aggregated confidence for one (receptor, peptide, ligand) triple."""

    pair_id: str
    construct: str
    e3_gene: str
    peptide_id: str
    peptide_gene: str | None
    peptide_label: str | None
    ligand_key: str | None
    modality: str
    tier: str
    # Design-arm linkage (DESIGN_ARM.md). Carried through scoring because
    # design lift is computed from scores.jsonl, and a variant that cannot
    # name its parent or its substitution cannot be paired with anything.
    # Without these the lift step finds zero variants and says so quietly,
    # after the campaign has already run.
    peptide_sequence: str | None = None
    parent_peptide_id: str | None = None
    substitution: str | None = None
    position: int | None = None
    role: str | None = None
    iptm_min_binary: float | None = None
    iptm_min_ternary: float | None = None
    iptm_min_ternary_conditioned: float | None = None
    iptm_min_ternary_unconstrained: float | None = None
    delta_iptm: float | None = None
    delta_iptm_global: float | None = None
    # Robust companions to the mandated minimum (D-NOB-023). Reported beside
    # delta_iptm, never instead of it.
    iptm_median_binary: float | None = None
    iptm_median_ternary: float | None = None
    delta_iptm_median: float | None = None
    collapsed_seeds_binary: list[int] = field(default_factory=list)
    collapsed_seeds_ternary: list[int] = field(default_factory=list)
    seed_collapse_affects_delta: bool = False
    iptm_min_binary_global: float | None = None
    iptm_min_ternary_global: float | None = None
    affinity_pred_value: float | None = None
    conditioning_disagreement: float | None = None
    forced: bool | None = None
    seeds_binary: int = 0
    seeds_ternary: int = 0
    seed_records: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # Pair-level fields on which this pair's jobs disagree. Empty is the
    # only healthy value: a non-empty one means the manifest emitted jobs
    # for two different things under one pair id (F42).
    pair_level_disagreements: dict = field(default_factory=dict)
    # How the ligand chain was encoded, and the manifest's flag for it. Spec
    # 2.2 wants a SMILES fallback flagged "so the difference is visible in
    # the results table", and both were on the queue row and dropped here,
    # so the table could not show what the manifest had recorded (F51).
    ligand_encoding: str | None = None
    ligand_flags: list = field(default_factory=list)
    # Whether Boltz's affinity head was requested for this pair's ligand.
    # False means the ligand exceeds the 128 heavy-atom cap, which spec 2.2
    # says to record as affinity_unavailable, and spec Phase 4 lists as one
    # of the three flags the ledger is faceted on. It was on the queue row
    # and not on the pair, so the facet could not be built (F53).
    affinity_available: bool | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# Properties of a (receptor, peptide, ligand) triple rather than of one job.
# Deliberately excludes ligand_key, which the binary arm legitimately lacks,
# and job_id, seed, complex_type and conditioning, which vary by design.
PAIR_LEVEL_FIELDS = (
    "construct", "e3_gene", "peptide_id", "peptide_gene", "peptide_label",
    "modality", "tier", "peptide_sequence", "parent_peptide_id",
    "substitution", "position", "role",
)


def peptide_chain_index(construct_name: str) -> int:
    """Index of the peptide chain in the YAML's chain order."""
    return len(C.CONSTRUCTS[construct_name].segments)


def _receptor_peptide_iptm(confidence: dict, construct_name: str) -> tuple:
    """Interface confidence between the substrate receptor and the peptide.

    Spec 4.3 defines Delta-ipTM as a difference of ipTM minima and does not
    say which chain pair the ipTM is. For a single-chain receptor there is no
    question. For a receptor submitted as several chains there is, and it was
    being answered silently: the pair was chain 0 against the peptide, which
    for DCAF15_DDB1_DDA1 means the N-terminal domain of DCAF15 alone while
    its C-terminal domain, which the substrate also binds, was ignored.

    Taking the minimum across the substrate receptor's own segments is the
    same rule this module already applies twice: across the two directions of
    Boltz's asymmetric matrix, and across seeds (spec 4.3, minimum not mean).
    The scaffolding chains are deliberately excluded. A minimum over all five
    would be dominated by DDB1, which the peptide is not supposed to touch, so
    the statistic would measure how well the degron fails to engage the
    scaffold.

    Measured effect of the change: one pair in one campaign, RBM39/DCAF15,
    whose Delta-ipTM moved from +0.1872 to +0.1937. No other pair in any
    campaign moved at all, and no verdict changed (D-NOB-044).

    Returns (value, chains_used, first_chain_only) so the number is auditable
    and the previous definition stays recoverable from the record.
    """
    chains = C.CONSTRUCTS[construct_name].substrate_receptor_chains()
    peptide = peptide_chain_index(construct_name)
    values = [_pair_iptm(confidence, chain, peptide) for chain in chains]
    # Defence in depth, not a fix. `_pair_iptm` already requires `finite`
    # on each cell (F76), so a non-finite value cannot reach this filter
    # today and `is not None` was adequate. It is `finite_values` because
    # the hazard if one ever did reach here is specific: `min` with a NaN
    # present is order-dependent, min([0.9, nan]) being 0.9 and
    # min([nan, 0.9]) being nan, so the order of the construct's receptor
    # segments would decide whether it survived into Delta-ipTM.
    #
    # Recorded as redundant because I first claimed it as a gap, and the
    # mutation harness disagreed: reverting this line failed no test,
    # because the NaN never gets this far (F87).
    present = finite_values(values)
    return (
        min(present) if present else None,
        list(chains),
        _pair_iptm(confidence, 0, peptide),
    )


def _pair_iptm(confidence: dict, first: int, second: int) -> float | None:
    """One cell of Boltz's pair_chains_iptm matrix, symmetrised.

    The matrix is not always symmetric (the smoke test showed 0.876 one way and
    0.840 the other), so the minimum of the two directions is taken. Choosing the
    minimum rather than the mean keeps the whole statistic conservative, which is
    the same reasoning spec 4.3 applies to the seed aggregation.
    """
    matrix = confidence.get("pair_chains_iptm")
    if not isinstance(matrix, dict):
        return None
    values = []
    for a, b in ((first, second), (second, first)):
        row = matrix.get(str(a)) or matrix.get(a)
        if isinstance(row, dict):
            value = row.get(str(b))
            if value is None:
                value = row.get(b)
            if finite(value):
                values.append(float(value))
    return min(values) if values else None


def seed_record(job: dict) -> SeedRecord:
    confidence = job.get("confidence") or {}
    affinity = job.get("affinity") or {}
    index = peptide_chain_index(job["construct"])
    receptor_peptide, chains_used, first_only = _receptor_peptide_iptm(
        confidence, job["construct"]
    )
    return SeedRecord(
        job_id=job["job_id"],
        seed=int(job["seed"]),
        complex_type=job["complex_type"],
        conditioning=job["conditioning"],
        iptm_global=confidence.get("iptm"),
        iptm_receptor_peptide=receptor_peptide,
        iptm_receptor_chains=chains_used,
        iptm_receptor_peptide_first_chain_only=first_only,
        ptm=confidence.get("ptm"),
        complex_plddt=confidence.get("complex_plddt"),
        ligand_iptm=confidence.get("ligand_iptm"),
        confidence_score=confidence.get("confidence_score"),
        # Spec 4.7 and D-NOB-005: recorded for the small-molecule chain only,
        # and never a ranking key.
        affinity_pred_value=affinity.get("affinity_pred_value") if affinity else None,
        structure=job.get("structure"),
    )


def _minimum(values: list[float | None]) -> float | None:
    present = finite_values(values)
    return min(present) if present else None


def _median(values: list[float | None]) -> float | None:
    present = sorted(finite_values(values))
    if not present:
        return None
    middle = len(present) // 2
    if len(present) % 2:
        return present[middle]
    return (present[middle - 1] + present[middle]) / 2


# A seed whose interface confidence sits this far below the median of its own
# condition is treated as a collapsed run rather than a low measurement.
COLLAPSE_MARGIN = float(paths.thresholds()["scoring"]["collapse_margin"])


def _collapsed_seeds(values: list[tuple[int, float | None]]) -> list[int]:
    """Seeds that fell far below the median of their own condition.

    This exists because of what the benchmark panel showed on its first pair.
    GSPT1/CRBN/CC-885, the single highest-value positive control in the panel,
    returned receptor-peptide ipTM of 0.885, 0.877, 0.806, **0.082** and 0.911
    across its five conditioned ternary seeds. Four seeds agree closely and one
    diffusion run collapsed.

    Spec 4.3 mandates the minimum across seeds, so that one run sets the
    headline number and drags Delta-ipTM to -0.76 for a pair that four runs out
    of five call a confident interface. The minimum is the right statistic for
    the question "does this interface reliably form", but it is a measure of
    worst-case seed behaviour, not of interface confidence, and the two part
    company whenever a diffusion run fails outright.

    The mandated minimum is still what `delta_iptm` reports. These diagnostics
    sit beside it so the distinction is visible rather than silently folded into
    the headline. See D-NOB-023.
    """
    present = [(seed, value) for seed, value in values if finite(value)]
    if len(present) < COLLAPSE_MINIMUM_SEEDS:
        return []
    median = _median([value for _seed, value in present])
    if median is None:
        return []
    return sorted(seed for seed, value in present if median - value > COLLAPSE_MARGIN)


def aggregate(results_path: Path, sampling_tier: int = 1) -> list[PairMetrics]:
    """Aggregate every completed job into per-pair metrics.

    `sampling_tier` partitions by sampling regime and defaults to tier 1, the
    regime the headline Delta-ipTM is defined over. This is a hard filter, not
    a label: `iptm_min` is a minimum over seeds and a minimum is not robust to
    sample count. Tier 2 draws 25 diffusion samples where tier 1 draws 1, so
    mixing the two into one minimum would drag the ternary arm down while the
    binary arm stayed put, and `delta_iptm` would report an order-statistic
    artefact as a weakened interface. Tier 2 exists to refine poses (spec 1.2),
    not to re-measure Delta-ipTM.

    Note the field name: `tier` on a job record is the *curation* tier (Tier A,
    Tier B, benchmark), which is a different axis entirely. The sampling tier
    is `tier_setting`, and a record written before that field existed is tier 1.
    """
    if not results_path.exists():
        return []

    jobs = [
        json.loads(line) for line in results_path.read_text().splitlines() if line.strip()
    ]
    jobs = [job for job in jobs if int(job.get("tier_setting", 1)) == sampling_tier]
    if not jobs:
        return []
    grouped: dict[str, list[dict]] = defaultdict(list)
    for job in jobs:
        grouped[job["pair_id"]].append(job)

    output: list[PairMetrics] = []
    for pair_id, pair_jobs in sorted(grouped.items()):
        first = pair_jobs[0]
        # Everything below is read off the first job on the understanding that
        # these are properties of the pair, not of the job. They are, and
        # nothing said so. `ligand_key` is already taken differently, from the
        # first job that has one, because the binary arm has none: so one field
        # was known to vary and the rest were taken on trust (F42).
        #
        # A disagreement here means the manifest emitted one pair's jobs with
        # two different peptides, constructs or labels, and taking the first
        # would report the pair as whichever job happened to be read first.
        # Recorded rather than raised: scoring a campaign is not the place to
        # refuse, and a pair carrying this note is one nobody should read.
        disagreements = {
            field: sorted({str(job.get(field)) for job in pair_jobs})
            for field in PAIR_LEVEL_FIELDS
            if len({str(job.get(field)) for job in pair_jobs}) > 1
        }
        metrics = PairMetrics(
            pair_id=pair_id,
            construct=first["construct"],
            e3_gene=first["e3_gene"],
            peptide_id=first["peptide_id"],
            peptide_gene=first.get("peptide_gene"),
            peptide_label=first.get("peptide_label"),
            ligand_key=next(
                (job.get("ligand_key") for job in pair_jobs if job.get("ligand_key")), None
            ),
            # Taken the same way as ligand_key, from the first job that has
            # one, because the binary arm carries neither.
            ligand_encoding=next(
                (job.get("ligand_encoding") for job in pair_jobs
                 if job.get("ligand_encoding")), None
            ),
            ligand_flags=sorted({
                flag for job in pair_jobs for flag in (job.get("flags") or [])
            }),
            affinity_available=next(
                (str(job.get("affinity_available")).lower() == "true"
                 for job in pair_jobs if job.get("affinity_available") is not None),
                None,
            ),
            modality=first.get("modality", "none"),
            tier=first.get("tier", "unknown"),
            peptide_sequence=first.get("peptide_sequence"),
            parent_peptide_id=first.get("parent_peptide_id"),
            substitution=first.get("substitution"),
            position=first.get("position"),
            role=first.get("role"),
        )
        if disagreements:
            metrics.notes.append(
                "jobs in this pair disagree on "
                + ", ".join(f"{field} ({'/'.join(values)})"
                            for field, values in sorted(disagreements.items()))
                + ": these are pair properties, so the pair is not one pair"
            )
            metrics.pair_level_disagreements = disagreements

        records = [seed_record(job) for job in pair_jobs]
        metrics.seed_records = [record.to_dict() for record in records]

        binary = [item for item in records if item.complex_type == "binary"]
        ternary = [item for item in records if item.complex_type == "ternary"]
        conditioned = [item for item in ternary if item.conditioning == "conditioned"]
        unconstrained = [item for item in ternary if item.conditioning == "unconstrained"]

        metrics.seeds_binary = len(binary)
        metrics.seeds_ternary = len(ternary)

        metrics.iptm_min_binary = _minimum([item.iptm_receptor_peptide for item in binary])
        metrics.iptm_min_ternary = _minimum([item.iptm_receptor_peptide for item in ternary])
        metrics.iptm_min_ternary_conditioned = _minimum(
            [item.iptm_receptor_peptide for item in conditioned]
        )
        metrics.iptm_min_ternary_unconstrained = _minimum(
            [item.iptm_receptor_peptide for item in unconstrained]
        )
        metrics.iptm_min_binary_global = _minimum([item.iptm_global for item in binary])
        metrics.iptm_min_ternary_global = _minimum([item.iptm_global for item in ternary])

        metrics.iptm_median_binary = _median(
            [item.iptm_receptor_peptide for item in binary]
        )
        metrics.iptm_median_ternary = _median(
            [item.iptm_receptor_peptide for item in ternary]
        )
        metrics.collapsed_seeds_binary = _collapsed_seeds(
            [(item.seed, item.iptm_receptor_peptide) for item in binary]
        )
        metrics.collapsed_seeds_ternary = _collapsed_seeds(
            [(item.seed, item.iptm_receptor_peptide) for item in ternary]
        )
        if (metrics.iptm_median_binary is not None
                and metrics.iptm_median_ternary is not None):
            metrics.delta_iptm_median = round(
                metrics.iptm_median_ternary - metrics.iptm_median_binary, 4
            )

        if metrics.iptm_min_binary is not None and metrics.iptm_min_ternary is not None:
            metrics.delta_iptm = round(
                metrics.iptm_min_ternary - metrics.iptm_min_binary, 4
            )
        else:
            metrics.notes.append(
                "delta_iptm not computed: "
                f"{len(binary)} binary and {len(ternary)} ternary seeds present"
            )

        # Did a collapsed seed set the minimum that the headline number uses?
        for records, collapsed, minimum in (
            (binary, metrics.collapsed_seeds_binary, metrics.iptm_min_binary),
            (ternary, metrics.collapsed_seeds_ternary, metrics.iptm_min_ternary),
        ):
            if not collapsed or minimum is None:
                continue
            setter = [
                item.seed for item in records
                if finite(item.iptm_receptor_peptide)
                and abs(item.iptm_receptor_peptide - minimum) < 1e-9
            ]
            if any(seed in collapsed for seed in setter):
                metrics.seed_collapse_affects_delta = True
                metrics.notes.append(
                    f"seed(s) {collapsed} collapsed well below the median of their "
                    "condition and set the mandated minimum, so delta_iptm here "
                    "reports worst-case seed behaviour rather than interface "
                    "confidence. delta_iptm_median is reported alongside"
                )
        if (metrics.iptm_min_binary_global is not None
                and metrics.iptm_min_ternary_global is not None):
            metrics.delta_iptm_global = round(
                metrics.iptm_min_ternary_global - metrics.iptm_min_binary_global, 4
            )

        # Spec 4.7: agreement between the conditioned and unconstrained arms is
        # the signal. A pose that only appears under conditioning is forced.
        if (metrics.iptm_min_ternary_conditioned is not None
                and metrics.iptm_min_ternary_unconstrained is not None):
            metrics.conditioning_disagreement = round(
                metrics.iptm_min_ternary_conditioned
                - metrics.iptm_min_ternary_unconstrained, 4
            )
        else:
            metrics.notes.append("conditioning disagreement not computable: one arm absent")

        affinities = [
            item.affinity_pred_value for item in ternary
            if finite(item.affinity_pred_value)
        ]
        metrics.affinity_pred_value = (
            round(sum(affinities) / len(affinities), 4) if affinities else None
        )

        output.append(metrics)
    return output
