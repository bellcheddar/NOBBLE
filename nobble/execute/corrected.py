"""The corrected-construct benchmark campaign (D-NOB-027, FINDINGS.md F6).

F6 is a hypothesis with an obvious experiment attached, and this runs it.

The claim: six of the seven benchmark pairs failed to recover their crystal
pose because their substrate was submitted as a 15-mer cut out of a folded
domain, which cannot fold and so cannot present the surface the intact domain
presents. The one pair that worked, IKZF1, is the one whose epitope is linear.

The test: re-run the panel with each domain-mediated substrate submitted as its
**whole domain**, change nothing else, and compare pose recovery against the
same deposited structures. If F6 is right, the pairs that sat at 19 to 29
angstrom should move towards IKZF1's 5. If they do not, F6 is wrong and the
problem is the model rather than the construct, which is equally worth knowing
and would redirect the whole campaign.

IKZF1 keeps its 15-mer and acts as the internal control: it already works, and
its number should not move.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from nobble import paths
from nobble.curate import constructs as C
from nobble.curate import ligands as L
from nobble.curate import manifest as M
from nobble.curate import numbering
from nobble.curate import peptides as P
from nobble.execute import msa as msa_module
from nobble.execute import yaml_gen as Y

# The manifest's, not a second copy. Two tuples drifting apart would have
# emitted a corrected campaign with a different seed count from the
# benchmark it is compared against, and the comparison's whole point is
# that one variable changed (F91).
from nobble.curate.manifest import SEEDS


def substrate_chain(plan: dict) -> dict:
    """The substrate as it will be submitted, with its MSA decision explained."""
    substrate = plan["substrate"]
    if substrate["mode"] == "folded_domain":
        sequence = numbering.canonical_sequence(substrate["accession"])[
            substrate["start"] - 1 : substrate["end"]
        ]
        cached = msa_module.is_cached(sequence)
        return {
            "sequence": sequence,
            "start": substrate["start"],
            "end": substrate["end"],
            "mode": "folded_domain",
            # A folded domain is a protein chain, not a peptide: spec 1.3's
            # "peptides get no MSA" does not apply, and running it without one
            # would handicap the arm this experiment exists to test.
            "msa": str(msa_module.a3m_path(sequence)) if cached else msa_module.EMPTY,
            "msa_cached": cached,
        }
    peptide = next(
        (item for item in P.benchmark_peptides()
         if item.gene == plan["gene"] and item.e3_hint == plan["e3"]), None
    )
    return {
        "sequence": peptide.sequence if peptide else "",
        "start": peptide.start_res if peptide else None,
        "end": peptide.end_res if peptide else None,
        "mode": "peptide_15mer",
        "msa": msa_module.EMPTY,
        "msa_cached": False,
    }


def build_yaml(construct, substrate: dict, ligand, pocket, complex_type: str,
               conditioning: str) -> dict:
    """Same topology as the tier-1 YAMLs, with the substrate chain widened."""
    sequences: list[dict] = []
    for index, segment in enumerate(construct.segments):
        sequence = segment.sequence()
        chain_id = Y.RECEPTOR_CHAINS[index]
        sequences.append({"protein": {
            "id": chain_id,
            "sequence": sequence,
            "msa": (str(msa_module.a3m_path(sequence))
                    if msa_module.is_cached(sequence) else msa_module.EMPTY),
        }})

    sequences.append({"protein": {
        "id": Y.PEPTIDE_CHAIN,
        "sequence": substrate["sequence"],
        "msa": substrate["msa"],
    }})

    document: dict = {"version": 1, "sequences": sequences}

    if complex_type == "ternary" and ligand is not None:
        entry: dict = {"id": Y.LIGAND_CHAIN}
        if ligand.encoding == "ccd":
            entry["ccd"] = ligand.ccd
        else:
            entry["smiles"] = ligand.smiles
        sequences.append({"ligand": entry})
        if conditioning == "conditioned" and pocket is not None:
            document["constraints"] = [pocket.to_yaml_fragment()]
        if ligand.affinity_available:
            document["properties"] = [{"affinity": {"binder": Y.LIGAND_CHAIN}}]
    return document


def _substrate_plans() -> list[dict]:
    """The substrate plan this assembly is working from.

    Separate so the recorded plan is the one the YAMLs were written from
    rather than a second call that could resolve differently (F94).
    """
    from nobble.curate import peptides as peptide_module

    try:
        return list(peptide_module.benchmark_substrate_constructs())
    except Exception:                                   # noqa: BLE001
        return []


def assemble() -> dict:
    """Emit the corrected campaign. Same axes as tier 1: 15 jobs per pair."""
    from nobble.execute.campaign import fresh_campaign

    with fresh_campaign("corrected") as directory:
        ligand_map = L.benchmark_ligands()
        member_by_index = {item["index"]: item for item in P.BENCHMARK_CHAINS}
        cap = int(paths.thresholds()["manifest"]["token_cap_tier1"])

        pairs, written = [], 0
        with (directory / "queue.jsonl").open("w") as queue:
            for plan in P.benchmark_substrate_constructs():
                member = member_by_index[plan["member"]]
                construct_name = M.E3_TO_CONSTRUCT.get(member["e3"])
                if not construct_name:
                    continue
                construct = C.by_name(construct_name)
                ligand = ligand_map.get(member["index"])
                substrate = substrate_chain(plan)
                if not substrate["sequence"]:
                    continue

                ccd = ligand.ccd if ligand and ligand.encoding == "ccd" else None
                pocket = Y.derive_pocket(construct, member["pdb_id"], ccd, member["e3"])
                pair_id = f"corr{member['index']:02d}_{member['gene']}_{member['e3']}"

                for complex_type in ("binary", "ternary"):
                    if complex_type == "ternary" and ligand is None:
                        continue
                    conditions = (("conditioned", "unconstrained")
                                  if complex_type == "ternary" else ("unconstrained",))
                    for conditioning in conditions:
                        if conditioning == "conditioned" and pocket is None:
                            continue
                        for seed in SEEDS:
                            job_id = f"{pair_id}__{complex_type}__{conditioning}__seed{seed}"
                            document = build_yaml(construct, substrate, ligand, pocket,
                                                  complex_type, conditioning)
                            path = directory / "yaml" / f"{job_id}.yaml"
                            path.write_text(Y.to_yaml_text(document))

                            tokens = (construct.residue_count() + len(substrate["sequence"])
                                      + ((ligand.heavy_atoms or 0)
                                         if complex_type == "ternary" and ligand else 0))
                            queue.write(json.dumps({
                                "job_id": job_id, "pair_id": pair_id, "tier": "corrected",
                                "construct": construct.name, "e3_gene": construct.e3_gene,
                                "peptide_id": f"{member['gene']}_{substrate['mode']}",
                                "peptide_sequence": substrate["sequence"],
                                "peptide_gene": member["gene"],
                                "peptide_label": "degraded",
                                "peptide_accession": plan["substrate"]["accession"],
                                "peptide_start_res": substrate["start"],
                                "peptide_end_res": substrate["end"],
                                "ligand_key": ligand.key if (ligand and complex_type == "ternary") else None,
                                "ligand_encoding": (ligand.encoding if (ligand and complex_type == "ternary") else None),
                                "modality": ligand.modality if ligand else "none",
                                "complex_type": complex_type, "conditioning": conditioning,
                                "seed": seed, "tokens": tokens,
                                "affinity_available": bool(
                                    ligand and complex_type == "ternary" and ligand.affinity_available),
                                "required_modification": None,
                                "substrate_mode": substrate["mode"],
                                "substrate_msa_cached": substrate["msa_cached"],
                                "flags": (["token_cap_declared_exception"]
                                          if tokens > cap else []),
                                "yaml": str(path),
                                "pocket_residues": pocket.positions if pocket else None,
                            }) + "\n")
                            written += 1

                pairs.append({
                    "pair_id": pair_id, "member": member["index"], "gene": member["gene"],
                    "e3": member["e3"], "substrate_mode": substrate["mode"],
                    "substrate_length": len(substrate["sequence"]),
                    "substrate_msa_cached": substrate["msa_cached"],
                    "tokens": plan["tokens"], "within_cap": plan["within_cap"],
                    "declared_exception": plan["declared_exception"],
                })

        summary = {
            "campaign_id": directory.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "purpose": (
                "Tests FINDINGS.md F6: whether submitting a domain-mediated "
                "substrate as its whole domain recovers the crystal pose that a "
                "15-mer cut from the same domain did not. IKZF1 keeps its 15-mer "
                "as the internal control and its number should not move."
            ),
            # Both keys, matching the benchmark builder: `pairs` as a count and
            # the records under `pair_detail`, plus the records under `pairs` for
            # anything already reading that.
            "pairs": pairs, "pair_count": len(pairs), "pair_detail": pairs,
            "jobs_emitted": written,
            "compare_against": "the tier-1 benchmark campaign, same deposited structures",
            # Which domain each substrate actually was, recorded rather than
            # recomputed later. The boundaries come from an InterPro lookup
            # and move when ambiguous-entry resolution is fixed, so a
            # campaign that records only its job count cannot be checked
            # against the plan it ran under: corr05's CSNK1A1 domain moved
            # from 269 residues to 219 and nothing noticed, while the
            # published plan beside the result described the newer one
            # (F93, F94).
            # Keys read from the plan rather than guessed: the gene and the
            # E3 are top level and the domain is under `substrate`, which
            # also carries the InterPro entry the boundary came from. That
            # entry is the thing that moves, so recording it is the point.
            "substrate_plan": [
                {
                    "gene": plan.get("gene"),
                    "e3": plan.get("e3"),
                    "mode": (plan.get("substrate") or {}).get("mode"),
                    "accession": (plan.get("substrate") or {}).get("accession"),
                    "interpro": (plan.get("substrate") or {}).get("interpro"),
                    "start": (plan.get("substrate") or {}).get("start"),
                    "end": (plan.get("substrate") or {}).get("end"),
                    "length": (plan.get("substrate") or {}).get("length"),
                }
                for plan in _substrate_plans()
            ],
        }
        (directory / "campaign.json").write_text(json.dumps(summary, indent=2, default=str))
        return {"path": str(directory), **summary}
