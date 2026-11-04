"""Build the design arm's published document.

Runs on the Studio, not the droplet. The tab reads the result as static
JSON, like every other precomputed view.
"""
from __future__ import annotations

import json
from pathlib import Path

from nobble import paths
from nobble.design import lift as lift_module
from nobble.design import variants as variant_module
from nobble.numeric import finite


def candidate_parents() -> list[dict]:
    """Degrons worth scanning, with their experimental anchor.

    Only peptides carrying an experimental label qualify. A scan of an
    unlabelled sequence produces lifts against a parent whose own
    Delta-ipTM means nothing, which is a chart with no zero.
    """
    from nobble.curate import library as library_module

    library = library_module.load()
    if library is None:
        return []

    parents = []
    for row in library["peptides"]:
        if row.get("source") not in ("benchmark", "sievers_zf"):
            continue
        if row.get("label") not in ("degraded",):
            continue
        parents.append({
            "peptide_id": row["peptide_id"],
            "gene": row.get("gene"),
            "sequence": row["sequence"],
            "length": len(row["sequence"]),
            "source": row["source"],
            "e3_hint": row.get("e3_hint"),
            "label": row.get("label"),
            "modality": _modality_of(row),
        })
    return sorted(parents, key=lambda item: (item["source"], item["gene"] or ""))


def _modality_of(row: dict) -> str:
    """glue or protac, for the parent this peptide belongs to.

    The arm measures glue dependence, so a bivalent degrader is a poor
    default target even though it is a perfectly good benchmark pair.
    Sievers fingers are all IMiD glues.
    """
    from nobble.curate import ligands as ligand_module
    from nobble.curate import peptides as peptide_module

    if row.get("source") == "sievers_zf":
        return "glue"
    member = next((m for m in peptide_module.BENCHMARK_CHAINS
                   if m["gene"] == row.get("gene")
                   and m["e3"] == row.get("e3_hint")), None)
    if member is None:
        return "unknown"
    entry = ligand_module.BENCHMARK_LIGANDS.get(member["index"])
    return entry[1] if entry else "unknown"


def _default_parent(parents: list[dict]) -> dict:
    """Which degron to scan first, chosen from the measurement.

    Every benchmark degron is a 15-mer, so picking "the shortest" was an
    arbitrary tiebreak that happened to land on BRD4/VHL: a PROTAC pair,
    when the arm is about glue dependence. Rank by measured Delta-ipTM
    instead, because the degron worth scanning first is the one with the
    largest signal to move, and a scan of a parent with no glue dependence
    measures the noise floor.

    Falls back to the shortest glue parent when nothing is scored yet, so
    the tab still has something to show before the campaign runs.
    """
    scored: dict[str, float] = {}
    try:
        from nobble.app import data as app_data
        for row in app_data.scores():
            value = row.get("delta_iptm")
            if finite(value) and row.get("peptide_id"):
                scored[row["peptide_id"]] = value
    except Exception:                                      # noqa: BLE001
        scored = {}

    ranked = [p for p in parents if p["peptide_id"] in scored]
    if ranked:
        best = max(ranked, key=lambda p: scored[p["peptide_id"]])
        best = dict(best)
        best["chosen_because"] = (
            f"largest measured delta-ipTM of the scored parents "
            f"({scored[best['peptide_id']]:+.3f}): the degron with the most "
            "glue dependence to move"
        )
        return best

    # Nothing scored. Fall back, but not to a bivalent degrader: the arm
    # measures glue dependence, and the unqualified "shortest benchmark
    # degron" rule picked BRD4/VHL, a PROTAC pair, because every benchmark
    # degron is a 15-mer and length was an arbitrary tiebreak.
    glue = [p for p in parents if p.get("modality") == "glue"]
    benchmark = [p for p in (glue or parents) if p["source"] == "benchmark"]
    fallback = dict(min(benchmark or glue or parents,
                        key=lambda p: (p["length"], p["peptide_id"])))
    fallback["chosen_because"] = (
        "nothing is scored yet, so the shortest benchmark glue degron stands "
        "in. A scan chosen this way has not been ranked against anything"
    )
    return fallback


