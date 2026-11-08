"""Turn a planned scan into a runnable campaign (DESIGN_ARM.md).

The parent is re-run alongside its variants rather than reused from an
earlier campaign. That costs 15 jobs out of 240, about 6 per cent, and buys
the one thing design lift depends on: parent and variant measured under
identical settings, pockets, seeds and tier. Reusing a parent scored in a
different campaign would be the same subtraction across two sets of
conditions, which is the error `lift.compute` refuses at scoring time. It
is cheaper to make the refusal impossible than to hit it after the compute.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from nobble import paths
from nobble.curate import constructs as C
from nobble.curate import ligands as L
from nobble.curate import manifest as M
from nobble.curate import peptides as P
from nobble.design import variants as variant_module
from nobble.execute import yaml_gen as Y


def _peptide_from_row(row: dict) -> P.Peptide:
    return P.Peptide(**{k: v for k, v in row.items() if k != "length"})


def build_manifest(parent_id: str, generator: str = "alanine_scan",
                   positions: list[int] | None = None) -> dict:
    """Parent plus variants, routed to the parent's receptor and glue."""
    from nobble.curate import library as library_module

    library = library_module.load()
    if library is None:
        return {"status": "no library manifest", "jobs": [], "pairs": []}

    rows = {row["peptide_id"]: row for row in library["peptides"]}
    parent_row = rows.get(parent_id)
    if parent_row is None:
        return {"status": f"parent {parent_id} is not in the library",
                "jobs": [], "pairs": []}
    if parent_row.get("label") not in ("degraded",):
        return {"status": f"parent {parent_id} has no experimental label: a "
                          "scan against it would have no zero",
                "jobs": [], "pairs": []}

    parent = _peptide_from_row(parent_row)

    # Route exactly as the main campaign routes this peptide, so the design
    # campaign cannot drift from it.
    campaign_manifest = M.build_campaign_manifest(library=library["peptides"])
    parent_pair = next(
        (pair for pair in campaign_manifest["pairs"]
         if pair["peptide_id"] == parent_id), None)
    if parent_pair is None:
        return {"status": f"parent {parent_id} is not routed in the main campaign",
                "jobs": [], "pairs": []}

    construct = C.by_name(parent_pair["construct"])
    ligand_dict = parent_pair.get("ligand") or {}
    if ligand_dict.get("ccd"):
        ligand = L.by_ccd(ligand_dict["ccd"], modality=ligand_dict.get("modality", "glue"))
    elif ligand_dict.get("smiles"):
        ligand = L.by_smiles(ligand_dict["smiles"], key=ligand_dict.get("key", "parent"),
                             modality=ligand_dict.get("modality", "glue"))
    else:
        return {"status": f"parent {parent_id} has no ligand: there is no glue "
                          "dependence to design against",
                "jobs": [], "pairs": []}

    # The parent's cofactor decision, inherited by every variant. A scan
    # mutates coordinating residues, so inferring per variant would drop the
    # ion at exactly the positions the scan exists to measure (D-NOB-038).
    parent_cofactor = P.requires_structural_zinc(parent)

    generated = variant_module.generate(parent_id, parent_row["sequence"],
                                        generator=generator, positions=positions)

    jobs = []
    pairs = []

    parent_pair_id = f"design_parent_{parent_row.get('gene') or parent_id[-6:]}"
    parent_jobs = M.expand_pair(parent_pair_id, "design", construct, parent, ligand)
    jobs.extend(parent_jobs)
    pairs.append({
        "pair_id": parent_pair_id, "tier": "design", "role": "parent",
        "construct": construct.name, "e3_gene": construct.e3_gene,
        "peptide_id": parent_id, "peptide_sequence": parent_row["sequence"],
        "peptide_gene": parent_row.get("gene"),
        "peptide_label": parent_row.get("label"),
        "ligand": ligand.to_dict(), "jobs": len(parent_jobs),
        "cofactor": parent_cofactor,
    })

    for variant in generated["variants"]:
        peptide = P.Peptide(
            peptide_id=variant["variant_id"],
            sequence=variant["sequence"],
            source="design",
            # No experimental label: that is the point. A design is a
            # question, and labelling it would smuggle an answer into the
            # set the weight fitter reads.
            label=None,
            accession=parent_row.get("accession"),
            gene=parent_row.get("gene"),
            start_res=parent_row.get("start_res"),
            end_res=parent_row.get("end_res"),
            degron_class=f"design_of_{parent_row.get('degron_class')}",
            e3_hint=parent_row.get("e3_hint"),
            parent_peptide_id=parent_id,
            cofactor=dict(parent_cofactor),
            notes=[f"{generator} variant {variant['substitution']} of {parent_id}"],
        )
        pair_id = f"design_{variant['substitution']}_{parent_row.get('gene') or ''}"
        pair_jobs = M.expand_pair(pair_id, "design", construct, peptide, ligand)
        jobs.extend(pair_jobs)
        pairs.append({
            "pair_id": pair_id, "tier": "design", "role": "variant",
            "construct": construct.name, "e3_gene": construct.e3_gene,
            "peptide_id": variant["variant_id"],
            "peptide_sequence": variant["sequence"],
            "peptide_gene": parent_row.get("gene"),
            "peptide_label": None,
            "parent_peptide_id": parent_id,
            "parent_pair_id": parent_pair_id,
            "substitution": variant["substitution"],
            "position": variant["position"],
            "ligand": ligand.to_dict(), "jobs": len(pair_jobs),
            "cofactor": parent_cofactor,
        })

    issues = M.validate(jobs)
    return {
        "parent": parent_id,
        "parent_sequence": parent_row["sequence"],
        "generator": generator,
        "pairs": pairs,
        "jobs": jobs,
        "unroutable": [],
        "jobs_per_pair": M.jobs_per_pair(),
        "issues": [issue.to_dict() for issue in issues],
        "errors": sum(1 for issue in issues if issue.severity == "error"),
        "warnings": sum(1 for issue in issues if issue.severity == "warning"),
        "peptides": {row["peptide_id"]: row for row in [parent_row]},
    }


