"""Scoring orchestrator: run every component over a campaign and write the table.

Resumable and incremental by design, because it runs against a campaign that is
still executing. Spec's continuous-build rule 6 applies directly: build against
the data already available, mark what is missing as pending, and backfill when
the manifests show completion. So this can be run repeatedly while the queue is
live and each run scores whatever has landed since the last.

Composite (spec 4.8). The weights are fitted in Phase 3 on the benchmark panel
and the Sievers matched set, never hand-set (D-NOB-006), so until that fit has
data this writes the components and leaves `nobble_score` null rather than
inventing a weighting. The components are always reported alongside, never
replaced by, the composite.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nobble import paths
from nobble.score import geometry, lysine, metrics, plip, poses, weights

COMPONENTS = (
    "bridge_percentile",
    "lysine_reach",          # reported as measurement only: D-NOB-024
    "delta_iptm",
    "convergence_score",
    "plip_fingerprint_match",
)


def score_campaign(campaign: Path, with_plip: bool = True, limit: int | None = None) -> dict:
    """Score every pair with completed jobs. Writes scores.jsonl."""
    results_path = campaign / "results.jsonl"
    if not results_path.exists():
        return {"status": "no results yet", "campaign": str(campaign)}

    jobs = [
        json.loads(line) for line in results_path.read_text().splitlines() if line.strip()
    ]
    by_pair: dict[str, list[dict]] = {}
    for job in jobs:
        by_pair.setdefault(job["pair_id"], []).append(job)

    pair_metrics = {item.pair_id: item for item in metrics.aggregate(results_path)}

    scored = []
    pairs = sorted(by_pair)
    if limit:
        pairs = pairs[:limit]

    for pair_id in pairs:
        pair_jobs = by_pair[pair_id]
        record = pair_metrics.get(pair_id)
        entry: dict = record.to_dict() if record else {"pair_id": pair_id}

        # Geometry, per ternary job, then summarised over seeds.
        bridge_scores = []
        for job in pair_jobs:
            if job.get("complex_type") != "ternary":
                continue
            try:
                bridge_scores.append(geometry.score_structure(job))
            except Exception as problem:            # noqa: BLE001
                bridge_scores.append(None)
                entry.setdefault("errors", []).append(
                    f"geometry {job['job_id']}: {type(problem).__name__}: {problem}"
                )
        found = [item for item in bridge_scores if item is not None and item.found]
        entry["bridging_seeds_total"] = len([item for item in bridge_scores if item])
        entry["bridging_seeds_with_bridge"] = len(found)
        entry["bridge_formation_rate"] = (
            round(len(found) / entry["bridging_seeds_total"], 3)
            if entry["bridging_seeds_total"] else None
        )
        if found:
            percentiles = sorted(item.bridge_percentile for item in found)
            entry["bridge_percentile"] = percentiles[len(percentiles) // 2]
            entry["bridge_percentile_range"] = [percentiles[0], percentiles[-1]]
            entry["dsasa_total_median"] = sorted(item.dsasa_total for item in found)[
                len(found) // 2
            ]
            entry["bridging_balance_median"] = sorted(
                item.bridging_balance for item in found
            )[len(found) // 2]
        else:
            entry["bridge_percentile"] = None
            entry["notes"] = (entry.get("notes") or []) + [
                "no seed produced a glue bridge between receptor and peptide"
            ]

        # Docking: separate a failed trajectory from a weak interface.
        docked = []
        for job in pair_jobs:
            try:
                docked.append(poses.docking_check(job))
            except Exception:                       # noqa: BLE001
                continue
        entry["seeds_docked"] = sum(1 for item in docked if item.docked)
        entry["seeds_total"] = len(docked)
        entry["undocked_seeds"] = [
            item.job_id for item in docked if not item.docked
        ]

        # Convergence, per condition.
        entry["convergence"] = {}
        for condition in ("binary", "ternary_conditioned", "ternary_unconstrained"):
            try:
                result = poses.convergence(pair_jobs, condition)
            except Exception as problem:            # noqa: BLE001
                entry.setdefault("errors", []).append(
                    f"convergence {condition}: {type(problem).__name__}: {problem}"
                )
                continue
            entry["convergence"][condition] = result.to_dict()
        ternary_convergence = entry["convergence"].get("ternary_unconstrained") or {}
        entry["convergence_score"] = ternary_convergence.get("convergence_score")

        # Lysine geometry, on one representative ternary.
        representative = next(
            (job for job in pair_jobs if job.get("complex_type") == "ternary"), None
        )
        if representative:
            try:
                entry["lysine_reach"] = lysine.measure(representative).to_dict()
            except Exception as problem:            # noqa: BLE001
                entry.setdefault("errors", []).append(
                    f"lysine: {type(problem).__name__}: {problem}"
                )

        # PLIP fingerprint, on the same representative.
        if with_plip and representative:
            try:
                finger = plip.fingerprint(representative)
                entry["plip"] = finger.to_dict()
                expected = len(
                    plip.CANONICAL_FINGERPRINTS.get(representative.get("e3_gene"), {})
                    .get("receptor_residues", [])
                )
                entry["plip_fingerprint_match"] = (
                    round(len(finger.canonical_matched) / expected, 3)
                    if expected else None
                )
                entry["plip_glue_to_peptide_contacts"] = len(finger.peptide_contacts)
            except Exception as problem:            # noqa: BLE001
                entry.setdefault("errors", []).append(
                    f"plip: {type(problem).__name__}: {problem}"
                )

        # Spec 4.8. Left null until the weights are fitted (D-NOB-006): a
        # composite with invented weights is worse than no composite, because it
        # looks like a ranking.
        entry["nobble_score"] = None
        entry["nobble_score_status"] = (
            "not_computed: weights are fitted on the benchmark panel and the "
            "Sievers matched set in Phase 3 and are never hand-set (D-NOB-006). "
            "Components are reported individually."
        )
        # Spec 4.7, degraded: ProtCID was never acquired (D-NOB-010).
        entry["furniture"] = None
        entry["furniture_status"] = "not_computed: protcid_unavailable"
        entry["forced"] = (
            bool(entry.get("conditioning_disagreement") and
                 entry["conditioning_disagreement"] > 0.2)
            if entry.get("conditioning_disagreement") is not None else None
        )
        # Guarantee the schema. A pair whose PLIP or geometry has not run yet
        # must still carry every key, as null, rather than omitting it: a
        # consumer that reaches for a missing key gets an error instead of a
        # "not computed", and the app's Benchmark tab did exactly that on the
        # first pair whose ternary arm had not finished.
        for key in (
            "bridge_percentile", "bridge_percentile_range", "bridge_formation_rate",
            "bridging_seeds_total", "bridging_seeds_with_bridge",
            "dsasa_total_median", "bridging_balance_median",
            "convergence_score", "plip_fingerprint_match",
            "plip_glue_to_peptide_contacts", "plip", "lysine_reach",
            "seeds_docked", "seeds_total", "delta_iptm", "delta_iptm_median",
            "iptm_min_binary", "iptm_min_ternary", "conditioning_disagreement",
            "seed_collapse_affects_delta", "peptide_label", "peptide_gene",
            "ligand_key", "modality", "tier", "e3_gene", "construct",
        ):
            entry.setdefault(key, None)
        entry.setdefault("undocked_seeds", [])
        entry.setdefault("notes", [])
        entry.setdefault("seed_records", [])
        entry.setdefault("convergence", {})
        entry.setdefault("errors", [])
        scored.append(entry)

    output = campaign / "scores.jsonl"
    with output.open("w") as handle:
        for entry in scored:
            handle.write(json.dumps(entry, default=str) + "\n")

    # Spec 4.8: fit the weights, then apply them. Two passes are needed because
    # the fit reads the scored components, so the composite cannot be written
    # until every component exists. When the fit refuses, nobble_score stays
    # null and carries the refusal as its status, which is the honest output.
    fit = weights.fit(campaign)
    (campaign / "weights.json").write_text(json.dumps(fit.to_dict(), indent=2))
    if fit.fitted:
        for entry in scored:
            entry["nobble_score"] = weights.apply(entry, fit.weights)
            entry["nobble_score_status"] = (
                f"fitted on {fit.labelled_pairs} labelled pairs, AUC {fit.objective}"
            )
            entry["nobble_score_weights"] = fit.weights
            entry["nobble_score_caveats"] = fit.caveats
        with output.open("w") as handle:
            for entry in scored:
                handle.write(json.dumps(entry, default=str) + "\n")
    else:
        for entry in scored:
            entry["nobble_score_status"] = fit.status

    return {
        "campaign": str(campaign),
        "pairs_scored": len(scored),
        "scores": str(output),
        "components": list(COMPONENTS),
        "weight_fit": fit.to_dict(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a NOBBLE campaign")
    parser.add_argument("--campaign", type=Path, default=None)
    parser.add_argument("--no-plip", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    campaign = args.campaign
    if campaign is None:
        from nobble.execute.campaign import latest
        campaign = latest("benchmark")
    if campaign is None:
        print("no campaign found", file=sys.stderr)
        return 2

    summary = score_campaign(Path(campaign), with_plip=not args.no_plip, limit=args.limit)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
