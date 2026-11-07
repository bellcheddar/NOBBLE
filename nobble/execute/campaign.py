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
from nobble.execute import software
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


def latest_or_absent(prefix: str = "benchmark") -> Path:
    """`latest`, but a path that does not exist rather than None.

    For callers that resolve a campaign at import time and then guard on
    `.exists()`, which is how the test suite reads the campaigns on disk.
    Eighteen test files named a campaign directory by its timestamp, so
    they went quiet rather than failing the moment that campaign was
    superseded or pruned: the check still ran, found nothing, and skipped.
    That is F190's lesson, which fixed the same thing in the shell, and
    F195's, which is that a step reporting success for work it did not do
    is worse than one that fails.

    Returning a missing path rather than raising keeps every one of those
    `.exists()` guards meaningful: with no campaign of this prefix the
    tests skip as they always did, and with one they use the newest
    complete one instead of a name frozen into the file.
    """
    found = latest(prefix)
    return found if found is not None else paths.CAMPAIGNS / f"_no_{prefix}_campaign"


# Appended to, never rewritten: a failed assembly is an event, and the
# previous failure is the context for the next one. Three identical
# skeletons 20 minutes apart said more together than any one of them did.
FAILED_ASSEMBLIES = paths.MANIFESTS / "failed_assemblies.jsonl"