def parent_provenance(parent_id: str, scored_campaign: str | None = None) -> dict:
    """Why this parent, recorded with the campaign it produced (F338).

    `scored_campaign` is the campaign to rank against, and it matters more
    than it looks. `report.build` reads whatever `nobble.app.data` is
    configured to, which is global state: called with nothing configured it
    ranked against a different campaign and preferred a different peptide,
    so a check written on top of it refused the correct parent. Found by
    running it both ways rather than only the way that was convenient.

    Passing None keeps whatever the caller configured, which is what the
    assembler wants: it records what the ranking said in the process that
    assembled the campaign, and that process is the chain's own, which
    configures the main campaign first.

    `report.build`'s preview chooses a parent two ways and says which in
    `chosen_because`: by largest measured Delta-ipTM over the scored
    parents, or, when nothing is scored, by a fallback whose own wording is
    "a scan chosen this way has not been ranked against anything". The two
    produce an identical `campaign.json`, because the summary records
    `parent` and not the reason, so nothing downstream can tell a parent
    ranked against 158 pairs from one that was not ranked at all.

    That distinction is the entire reason `tools/run_chain.sh` queues the
    scan last and re-assembles it against the full campaign, and on
    2026-11-08 the campaign on disk was assembled before scoring while the
    ranked answer happened to agree: the same parent for a different
    reason, which is luck and not provenance.

    Derived here rather than passed in, because the caller is inline Python
    inside `run_chain.sh` and that file cannot be edited while the chain is
    executing it (F308). Imported inside the function: `nobble.design.report`
    imports the app's data layer, and importing that at module scope would
    make the assembler depend on it to emit a queue.

    A failure to determine it is recorded as a failure. Returning `{}` would
    make "nobody asked" and "asked and could not tell" the same record,
    which is F321 to F324.
    """
    try:
        from nobble.app import data
        from nobble.design import report

        if scored_campaign:
            data.configure(str(scored_campaign))
        preview = (report.build().get("preview") or {})
        parent = preview.get("parent") or {}
    except Exception as problem:                        # noqa: BLE001
        return {"status": f"could not be determined "
                          f"({type(problem).__name__}: {problem})"}
    if not parent:
        return {"status": "report.build() offered no parent, so this "
                          "campaign's parent was chosen by its caller and "
                          "the reason is not recorded here"}
    if str(parent.get("peptide_id")) != str(parent_id):
        return {"status": f"the ranking now prefers "
                          f"{parent.get('peptide_id')}, so {parent_id} was "
                          "not the ranked choice at the time this ran",
                "ranked_choice": parent.get("peptide_id"),
                "ranked_because": parent.get("chosen_because")}
    return {"chosen_because": parent.get("chosen_because"),
            "ranked_against": str(scored_campaign) if scored_campaign else None,
            "ranked": "largest measured delta-ipTM" in str(
                parent.get("chosen_because") or "")}


