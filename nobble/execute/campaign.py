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

import contextlib
import json
import re
import shutil
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


# campaign_id() stamps a UTC timestamp, so a real campaign directory always
# ends in one. Matching the prefix alone let any sibling with the same prefix
# shadow the real thing: a scratch directory named campaign_smoke sorts after
# campaign_20261104T004632Z, because "s" sorts after "2", and silently became
# "the latest campaign".
TIMESTAMP = re.compile(r"^\d{8}T\d{6}Z$")

# Written last by every assembler, after the queue and the YAMLs, so its
# presence is what distinguishes a campaign from a directory an assembler
# was part way through building. An assembly that raises leaves the skeleton
# behind, and three of those from a failing design scan sat in campaigns/
# looking exactly like campaigns that had run and produced nothing. Sorting
# last by name, the newest of them would have been "the latest" (F57).
COMPLETION_MARKER = "campaign.json"


def latest(prefix: str = "benchmark") -> Path | None:
    """Most recent complete campaign directory with this prefix, or None.

    Complete, not merely present. Four of this function's callers use what
    it returns without checking anything further, so the check belongs here
    rather than at each of them.
    """
    candidates = sorted(
        (item for item in paths.CAMPAIGNS.iterdir()
         if item.is_dir()
         and item.name.startswith(f"{prefix}_")
         and TIMESTAMP.match(item.name[len(prefix) + 1:])
         and (item / COMPLETION_MARKER).exists()),
        key=lambda item: item.name,
    )
    return candidates[-1] if candidates else None


@contextlib.contextmanager
def fresh_campaign(prefix: str):
    """A campaign directory that does not outlive a failed assembly.

    Every assembler creates `yaml/` and `outputs/` and then does work that
    can raise: a pocket it cannot derive, a peptide row it cannot parse. The
    directory it had already created stayed behind under a campaign name,
    holding two empty subdirectories and nothing else, which is
    indistinguishable from a campaign that ran and produced no results.
    Three of those accumulated from a failing design scan.

    A directory that leaves this block without its completion marker is
    removed. A process killed mid-assembly can still leave one, which is
    why `latest()` checks the marker as well: this handles the failure that
    actually happened, and that handles the one that cannot be caught.
    """
    directory = paths.CAMPAIGNS / campaign_id(prefix)
    (directory / "yaml").mkdir(parents=True, exist_ok=True)
    (directory / "outputs").mkdir(parents=True, exist_ok=True)
    try:
        yield directory
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    if not (directory / COMPLETION_MARKER).exists():
        shutil.rmtree(directory, ignore_errors=True)
        raise RuntimeError(
            f"{directory.name} finished assembling without writing "
            f"{COMPLETION_MARKER}: removed rather than left looking complete"
        )


def assemble_benchmark(reuse_latest: bool = True) -> dict:
    """Emit the benchmark campaign. Idempotent: reuses the latest by default."""
    if reuse_latest:
        existing = latest("benchmark")
        if existing:
            summary = json.loads((existing / "campaign.json").read_text())
            return {"path": str(existing), "reused": True, **summary}

    manifest = M.build_benchmark_manifest()
    if manifest["errors"]:
        raise RuntimeError(
            f"{manifest['errors']} manifest validation errors: refusing to emit a "
            "campaign. See data/manifests/benchmark.summary.json"
        )

    with fresh_campaign("benchmark") as directory:
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


# Where each IMiD's CRBN pocket is measured from. Both are benchmark panel
# depositions, so the pocket the Sievers arm is conditioned on is the same
# pocket the positive controls were conditioned on: if the pocket is wrong,
# the benchmark says so before the arm does.
IMID_POCKET_SOURCE = {
    "Y70": "6H0F",   # S-pomalidomide, CRBN-DDB1-IKZF1 ZF2
    "LVY": "5FQD",   # S-lenalidomide, CRBN-DDB1-CSNK1A1
}


