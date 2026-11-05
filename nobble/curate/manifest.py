"""Manifest generation and validation (spec Phase 1).

A manifest row is one Boltz job. Every tier-1 pair expands to the full job set
spec 1.2 and Phase 2 describe:

    (binary, ternary) x (conditioned, unconstrained) x 5 seeds = 20 jobs per pair

Spec 1.2 quotes "two jobs (binary and ternary) across five seeds, so a 400-pair
campaign is 4,000 inferences", which counts 10 per pair and omits the
conditioning axis that Phase 2's build list then adds. Both readings are carried
explicitly here: `jobs_per_pair` is computed from the axes actually emitted
rather than quoted, so the campaign sizer cannot inherit the ambiguity. See
D-NOB-019.

Validation is the Phase 1 gate: PTM completeness (spec 2.3), token count against
the cap (spec 1.1), CCD resolution and the affinity heavy-atom cap (spec 2.2).
A peptide whose degron class requires a modification and which is submitted
without one is an error here, not a low-scoring result later.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from nobble import paths
from nobble.curate import constructs as C
from nobble.curate import ligands as L

# Which construct serves each E3. Only receptors with a defined
# substrate-binding domain can be built: a peptide whose annotated E3 has no
# construct is recorded as unroutable rather than silently reassigned to CRBN.
# Spec 1.1's six Tier A receptors. Tier B's are added below from the form
# rather than written out here, so the map and the form cannot disagree
# about which construct a gene uses.
E3_TO_CONSTRUCT = {
    "CRBN": "CRBN_CULT",
    "VHL": "VHL_VCB",
    "DCAF15": "DCAF15_DDB1_DDA1",
    "DDB1": "DDB1_BPC",
    "KEAP1": "KEAP1_KELCH",
    "FEM1B": "FEM1B_ANK",
}


def _tier_b_routes() -> dict[str, str]:
    """Gene to construct name for the Tier B receptors that are named.

    Derived, not transcribed. A second copy of these eleven pairs is the
    duplication F181, F183 and F187 were each about, and the form is where
    the judgement lives (D-NOB-072).
    """
    try:
        from nobble.curate import tier_b_constructs as T

        return {c.e3_gene: name for name, c in T.load().items() if c.e3_gene}
    except Exception:                                   # noqa: BLE001
        return {}


# Tier A wins a collision, which there is none of: the genes are disjoint.
E3_TO_CONSTRUCT = {**_tier_b_routes(), **E3_TO_CONSTRUCT}

# From config, not written here. `config/tuning.toml` declares
# `campaign.seeds = 5` and nothing read it: two hard-coded copies of
# (1, 2, 3, 4, 5), here and in execute/corrected.py, decided the real
# behaviour, so changing the configured value changed nothing.
#
# The count matters more than most. Delta-ipTM is a difference of minima
# over seeds and a minimum is not robust to how many draws it was taken
# over, which is the reasoning behind the hard partition by sampling tier
# and behind the seed-balance report on the headline curve. It also sets
# the campaign's size: 158 pairs times 5 seeds times 3 arms is 2,360 jobs
# (F91).
SEEDS = tuple(range(1, int(paths.tuning()["campaign"]["seeds"]) + 1))
CONDITIONS = ("conditioned", "unconstrained")
COMPLEXES = ("binary", "ternary")


@dataclass
class Job:
    """One Boltz inference."""

    job_id: str
    pair_id: str
    tier: str                      # benchmark | A | B
    construct: str
    e3_gene: str
    peptide_id: str
    peptide_sequence: str
    peptide_gene: str | None
    peptide_label: str | None
    # The peptide's span in canonical numbering. Pose recovery needs it to map
    # a predicted peptide (numbered 1..N in its own chain) onto the deposited
    # chain, and without it the comparison cannot be made at all.
    peptide_accession: str | None
    peptide_start_res: int | None
    peptide_end_res: int | None
    ligand_key: str | None
    ligand_encoding: str | None
    modality: str
    complex_type: str              # binary | ternary
    conditioning: str              # conditioned | unconstrained
    seed: int
    tokens: int
    affinity_available: bool
    required_modification: dict | None
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ValidationIssue:
    severity: str                  # error | warning
    code: str
    detail: str
    job_id: str | None = None
    pair_id: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def jobs_per_pair() -> int:
    """Computed from the axes emitted, never quoted from the spec."""
    # A binary complex has no ligand, so conditioning on a ligand pocket is
    # meaningless for it: the binary arm runs unconstrained only. That makes the
    # real count 5 binary + 10 ternary = 15, not the 10 spec 1.2 quotes nor the
    # 20 a naive product of all three axes would give.
    return len(SEEDS) * (1 + len(CONDITIONS))


def expand_pair(
    pair_id: str,
    tier: str,
    construct: C.Construct,
    peptide,
    ligand: L.Ligand | None,
    seeds: tuple[int, ...] | None = None,
    conditions: tuple[str, ...] | None = None,
) -> list[Job]:
    """Expand one (receptor, peptide, ligand) triple into its job set.

    `seeds` and `conditions` default to the campaign's axes. Tier B passes
    `conditions=("unconstrained",)` because conditioning needs a ligand
    pocket derived from the receptor's own deposited structure, and a Tier B
    receptor has none: the pocket in the benchmark pair it borrows its glue
    and degron from belongs to the proven receptor, not to this one. A
    conditioned arm there would place the ligand in another protein's
    pocket (D-NOB-073).
    """
    seeds = SEEDS if seeds is None else seeds
    all_conditions = CONDITIONS if conditions is None else conditions
    jobs: list[Job] = []
    # A structural zinc is one heavy atom, so one token, and it is present in
    # both arms (see yaml_gen). Counting it in only one would understate the
    # binary arm against the token cap it is validated on.
    from nobble.curate import peptides as _P

    cofactor_tokens = 1 if _P.requires_structural_zinc(peptide)["required"] else 0
    base_tokens = construct.residue_count() + peptide.length + cofactor_tokens

    for complex_type in COMPLEXES:
        if complex_type == "ternary" and ligand is None:
            continue
        ligand_atoms = (ligand.heavy_atoms or 0) if complex_type == "ternary" else 0
        tokens = base_tokens + ligand_atoms
        # Conditioning places the ligand in a pocket, so it only applies to the
        # ternary arm.
        arm_conditions = (all_conditions if complex_type == "ternary"
                          else ("unconstrained",))
        for conditioning in arm_conditions:
            for seed in seeds:
                flags: list[str] = []
                if construct.exception:
                    flags.append("token_cap_declared_exception")
                if ligand is not None and complex_type == "ternary":
                    if not ligand.affinity_available:
                        flags.append("affinity_unavailable")
                    if ligand.encoding == "smiles":
                        flags.append("smiles_fallback")
                    if ligand.is_furniture:
                        flags.append("ligand_flagged_furniture")
                job_id = (
                    f"{pair_id}__{complex_type}__{conditioning}__seed{seed}"
                )
                jobs.append(
                    Job(
                        job_id=job_id,
                        pair_id=pair_id,
                        tier=tier,
                        construct=construct.name,
                        e3_gene=construct.e3_gene,
                        peptide_id=peptide.peptide_id,
                        peptide_sequence=peptide.sequence,
                        peptide_gene=peptide.gene,
                        peptide_label=peptide.label,
                        peptide_accession=peptide.accession,
                        peptide_start_res=peptide.start_res,
                        peptide_end_res=peptide.end_res,
                        ligand_key=ligand.key if (ligand and complex_type == "ternary") else None,
                        ligand_encoding=(
                            ligand.encoding if (ligand and complex_type == "ternary") else None
                        ),
                        modality=ligand.modality if ligand else "none",
                        complex_type=complex_type,
                        conditioning=conditioning,
                        seed=seed,
                        tokens=tokens,
                        affinity_available=bool(
                            ligand and complex_type == "ternary" and ligand.affinity_available
                        ),
                        required_modification=peptide.required_modification,
                        flags=flags,
                    )
                )
    return jobs


def validate(jobs: list[Job]) -> list[ValidationIssue]:
    """Spec Phase 1 manifest validation. Errors block the gate; warnings do not."""
    limits = paths.thresholds()["manifest"]
    cap = int(limits["token_cap_tier1"])
    issues: list[ValidationIssue] = []
    declared = C.declared_exceptions()

    for job in jobs:
        # Token cap (spec 1.1).
        if job.tokens > cap and job.construct not in declared:
            issues.append(ValidationIssue(
                "error", "token_cap_exceeded",
                f"{job.tokens} tokens exceeds the {cap}-token tier-1 cap and "
                f"{job.construct} is not a declared exception",
                job.job_id, job.pair_id,
            ))

        # PTM completeness (spec 2.3). A degron class that requires a
        # modification and carries none is a manifest error by construction.
        requirement = job.required_modification
        if requirement:
            if not any(residue in job.peptide_sequence for residue in requirement["residue"]):
                issues.append(ValidationIssue(
                    "error", "ptm_residue_absent",
                    f"degron class requires {requirement['note']} on "
                    f"{requirement['residue']} but the peptide carries no such residue",
                    job.job_id, job.pair_id,
                ))

        # Ligand encoding (spec 2.2).
        if job.complex_type == "ternary":
            if job.ligand_key is None:
                issues.append(ValidationIssue(
                    "error", "ternary_without_ligand",
                    "a ternary job must carry a ligand chain",
                    job.job_id, job.pair_id,
                ))
            elif job.ligand_encoding == "smiles":
                issues.append(ValidationIssue(
                    "warning", "smiles_fallback",
                    "no CCD match: encoded as SMILES and flagged",
                    job.job_id, job.pair_id,
                ))
            if not job.affinity_available:
                issues.append(ValidationIssue(
                    "warning", "affinity_unavailable",
                    "affinity head unavailable for this ligand; structure prediction runs",
                    job.job_id, job.pair_id,
                ))
    return issues


def build_benchmark_manifest() -> dict:
    """The seven benchmark pairs, which spec 3.1 runs first in every campaign."""
    from nobble.curate import peptides as P

    peptide_list = P.benchmark_peptides()
    ligand_map = L.benchmark_ligands()
    # Keyed on gene AND E3: BRD4 is two distinct members (BD2/VHL/MZ1 and
    # BD1/CRBN/dBET), and keying on gene alone silently collapses them, which
    # drops the canonical bivalent benchmark and double-counts the other arm.
    by_member = {(item["gene"], item["e3"]): item for item in P.BENCHMARK_CHAINS}

    jobs: list[Job] = []
    pairs: list[dict] = []
    unroutable: list[dict] = []
    # Keyed by peptide_id. A scramble inherits its parent's exact ligand, and
    # rebuilding one from its dict form loses the SMILES-encoded degraders:
    # by_ccd cannot reconstruct a ligand that never had a CCD.
    routing: dict[str, dict] = {}

    for peptide in peptide_list:
        member = by_member.get((peptide.gene, peptide.e3_hint))
        if member is None:
            continue
        construct_name = E3_TO_CONSTRUCT.get(member["e3"])
        if construct_name is None:
            unroutable.append({"peptide": peptide.peptide_id, "e3": member["e3"],
                               "reason": "no receptor construct defined"})
            continue
        construct = C.by_name(construct_name)
        ligand = ligand_map.get(member["index"])
        pair_id = f"bench{member['index']:02d}_{peptide.gene}_{member['e3']}"
        pair_jobs = expand_pair(pair_id, "benchmark", construct, peptide, ligand)
        jobs.extend(pair_jobs)
        routing[peptide.peptide_id] = {"construct": construct, "ligand": ligand,
                                       "pair_id": pair_id}
        pairs.append({
            "pair_id": pair_id,
            "member": member["index"],
            "tier": "benchmark",
            "construct": construct.name,
            "e3_gene": construct.e3_gene,
            "peptide_id": peptide.peptide_id,
            "peptide_sequence": peptide.sequence,
            "peptide_gene": peptide.gene,
            "ligand": ligand.to_dict() if ligand else None,
            "jobs": len(pair_jobs),
        })

    issues = validate(jobs)
    return {
        "pairs": pairs,
        "jobs": jobs,
        "unroutable": unroutable,
        "routing": routing,
        "jobs_per_pair": jobs_per_pair(),
        "issues": [issue.to_dict() for issue in issues],
        "errors": sum(1 for issue in issues if issue.severity == "error"),
        "warnings": sum(1 for issue in issues if issue.severity == "warning"),
    }


def write(manifest: dict, name: str = "benchmark") -> dict:
    """Write the manifest to data/manifests/<name>.jsonl plus a summary."""
    path = paths.MANIFESTS / f"{name}.jsonl"
    with path.open("w") as handle:
        for job in manifest["jobs"]:
            handle.write(json.dumps(job.to_dict()) + "\n")

    summary_path = paths.MANIFESTS / f"{name}.summary.json"
    summary_path.write_text(json.dumps(
        {
            "pairs": manifest["pairs"],
            "pair_count": len(manifest["pairs"]),
            "job_count": len(manifest["jobs"]),
            "jobs_per_pair": manifest["jobs_per_pair"],
            "unroutable": manifest["unroutable"],
            "errors": manifest["errors"],
            "warnings": manifest["warnings"],
            "issues": manifest["issues"],
            "token_range": [
                min((job.tokens for job in manifest["jobs"]), default=0),
                max((job.tokens for job in manifest["jobs"]), default=0),
            ],
        },
        indent=2,
    ))
    return {"manifest": str(path), "summary": str(summary_path)}


def tier_b_seeds() -> tuple[int, ...]:
    """Seeds per arm for the Tier B arm, from config.

    Its own key rather than borrowing `design.minimum_seeds` or
    `scoring.collapse_minimum_seeds`, both of which are 3 and mean something
    else. One number serving two meanings is what F181 and F183 were about,
    and a later change to either of those for its own reasons would silently
    change the depth of this arm.
    """
    return tuple(range(1, int(paths.tuning()["campaign"]
                              .get("tier_b_seeds", len(SEEDS))) + 1))


def build_tier_b_manifest(library: list | None = None) -> dict:
    """The Tier B arm: unproven ligases against proven glue-degron pairs.

    Spec 3.3 selects fifteen ligandable-unproven ligases and names no
    receptor construct for any of them. Marc named eleven and excluded four
    (D-NOB-072); this is the arm those constructs make possible.

    The design is D-NOB-073's. A Tier B pair holds a known-working glue and
    degron together and swaps only the receptor: lenalidomide with the IKZF1
    zinc finger it actually degrades, against ASB8 instead of CRBN. So the
    benchmark panel contains the same glue and degron with its proven
    receptor, which makes it the matched positive control without spending a
    job on one. Each pair also gets its degron's composition-matched
    scramble, which the library already carries for all seven benchmark
    degrons, so the arm has an internal negative too.

    Two arms rather than three: see `expand_pair` on why conditioning cannot
    apply to a receptor whose pocket belongs to a different protein.

    What this arm can show is narrow and worth stating. Every pair is
    expected to fail, because these ligases have no known glue. A hit is a
    hypothesis and a uniform absence of hits is the likely and still
    informative result: it says the chemotypes that work on CRBN and VHL do
    not transfer, which is what "ligandable but unproven" predicts.
    """
    from nobble.curate import library as library_module
    from nobble.curate import peptides as P
    from nobble.curate import tier_b_constructs as T

    if library is None:
        persisted = library_module.load()
        if persisted is None:
            return {"status": "no library manifest: run nobble.curate.library first",
                    "pairs": [], "jobs": [], "unroutable": []}
        library = persisted["peptides"]

    receptors = sorted(T.load().items())
    if not receptors:
        return {"status": "no Tier B constructs: see config/tier_b_constructs.toml",
                "pairs": [], "jobs": [], "unroutable": []}

    # The glue and degron pairs, from the builder that already resolved each
    # benchmark member's deposited chain, CCD and ligand object. Taken from
    # its routing rather than rebuilt, because a SMILES-encoded degrader has
    # no CCD to reconstruct from.
    benchmark = build_benchmark_manifest()
    routing = benchmark.get("routing", {})
    by_id = {row["peptide_id"]: row for row in library}
    scramble_of: dict[str, dict] = {}
    for row in library:
        if row["source"] == "scramble" and row.get("parent_peptide_id") in routing:
            scramble_of[row["parent_peptide_id"]] = row

    seeds = tier_b_seeds()
    jobs: list[Job] = []
    pairs: list[dict] = []
    unroutable: list[dict] = []

    for construct_name, construct in receptors:
        for parent_id, resolved in sorted(routing.items()):
            parent_row = by_id.get(parent_id)
            ligand = resolved.get("ligand")
            if parent_row is None or ligand is None:
                unroutable.append({
                    "construct": construct_name, "peptide": parent_id,
                    "reason": ("the degron is not in the library" if parent_row is None
                               else "the benchmark pair resolved no ligand"),
                })
                continue
            members = [("pos", parent_row)]
            scramble = scramble_of.get(parent_id)
            if scramble is not None:
                members.append(("neg", scramble))
            else:
                unroutable.append({
                    "construct": construct_name, "peptide": parent_id,
                    "reason": "no composition-matched scramble for this degron",
                })
            for label, row in members:
                peptide = P.Peptide(**{k: v for k, v in row.items() if k != "length"})
                pair_id = (f"tb_{label}_{construct.e3_gene}_"
                           f"{parent_row.get('gene') or 'unknown'}_{ligand.key}")
                pair_jobs = expand_pair(
                    pair_id, "tier_b", construct, peptide, ligand,
                    seeds=seeds, conditions=("unconstrained",),
                )
                jobs.extend(pair_jobs)
                pairs.append({
                    "pair_id": pair_id,
                    "tier": "tier_b",
                    "construct": construct.name,
                    "e3_gene": construct.e3_gene,
                    "peptide_id": row["peptide_id"],
                    "peptide_sequence": row["sequence"],
                    "peptide_gene": parent_row.get("gene"),
                    "role": "positive" if label == "pos" else "scramble",
                    "scramble_of": parent_id if label == "neg" else None,
                    "borrowed_from": resolved.get("pair_id"),
                    "ligand": ligand.to_dict(),
                    "jobs": len(pair_jobs),
                })

    issues = validate(jobs)
    return {
        "pairs": pairs,
        "jobs": jobs,
        "unroutable": unroutable,
        "jobs_per_pair": len(seeds) * len(COMPLEXES),
        "seeds": list(seeds),
        "receptors": [name for name, _ in receptors],
        "glue_degron_pairs": sorted(routing),
        # Derived, never asserted. I wrote `"errors": 0` here and it was
        # false: validate() found ten token_cap_exceeded errors, DCAF8L1
        # against the largest glue, and a hard-coded zero would have carried
        # them past assemble_campaign's refusal, which keys on this field.
        # The same shape as F193 and F195, in a builder written minutes
        # after reading both (F211).
        "errors": sum(1 for issue in issues if issue.severity == "error"),
        "warnings": sorted({issue.code for issue in issues
                            if issue.severity == "warning"}),
        "issues": [issue.to_dict() for issue in issues],
    }


def build_campaign_manifest(library: list | None = None) -> dict:
    """The full campaign: the benchmark panel, the Sievers arm and the scrambles.

    Reads the persisted library (`data/manifests/library.jsonl`) rather than
    reassembling it, because assembly is network-bound on UniProt and InterPro
    and takes over half an hour.

    Routing differs by source, so it is explicit per source rather than one
    rule with exceptions:

    * **benchmark** members come from `build_benchmark_manifest`, which knows
      each member's deposited chain, CCD and E3 pairing.
    * **sievers_zf** members all target CRBN and carry the IMiD assigned in
      D-NOB-033, pomalidomide or lenalidomide depending on which the screen
      found significant for that zinc finger.
    * **scramble** members inherit their parent's construct and ligand. A
      composition-matched scramble run against a different receptor or a
      different drug than its positive is not a control for anything.
    """
    from nobble.curate import library as library_module
    from nobble.curate import peptides as P

    if library is None:
        persisted = library_module.load()
        if persisted is None:
            return {"status": "no library manifest: run nobble.curate.library first",
                    "pairs": [], "jobs": []}
        library = persisted["peptides"]

    rows = {row["peptide_id"]: row for row in library}

    # The benchmark panel keeps its own builder: it is the only arm whose
    # routing depends on a deposited structure rather than on the peptide.
    benchmark = build_benchmark_manifest()
    jobs: list[Job] = list(benchmark["jobs"])
    pairs: list[dict] = list(benchmark["pairs"])
    unroutable: list[dict] = list(benchmark["unroutable"])
    benchmark_routing = benchmark.get("routing", {})

    def _ligand_for(row: dict):
        ccd = (row.get("screen_drugs") or {}).get("assigned_ccd")
        if not ccd:
            return None
        return L.by_ccd(ccd, modality="glue", source="sievers_assigned")

    # Sievers arm, then scrambles, so a scramble can look its parent up.
    resolved: dict[str, dict] = {}
    for row in library:
        if row["source"] != "sievers_zf":
            continue
        construct_name = E3_TO_CONSTRUCT.get(row.get("e3_hint"))
        ligand = _ligand_for(row)
        if construct_name is None or ligand is None:
            unroutable.append({
                "peptide": row["peptide_id"], "e3": row.get("e3_hint"),
                "reason": ("no receptor construct defined" if construct_name is None
                           else "no IMiD assigned: see D-NOB-033"),
            })
            continue
        construct = C.by_name(construct_name)
        peptide = P.Peptide(**{k: v for k, v in row.items() if k != "length"})
        label = "pos" if row.get("label") == "degraded" else "neg"
        pair_id = f"sv_{label}_{row.get('gene') or 'unknown'}_{row['peptide_id'][-6:]}"
        pair_jobs = expand_pair(pair_id, "sievers_zf", construct, peptide, ligand)
        jobs.extend(pair_jobs)
        entry = {
            "pair_id": pair_id,
            "tier": "sievers_zf",
            "construct": construct.name,
            "e3_gene": construct.e3_gene,
            "peptide_id": row["peptide_id"],
            "peptide_sequence": row["sequence"],
            "peptide_gene": row.get("gene"),
            "screen_label": row.get("label"),
            "assigned_drug": (row.get("screen_drugs") or {}).get("assigned_drug"),
            "ligand": ligand.to_dict(),
            "jobs": len(pair_jobs),
        }
        pairs.append(entry)
        resolved[row["peptide_id"]] = {"construct": construct, "ligand": ligand,
                                       "pair_id": pair_id}

    for row in library:
        if row["source"] != "scramble":
            continue
        parent_id = row.get("parent_peptide_id")
        parent_row = rows.get(parent_id)
        inherited = resolved.get(parent_id)
        if inherited is None:
            # A benchmark parent: take the construct and ligand object the
            # benchmark builder already resolved, including SMILES-encoded
            # degraders that have no CCD to rebuild from.
            inherited = benchmark_routing.get(parent_id)
        if inherited is None or inherited["ligand"] is None:
            unroutable.append({
                "peptide": row["peptide_id"], "parent": parent_id,
                "reason": ("scramble whose parent was not routed: a control "
                           "cannot run without the positive it controls for"),
            })
            continue
        peptide = P.Peptide(**{k: v for k, v in row.items() if k != "length"})
        pair_id = f"scr_{inherited['pair_id']}"
        pair_jobs = expand_pair(pair_id, "scramble", inherited["construct"],
                                peptide, inherited["ligand"])
        jobs.extend(pair_jobs)
        pairs.append({
            "pair_id": pair_id,
            "tier": "scramble",
            "construct": inherited["construct"].name,
            "e3_gene": inherited["construct"].e3_gene,
            "peptide_id": row["peptide_id"],
            "peptide_sequence": row["sequence"],
            "peptide_gene": row.get("gene"),
            "parent_peptide_id": parent_id,
            "parent_pair_id": inherited["pair_id"],
            "ligand": inherited["ligand"].to_dict(),
            "jobs": len(pair_jobs),
        })

    issues = validate(jobs)
    return {
        "pairs": pairs,
        "jobs": jobs,
        "unroutable": unroutable,
        "jobs_per_pair": jobs_per_pair(),
        "issues": [issue.to_dict() for issue in issues],
        "errors": sum(1 for issue in issues if issue.severity == "error"),
        "warnings": sum(1 for issue in issues if issue.severity == "warning"),
    }