def assemble(parent_id: str, generator: str = "alanine_scan",
             positions: list[int] | None = None) -> dict:
    """Emit a runnable design campaign directory."""
    manifest = build_manifest(parent_id, generator, positions)
    if manifest.get("status"):
        return manifest
    if manifest["errors"]:
        raise RuntimeError(f"{manifest['errors']} manifest validation errors")

    # One pocket serves the whole campaign because every pair shares the
    # parent's receptor and glue by construction. That has been stated in a
    # comment here and never checked: the pocket is derived from pairs[0], so
    # a variant routed to a different glue would have been given the parent's
    # pocket instead (F42). Checked before any work, since there is nothing to
    # assemble if it fails.
    ligands = sorted({(pair.get("ligand") or {}).get("ccd")
                      for pair in manifest["pairs"]})
    if len(ligands) > 1:
        raise RuntimeError(
            "the design scan's pairs do not share one glue "
            f"({', '.join(str(c) for c in ligands)}): a single pocket cannot "
            "describe them, so the campaign is not assembled"
        )

    from nobble.execute.campaign import fresh_campaign

    with fresh_campaign("design") as directory:
        pair_by_id = {pair["pair_id"]: pair for pair in manifest["pairs"]}
        peptide_by_id: dict[str, P.Peptide] = {}
        for pair in manifest["pairs"]:
            if pair["role"] == "parent":
                peptide_by_id[pair["peptide_id"]] = _peptide_from_row(
                    manifest["peptides"][pair["peptide_id"]])
                peptide_by_id[pair["peptide_id"]].cofactor = dict(pair["cofactor"])
            else:
                peptide_by_id[pair["peptide_id"]] = P.Peptide(
                    peptide_id=pair["peptide_id"], sequence=pair["peptide_sequence"],
                    source="design", label=None, accession=None,
                    gene=pair["peptide_gene"], start_res=None, end_res=None,
                    degron_class="design", e3_hint=pair["e3_gene"],
                    parent_peptide_id=pair.get("parent_peptide_id"),
                    cofactor=dict(pair["cofactor"]),
                )

        first = manifest["pairs"][0]
        ccd = (first.get("ligand") or {}).get("ccd")
        pdb_id = None
        from nobble.execute.campaign import IMID_POCKET_SOURCE
        member = next((m for m in P.BENCHMARK_CHAINS
                       if m["ligand"] == ccd), None)
        if member:
            pdb_id = member["pdb_id"]
        elif ccd:
            pdb_id = IMID_POCKET_SOURCE.get(ccd)
        pocket = None
        if pdb_id and ccd:
            pocket = Y.derive_pocket(C.by_name(first["construct"]), pdb_id, ccd,
                                     first["e3_gene"])

        queue_path = directory / "queue.jsonl"
        written = 0
        dropped = 0
        with queue_path.open("w") as queue:
            for job in manifest["jobs"]:
                pair = pair_by_id[job.pair_id]
                peptide = peptide_by_id[job.peptide_id]
                ligand_dict = pair["ligand"]
                if ligand_dict.get("ccd"):
                    ligand = L.by_ccd(ligand_dict["ccd"],
                                      modality=ligand_dict.get("modality", "glue"))
                else:
                    ligand = L.by_smiles(ligand_dict["smiles"],
                                         key=ligand_dict.get("key", "parent"),
                                         modality=ligand_dict.get("modality", "glue"))
                if job.conditioning == "conditioned" and pocket is None:
                    dropped += 1
                    continue
                document = Y.build_yaml(job, peptide, ligand, pocket)
                yaml_path = directory / "yaml" / f"{job.job_id}.yaml"
                yaml_path.write_text(Y.to_yaml_text(document))
                record = job.to_dict()
                record["yaml"] = str(yaml_path)
                record["role"] = pair["role"]
                record["substitution"] = pair.get("substitution")
                record["position"] = pair.get("position")
                record["parent_peptide_id"] = pair.get("parent_peptide_id")
                record["pocket_residues"] = pocket.positions if pocket else None
                queue.write(json.dumps(record) + "\n")
                written += 1

        summary = {
            "campaign_id": directory.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "parent": parent_id,
            "parent_sequence": manifest["parent_sequence"],
            "generator": generator,
            "pairs": len(manifest["pairs"]),
            "variants": len(manifest["pairs"]) - 1,
            "jobs_emitted": written,
            "conditioned_jobs_dropped_no_pocket": dropped,
            "pocket": pocket.positions if pocket else None,
            "cofactor": first.get("cofactor"),
            # Why this parent, not only which (F338).
            "parent_provenance": parent_provenance(parent_id),
            "note": (
                "The parent is re-run here rather than reused from an earlier "
                "campaign, so design lift subtracts two numbers measured under "
                "identical settings. Every variant inherits the parent's "
                "cofactor decision (D-NOB-038)."
            ),
        }
        (directory / "campaign.json").write_text(json.dumps(summary, indent=2, default=str))
        return {"path": str(directory), **summary}