def _record_failed_assembly(directory: Path, error: BaseException) -> None:
    """Write down why a campaign directory is about to be removed."""
    import traceback

    contents = []
    try:
        contents = sorted(
            str(item.relative_to(directory)) for item in directory.rglob("*"))
    except Exception:                                           # noqa: BLE001
        pass
    record = {
        "campaign_id": directory.name,
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "error": type(error).__name__,
        "message": str(error),
        "traceback": "".join(
            traceback.format_exception(type(error), error,
                                       error.__traceback__)),
        "contents": contents,
    }
    try:
        FAILED_ASSEMBLIES.parent.mkdir(parents=True, exist_ok=True)
        with FAILED_ASSEMBLIES.open("a") as handle:
            handle.write(json.dumps(record) + "\n")
    except Exception:                                           # noqa: BLE001
        # Losing the record must not mask the error it describes, and the
        # ways a path can fail are not all OSError: a bad FAILED_ASSEMBLIES
        # raises ValueError from pathlib before any I/O is attempted, which
        # a narrower clause let through and on top of the real failure.
        pass


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

    The reason is recorded before the directory goes. The three skeletons
    that prompted this carried no record of why they failed, so the cause
    had to be guessed at afterwards and could not be confirmed. Removing
    them without writing the traceback down would have replaced litter with
    nothing at all, which is quieter and no more informative.
    """
    directory = paths.CAMPAIGNS / campaign_id(prefix)
    (directory / "yaml").mkdir(parents=True, exist_ok=True)
    (directory / "outputs").mkdir(parents=True, exist_ok=True)
    try:
        yield directory
    except BaseException as error:
        _record_failed_assembly(directory, error)
        shutil.rmtree(directory, ignore_errors=True)
        raise
    if not (directory / COMPLETION_MARKER).exists():
        error = RuntimeError(
            f"{directory.name} finished assembling without writing "
            f"{COMPLETION_MARKER}: removed rather than left looking complete"
        )
        _record_failed_assembly(directory, error)
        shutil.rmtree(directory, ignore_errors=True)
        raise error


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
                C.by_name(construct_name), member["pdb_id"], ccd, member["e3"]
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
            # Which Boltz will produce the coordinates. Recorded at
            # assembly, because that is when the environment is the one the
            # queue will run in, and because every number the atlas
            # publishes is a prediction from this version: the tuning on the
            # line above was already recorded and the model was not (F185).
            "software": software.versions(),
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


def assemble_tier_b(reuse_latest: bool = True) -> dict:
    """Emit the Tier B arm: eleven unproven ligases against proven pairs.

    The design is D-NOB-073's and the manifest is
    `M.build_tier_b_manifest`. This turns it into a campaign directory.

    Simpler than the main campaign in one way and fiddlier in another. No
    pockets, because conditioning needs a pocket from the receptor's own
    deposited structure and these receptors have none, so every job is
    unconstrained and `build_yaml` gets `pocket=None`. But the ligand cannot
    be rebuilt from the pair's stored dict: dBET57 is SMILES-encoded with no
    CCD, so `by_ccd` cannot reconstruct it. Each Tier B pair records the
    benchmark pair it borrowed its glue and degron from, and the ligand is
    taken from there, which is the same reason `build_campaign_manifest`
    carries `benchmark_routing` rather than rebuilding.
    """
    if reuse_latest:
        existing = latest("tier_b")
        if existing:
            summary = json.loads((existing / "campaign.json").read_text())
            return {"path": str(existing), "reused": True, **summary}

    from nobble.curate import library as LM
    from nobble.curate import tier_b_constructs as T

    blocked = T.report()
    if not blocked["assemblable"]:
        raise RuntimeError(
            f"Tier B is not assemblable: {blocked['status']}. "
            "See config/tier_b_constructs.toml"
        )

    library = LM.load()
    if library is None:
        raise RuntimeError(
            "no library manifest: run nobble.curate.library before assembling"
        )

    manifest = M.build_tier_b_manifest(library=library["peptides"])
    if manifest.get("errors"):
        raise RuntimeError(
            f"{manifest['errors']} manifest validation error(s): refusing to "
            "emit the Tier B arm. See the issues in the manifest summary"
        )
    if not manifest["jobs"]:
        raise RuntimeError(f"Tier B manifest emitted no jobs: {manifest.get('status')}")

    with fresh_campaign("tier_b") as directory:
        rows = {row["peptide_id"]: row for row in library["peptides"]}
        pair_by_id = {pair["pair_id"]: pair for pair in manifest["pairs"]}
        ligand_by_index = L.benchmark_ligands()
        member_by_pair = {
            f"bench{item['index']:02d}_{item['gene']}_{item['e3']}": item
            for item in P.BENCHMARK_CHAINS
        }

        queue_path = directory / "queue.jsonl"
        written = 0
        with queue_path.open("w") as queue:
            for job in manifest["jobs"]:
                pair = pair_by_id.get(job.pair_id)
                row = rows.get(job.peptide_id)
                if pair is None or row is None:
                    continue
                peptide = P.Peptide(**{k: v for k, v in row.items() if k != "length"})

                # From the benchmark pair this one borrowed, so a
                # SMILES-encoded degrader survives the round trip.
                member = member_by_pair.get(pair.get("borrowed_from") or "")
                ligand = ligand_by_index.get(member["index"]) if member else None
                if ligand is None:
                    ccd = (pair.get("ligand") or {}).get("ccd")
                    ligand = L.by_ccd(ccd, modality="glue") if ccd else None

                document = Y.build_yaml(job, peptide, ligand, None)
                yaml_path = directory / "yaml" / f"{job.job_id}.yaml"
                yaml_path.write_text(Y.to_yaml_text(document))

                record = job.to_dict()
                record["yaml"] = str(yaml_path)
                record["pocket_residues"] = None
                record["pocket_provenance"] = None
                record["role"] = pair.get("role")
                record["scramble_of"] = pair.get("scramble_of")
                record["borrowed_from"] = pair.get("borrowed_from")
                queue.write(json.dumps(record) + "\n")
                written += 1

        by_role: dict[str, int] = {}
        for pair in manifest["pairs"]:
            role = pair.get("role") or "unknown"
            by_role[role] = by_role.get(role, 0) + 1

        summary = {
            "campaign_id": directory.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "pairs": len(manifest["pairs"]),
            "pairs_by_role": by_role,
            "jobs_emitted": written,
            "jobs_per_pair": manifest["jobs_per_pair"],
            "seeds": manifest["seeds"],
            "receptors": manifest["receptors"],
            "glue_degron_pairs": manifest["glue_degron_pairs"],
            "excluded_genes": sorted(T.exclusions()),
            "manifest_warnings": manifest["warnings"],
            "unroutable": manifest["unroutable"],
            "conditioned_jobs_dropped_no_pocket": 0,
            "conditioning": "unconstrained only: a Tier B receptor has no "
                            "deposited structure to derive a pocket from",
            "tuning": paths.tuning()["campaign"],
            "software": software.versions(),
        }
        (directory / "campaign.json").write_text(
            json.dumps(summary, indent=2, default=str))
        return {"path": str(directory), "reused": False, **summary}


def regenerate_all() -> dict[str, str]:
    """`{job_id: yaml text}` for the whole main campaign, manifest built once.

    `regenerate_pair` builds the manifest itself, which is right for one pair
    and wasteful for all of them: 158 pairs at about 0.15 s of manifest each
    turned a two-second scan into twenty-three.
    """
    return _regenerate(None)


def regenerate_pair(pair_id: str) -> dict[str, str]:
    """`{job_id: yaml text}` for one pair, as the current code would write it."""
    return _regenerate(pair_id)


def _regenerate(only: str | None) -> dict[str, str]:
    """Every job's YAML text, or one pair's when `only` names a pair.

    Nothing is written and no campaign directory is created. That last part
    is why this exists: re-deriving a YAML used to mean calling
    `assemble_campaign`, which writes a whole new `campaigns/campaign_<stamp>`
    directory, and both the chain and `tools/status.sh` pick their campaign
    with the newest such directory. A scratch assembly would have become "the
    latest campaign" and the chain's remaining stages would have targeted it.

    Conditioned jobs with no measurable pocket are omitted, the same ones the
    assembler drops and counts, so a caller comparing this against a campaign
    on disk finds them absent from both.
    """
    from nobble.curate import library as LM
    from nobble.curate import manifest as M

    library = LM.load()
    if library is None:
        raise RuntimeError("no library manifest: run nobble.curate.library first")
    manifest = M.build_campaign_manifest(library=library["peptides"])
    pair_by_id = {pair["pair_id"]: pair for pair in manifest["pairs"]}
    rows = {row["peptide_id"]: row for row in library["peptides"]}
    ligand_by_index = L.benchmark_ligands()
    member_by_pair = {
        f"bench{item['index']:02d}_{item['gene']}_{item['e3']}": item
        for item in P.BENCHMARK_CHAINS
    }
    cache: dict[tuple, Y.PocketConstraint | None] = {}

    out: dict[str, str] = {}
    for job in manifest["jobs"]:
        if only is not None and job.pair_id != only:
            continue
        pair = pair_by_id.get(job.pair_id)
        row = rows.get(job.peptide_id)
        if pair is None or row is None:
            continue
        pocket = _pocket_for_pair(pair, member_by_pair, cache)
        if job.conditioning == "conditioned" and pocket is None:
            continue
        out[job.job_id] = Y.to_yaml_text(document_for(
            job, pair, row, member_by_pair, ligand_by_index, pocket))
    return out


def _pocket_for_pair(pair: dict, member_by_pair: dict,
                     cache: dict) -> "Y.PocketConstraint | None":
    """The pocket constraint for a pair, cached by construct and ligand.

    Lifted out of `assemble_campaign`'s closure so the rerun tool can produce
    the same document the assembler would. Two spellings of how a YAML is
    built is the F154 and F57 shape: the one that is not exercised drifts, and
    this one would be the one that decides whether a correction is a
    correction.
    """
    construct_name = pair["construct"]
    ligand = pair.get("ligand") or {}
    ccd = ligand.get("ccd")
    key = (construct_name, ccd or ligand.get("key"))
    if key in cache:
        return cache[key]

    member = member_by_pair.get(pair["pair_id"])
    if member is not None:
        pdb_id = member["pdb_id"]
    else:
        pdb_id = IMID_POCKET_SOURCE.get(ccd)
    pocket = None
    if pdb_id and ccd:
        pocket = Y.derive_pocket(
            C.by_name(construct_name), pdb_id, ccd, pair.get("e3_gene") or "")
    cache[key] = pocket
    return pocket


def document_for(job, pair: dict, row: dict, member_by_pair: dict,
                 ligand_by_index: dict, pocket) -> dict:
    """The YAML document the assembler would write for one job.

    The pocket is passed in rather than resolved here, because the caller
    decides what to do with a conditioned job that has none: the assembler
    drops it and counts it, and that decision has to happen before the
    document is built, not after.
    """
    peptide = P.Peptide(**{k: v for k, v in row.items() if k != "length"})
    member = member_by_pair.get(job.pair_id)
    if member is not None:
        ligand = ligand_by_index.get(member["index"])
    else:
        ligand = _ligand_of(pair)
    return Y.build_yaml(job, peptide, ligand, pocket)


def _ligand_of(pair: dict) -> "L.Ligand | None":
    """The pair's own ligand, rebuilt from the manifest record.

    A pair id that is not a benchmark member, which is every scramble and
    every borrowed pair, used to fall back to `L.by_ccd(pair["ligand"]["ccd"])`.
    A SMILES-only degrader has no CCD, so that returned None and
    `build_yaml` omitted the ligand block entirely: the ternary arm was
    written as a second binary arm while the queue record still named the
    ligand. One pair in the main campaign went through a whole run that way,
    scr_bench03_BRD4_CRBN with dBET57, and its Delta-ipTM came out at exactly
    0.0, which for a scramble control reads as the cleanest result there is
    (F262).

    The manifest's pair carries a full `Ligand.to_dict()`, so there is
    nothing to look up. Filtered through the dataclass's own fields rather
    than splatted, so a record that gains a key later does not raise here,
    and falling back to the CCD lookup only when the record cannot be used
    at all.
    """
    import dataclasses

    record = pair.get("ligand") or {}
    if not record:
        return None
    names = {field.name for field in dataclasses.fields(L.Ligand)}
    missing = names - set(record)
    if not missing:
        return L.Ligand(**{k: v for k, v in record.items() if k in names})
    ccd = record.get("ccd")
    return L.by_ccd(ccd, modality="glue") if ccd else None


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

        # Pocket cache keyed by (construct, ligand ccd or smiles key),
        # resolved by the module-level helper the rerun tool shares.
        pocket_cache: dict[tuple, Y.PocketConstraint | None] = {}

        queue_path = directory / "queue.jsonl"
        written = 0
        skipped_conditioned = 0
        with queue_path.open("w") as queue:
            for job in manifest["jobs"]:
                pair = pair_by_id.get(job.pair_id)
                row = rows.get(job.peptide_id)
                if pair is None or row is None:
                    continue
                pocket = _pocket_for_pair(pair, member_by_pair, pocket_cache)
                if job.conditioning == "conditioned" and pocket is None:
                    skipped_conditioned += 1
                    continue

                document = document_for(job, pair, row, member_by_pair,
                                        ligand_by_index, pocket)
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
            # Which Boltz will produce the coordinates. Recorded at
            # assembly, because that is when the environment is the one the
            # queue will run in, and because every number the atlas
            # publishes is a prediction from this version: the tuning on the
            # line above was already recorded and the model was not (F185).
            "software": software.versions(),
            "pockets": {
                f"{construct}/{ligand}": (pocket.positions if pocket else None)
                for (construct, ligand), pocket in pocket_cache.items()
            },
            "imid_pocket_sources": IMID_POCKET_SOURCE,
        }
        (directory / "campaign.json").write_text(json.dumps(summary, indent=2, default=str))
        return {"path": str(directory), "reused": False, **summary}