def cost_of(count: int, tokens_per_pair: int | None = None,
            job_tokens: list[int] | None = None) -> dict:
    """What a set of variants would cost, from the measured rate.

    `job_tokens` is the token count of each job the scan would actually
    emit, which is what the projection wants. `tokens_per_pair` is the older
    way of saying the same thing when every job is the same size.

    Both were optional and neither was ever passed, so this always took the
    fallback that F45's whole finding was about: a representative job from
    whichever campaign was measured last. It gave the right answer only
    because throughput happened to be measured on a campaign whose median
    job is 144 tokens, the same as the design scan's. Measured on the
    corrected campaign instead, whose median job is 397, the same unchanged
    scan would have been projected at 11.5 hours against a real 4.4 (F79).
    A design scan's variants are the parent's length, so one number covers
    them all, and that is exactly the case the banded projection prices
    correctly: every job is the same size, so it belongs in one band, and a
    scan whose jobs are all 1,200 tokens must not be priced at a rate whose
    median came from 144-token jobs (F61).
    """
    from nobble.curate.diversity import projected_hours
    from nobble.curate.manifest import jobs_per_pair

    jobs = count * jobs_per_pair()
    if job_tokens is None and tokens_per_pair:
        job_tokens = [tokens_per_pair] * jobs
    total_tokens = sum(job_tokens) if job_tokens else None
    projection = projected_hours(count, total_tokens=total_tokens,
                                 job_tokens=job_tokens)
    return {
        "variants": count,
        "jobs": projection.get("jobs"),
        "projected_hours": projection.get("projected_hours"),
        "status": projection.get("status"),
        "basis": projection.get("basis"),
    }


def _scan_job_tokens(parent_id: str) -> list[int] | None:
    """Token count of every job the scan would emit, from the assembler.

    Taken from `build_manifest`, which is what will actually emit them, so
    the preview's cost is the cost of the thing being previewed rather than
    an estimate built beside it. `build_manifest` writes nothing, and the
    design report is produced at atlas-build time rather than per request.

    Recomputing the token formula here instead would be a second copy of
    `construct.residue_count() + peptide.length + cofactor + ligand_atoms`,
    which is the shape this project keeps having to undo (F79).
    """
    try:
        from nobble.design import assemble as assemble_module

        manifest = assemble_module.build_manifest(parent_id)
    except Exception:                               # noqa: BLE001
        return None
    jobs = manifest.get("jobs") or []
    tokens = [job.tokens for job in jobs if getattr(job, "tokens", None)]
    return tokens or None


def build(parent_id: str | None = None) -> dict:
    """The document the tab renders."""
    parents = candidate_parents()
    chosen = None
    if parent_id:
        chosen = next((p for p in parents if p["peptide_id"] == parent_id), None)
    elif parents:
        chosen = _default_parent(parents)

    preview: dict = {}
    if chosen:
        generated = variant_module.generate(chosen["peptide_id"], chosen["sequence"])
        preview = {
            "parent": chosen,
            "generator": "alanine_scan",
            "variants": generated["variants"],
            "cost": cost_of(generated["count"],
                            job_tokens=_scan_job_tokens(chosen["peptide_id"])),
        }

    # Lifts, if a design campaign has actually run.
    lifts: dict = {"status": "no design campaign has run yet", "lifts": []}
    profile: dict = {}
    campaign = paths.CAMPAIGNS
    scored = sorted(campaign.glob("design_*/scores.jsonl")) if campaign.exists() else []
    if scored and chosen:
        lifts = lift_module.from_scores(scored[-1], chosen["peptide_id"])
        if lifts.get("lifts"):
            objects = [lift_module.Lift(**item) for item in lifts["lifts"]]
            profile = lift_module.scan_profile(objects, chosen["sequence"])

    # The validation state of the score the arm would rank by. Reported
    # next to the rankings rather than buried: a ranked list reads as a
    # recommendation whatever the caption says.
    validation = {}
    validation_path = paths.DATA / "atlas" / "validation.json"
    if validation_path.exists():
        try:
            document = json.loads(validation_path.read_text())
            layer = (document.get("layers") or {}).get("matched_control_roc", {})
            validation = {"matched_control_roc": layer.get("status")}
        except Exception:                                  # noqa: BLE001
            validation = {}

    # Previews for every scannable parent, precomputed. The droplet has no
    # curation stack, so it cannot generate a scan on request: without this
    # the tab is locked to whichever parent the atlas was built for. 31
    # parents at about 20 variants each is small enough to ship whole.
    all_previews = {}
    for candidate in parents:
        generated = variant_module.generate(candidate["peptide_id"],
                                            candidate["sequence"])
        all_previews[candidate["peptide_id"]] = {
            "parent": candidate,
            "variants": generated["variants"],
            "cost": cost_of(generated["count"]),
        }

    return {
        "parents": parents,
        "previews": all_previews,
        "preview": preview,
        "lifts": lifts,
        "profile": profile,
        "score_validation": validation,
        "caveat": (
            "The composite score this arm would rank by is not validated: the "
            "matched-control ROC reports not_computed until the Sievers arm "
            "runs. Until it does, the durable claim from a scan is the "
            "ordering of positions, not the absolute lift and not a "
            "prediction that any variant will be degraded."
        ),
    }


def main() -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Build the design arm document.")
    parser.add_argument("--parent", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    document = build(args.parent)
    target = Path(args.out) if args.out else paths.DATA / "atlas" / "design.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, default=str))
    print(json.dumps({
        "parents": len(document["parents"]),
        "preview_variants": len(document.get("preview", {}).get("variants", [])),
        "cost": document.get("preview", {}).get("cost"),
        "lifts": document["lifts"].get("status", "present"),
        "written": str(target),
    }, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