def assemble_campaign(reuse_latest: bool = True) -> dict:
    """Emit the main campaign: benchmark panel, Sievers arm and scrambles.

    Pockets are measured once per (construct, ligand) rather than once per
    pair. Every Sievers pair shares CRBN_CULT and one of two IMiDs, so 120
    pairs need two pocket measurements, not 120, and measuring them per pair
    would invite 120 chances to disagree about the same pocket.
    """
    if reuse_latest:
        existing = latest("campaign")
        if existing:
            summary = json.loads((existing / "campaign.json").read_text())
            return {"path": str(existing), "reused": True, **summary}

    from nobble.curate import library as LM

    library = LM.load()
    if library is None:
        raise RuntimeError(
            "no library manifest: run nobble.curate.library before assembling"
        )

    manifest = M.build_campaign_manifest(library=library["peptides"])
    if manifest["errors"]:
        raise RuntimeError(
            f"{manifest['errors']} manifest validation errors: refusing to emit a "
            "campaign. See data/manifests/campaign.summary.json"
        )

    with fresh_campaign("campaign") as directory:
        rows = {row["peptide_id"]: row for row in library["peptides"]}
        pair_by_id = {pair["pair_id"]: pair for pair in manifest["pairs"]}
        ligand_by_index = L.benchmark_ligands()
        member_by_pair = {
            f"bench{item['index']:02d}_{item['gene']}_{item['e3']}": item
            for item in P.BENCHMARK_CHAINS
        }

        # Pocket cache keyed by (construct, ligand ccd or smiles key).
        pocket_cache: dict[tuple, Y.PocketConstraint | None] = {}

        def _pocket_for(pair: dict) -> Y.PocketConstraint | None:
            construct_name = pair["construct"]
            ligand = pair.get("ligand") or {}
            ccd = ligand.get("ccd")
            key = (construct_name, ccd or ligand.get("key"))
            if key in pocket_cache:
                return pocket_cache[key]

            member = member_by_pair.get(pair["pair_id"])
            if member is not None:
                pdb_id = member["pdb_id"]
            else:
                pdb_id = IMID_POCKET_SOURCE.get(ccd)
            pocket = None
            if pdb_id and ccd:
                pocket = Y.derive_pocket(
                    C.CONSTRUCTS[construct_name], pdb_id, ccd,
                    pair.get("e3_gene") or "",
                )
            pocket_cache[key] = pocket
            return pocket

        queue_path = directory / "queue.jsonl"
        written = 0
        skipped_conditioned = 0
        with queue_path.open("w") as queue:
            for job in manifest["jobs"]:
                pair = pair_by_id.get(job.pair_id)
                row = rows.get(job.peptide_id)
                if pair is None or row is None:
                    continue
                peptide = P.Peptide(**{k: v for k, v in row.items() if k != "length"})

                member = member_by_pair.get(job.pair_id)
                if member is not None:
                    ligand = ligand_by_index.get(member["index"])
                else:
                    ccd = (pair.get("ligand") or {}).get("ccd")
                    ligand = L.by_ccd(ccd, modality="glue") if ccd else None

                pocket = _pocket_for(pair)
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

        by_tier: dict[str, int] = {}
        for pair in manifest["pairs"]:
            by_tier[pair["tier"]] = by_tier.get(pair["tier"], 0) + 1

        summary = {
            "campaign_id": directory.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "pairs": len(manifest["pairs"]),
            "pairs_by_tier": by_tier,
            "jobs_emitted": written,
            "jobs_per_pair": manifest["jobs_per_pair"],
            "conditioned_jobs_dropped_no_pocket": skipped_conditioned,
            "manifest_warnings": manifest["warnings"],
            "unroutable": manifest["unroutable"],
            "tuning": paths.tuning()["campaign"],
            "pockets": {
                f"{construct}/{ligand}": (pocket.positions if pocket else None)
                for (construct, ligand), pocket in pocket_cache.items()
            },
            "imid_pocket_sources": IMID_POCKET_SOURCE,
        }
        (directory / "campaign.json").write_text(json.dumps(summary, indent=2, default=str))
        return {"path": str(directory), "reused": False, **summary}
