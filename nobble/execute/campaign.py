"""Campaign assembly: emit one Boltz YAML per job and a resumable queue.

A campaign directory is self-contained, so a run can be inspected, resumed or
re-run without reference to the code that produced it:

    campaigns/<campaign_id>/
      campaign.json      the manifest summary and the settings used
      yaml/<job_id>.yaml  one input per inference
      queue.jsonl         the job queue in priority order
      outputs/<job_id>/   whatever Boltz writes
      results.jsonl       one parsed record per completed job
      state.jsonl         per-job checkpoints, append-only
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from nobble import paths
from nobble.curate import constructs as C
from nobble.curate import ligands as L
from nobble.curate import manifest as M
from nobble.curate import peptides as P
from nobble.execute import yaml_gen as Y


def campaign_id(prefix: str = "benchmark") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{stamp}"


def latest(prefix: str = "benchmark") -> Path | None:
    """Most recent campaign directory with this prefix, or None."""
    candidates = sorted(
        (item for item in paths.CAMPAIGNS.iterdir()
         if item.is_dir() and item.name.startswith(f"{prefix}_")),
        key=lambda item: item.name,
    )
    return candidates[-1] if candidates else None


def assemble_benchmark(reuse_latest: bool = True) -> dict:
    """Emit the benchmark campaign. Idempotent: reuses the latest by default."""
    if reuse_latest:
        existing = latest("benchmark")
        if existing and (existing / "queue.jsonl").exists():
            summary = json.loads((existing / "campaign.json").read_text())
            return {"path": str(existing), "reused": True, **summary}

    manifest = M.build_benchmark_manifest()
    if manifest["errors"]:
        raise RuntimeError(
            f"{manifest['errors']} manifest validation errors: refusing to emit a "
            "campaign. See data/manifests/benchmark.summary.json"
        )

    directory = paths.CAMPAIGNS / campaign_id("benchmark")
    (directory / "yaml").mkdir(parents=True, exist_ok=True)
    (directory / "outputs").mkdir(parents=True, exist_ok=True)

    peptide_by_id = {item.peptide_id: item for item in P.benchmark_peptides()}
    ligand_by_index = L.benchmark_ligands()
    member_by_pair = {
        f"bench{item['index']:02d}_{item['gene']}_{item['e3']}": item
        for item in P.BENCHMARK_CHAINS
    }

    # Pockets are measured once per pair, not once per job.
    pocket_cache: dict[str, Y.PocketConstraint | None] = {}
    for pair_id, member in member_by_pair.items():
        construct_name = M.E3_TO_CONSTRUCT.get(member["e3"])
        if not construct_name:
            continue
        ligand = ligand_by_index.get(member["index"])
        ccd = ligand.ccd if ligand and ligand.encoding == "ccd" else None
        pocket_cache[pair_id] = Y.derive_pocket(
            C.CONSTRUCTS[construct_name], member["pdb_id"], ccd, member["e3"]
        )

    queue_path = directory / "queue.jsonl"
    written = 0
    skipped_conditioned = 0
    with queue_path.open("w") as queue:
        for job in manifest["jobs"]:
            peptide = peptide_by_id.get(job.peptide_id)
            member = member_by_pair.get(job.pair_id)
            if peptide is None or member is None:
                continue
            ligand = ligand_by_index.get(member["index"])
            pocket = pocket_cache.get(job.pair_id)

            # A conditioned job without a measurable pocket is not a conditioned
            # job. Emitting it would duplicate the unconstrained arm and quietly
            # destroy the agreement signal spec 4.7 depends on, so it is dropped
            # and counted.
            if job.conditioning == "conditioned" and pocket is None:
                skipped_conditioned += 1
                continue

            document = Y.build_yaml(job, peptide, ligand, pocket)
            yaml_path = directory / "yaml" / f"{job.job_id}.yaml"
            yaml_path.write_text(Y.to_yaml_text(document))

            record = job.to_dict()
            record["yaml"] = str(yaml_path)
            record["pocket_residues"] = pocket.positions if pocket else None
            record["pocket_provenance"] = pocket.provenance if pocket else None
            queue.write(json.dumps(record) + "\n")
            written += 1

    summary = {
        "campaign_id": directory.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pairs": len(manifest["pairs"]),
        "jobs_emitted": written,
        "jobs_per_pair": manifest["jobs_per_pair"],
        "conditioned_jobs_dropped_no_pocket": skipped_conditioned,
        "manifest_warnings": manifest["warnings"],
        "pair_detail": manifest["pairs"],
        "tuning": paths.tuning()["campaign"],
        "pockets": {
            pair_id: (pocket.positions if pocket else None)
            for pair_id, pocket in pocket_cache.items()
        },
    }
    (directory / "campaign.json").write_text(json.dumps(summary, indent=2, default=str))
    return {"path": str(directory), "reused": False, **summary}
