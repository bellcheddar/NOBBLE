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
from nobble.execute.runner import tier_files
from nobble.score import geometry, lysine, metrics, plip, poses, weights
from nobble.numeric import finite_values, median_of

# Was a literal at the call site. It decides the published `forced` flag,
# so it is a cutoff and belongs in thresholds.toml (CLAUDE.md).
FORCED_DISAGREEMENT = float(paths.thresholds()["conditioning"]["forced_disagreement"])

COMPONENTS = (
    "bridge_percentile",
    "lysine_reach",          # reported as measurement only: D-NOB-024
    "delta_iptm",
    "convergence_score",
    "plip_fingerprint_match",
)


def score_campaign(campaign: Path, with_plip: bool = True, limit: int | None = None,
                   sampling_tier: int = 1) -> dict:
    """Score every pair with completed jobs. Writes scores.jsonl.

    `sampling_tier` selects which sampling regime to score and defaults to
    tier 1, the regime Delta-ipTM is defined over (D-NOB-032). Tier 2 has its
    own results file, so the two cannot mix by accident, but the job list is
    filtered here as well: `by_pair` feeds geometry and PLIP per job, which is
    a second path a stray record could take into a tier-1 number.
    """
    tier_paths = tier_files(campaign, sampling_tier)
    results_path = tier_paths["results"]
    if not results_path.exists():
        return {"status": "no results yet", "campaign": str(campaign),
                "sampling_tier": sampling_tier}

    jobs = paths.read_jsonl(results_path, tolerate_torn=True)
    jobs = [job for job in jobs if int(job.get("tier_setting", 1)) == sampling_tier]
    if not jobs:
        return {"status": f"no tier-{sampling_tier} results yet",
                "campaign": str(campaign), "sampling_tier": sampling_tier}

    by_pair: dict[str, list[dict]] = {}
    for job in jobs:
        by_pair.setdefault(job["pair_id"], []).append(job)

    pair_metrics = {
        item.pair_id: item
        for item in metrics.aggregate(results_path, sampling_tier=sampling_tier)
    }

    scored = []
    pairs = sorted(by_pair)
    if limit:
        pairs = pairs[:limit]

    for pair_id in pairs:
        pair_jobs = by_pair[pair_id]
        record = pair_metrics.get(pair_id)
        entry: dict = record.to_dict() if record else {"pair_id": pair_id}

        # How many diffusion samples this pair's jobs actually ran at.
        #
        # One number for the whole of tier 2 until F298. A job too large to
        # refine at the tier's sample count now samples fewer, which is the
        # right trade for a job that otherwise writes nothing, and it makes a
        # minimum over poses no longer comparable across pairs: a best-of-9
        # and a best-of-25 are different draws from the same distribution and
        # the second wins on sample count alone. Tier 2 already withholds the
        # minimum-over-seeds quantities for exactly this reason, but
        # `best_rmsd` in the pose-recovery layer is a minimum too.
        #
        # So the count is carried on the pair rather than left in the job
        # rows. A reader comparing two pairs' refined poses can see it, and
        # `_sampling_note` below says so once for the whole campaign instead
        # of leaving it to be noticed.
        seen = sorted({int(job["diffusion_samples"]) for job in pair_jobs
                       if job.get("diffusion_samples") is not None})
        entry["diffusion_samples"] = seen or None

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
        # A seed whose geometry could not run is not a seed that did not
        # bridge. Both used to land in the denominator, so a pair with five
        # usable ternaries of which four bridged, and five whose output had no
        # ligand chain, reported a formation rate of 0.4 rather than 0.8 with
        # five seeds unmeasurable. Latent so far: the only reason seen in any
        # campaign is BINMAN's own single_chain verdict, which is a real
        # negative and still counts.
        unmeasurable = [
            item for item in bridge_scores
            if item is not None and not item.found
            and item.reject_reason in geometry.MEASUREMENT_FAILURES
        ]
        measured = [
            item for item in bridge_scores
            if item is not None and item not in unmeasurable
        ]
        entry["bridging_seeds_total"] = len(measured)
        entry["bridging_seeds_with_bridge"] = len(found)
        entry["bridging_seeds_unmeasurable"] = len(unmeasurable)
        if unmeasurable:
            counts: dict[str, int] = {}
            for item in unmeasurable:
                key = item.reject_reason or "unknown"
                counts[key] = counts.get(key, 0) + 1
            entry["bridging_unmeasurable_reasons"] = counts

        # Why the seeds that did not bridge did not bridge. The per-seed
        # reason was computed and then aggregated away, so a pair with no
        # bridge showed a blank percentile and no explanation. On CDK12 all
        # ten seeds reject as single_chain:1_qualifying_of_1, which says the
        # glue buried surface against one chain rather than two: it is not
        # that the bridge was weak, it is that there was no bridge to
        # measure. That distinction is the whole of spec 4.1.
        reasons: dict[str, int] = {}
        for item in measured:
            if item.found:
                continue
            reason = item.reject_reason or "unknown"
            reasons[reason] = reasons.get(reason, 0) + 1
        entry["bridge_reject_reasons"] = (
            dict(sorted(reasons.items(), key=lambda kv: -kv[1])) if reasons else {}
        )
        entry["bridge_formation_rate"] = (
            round(len(found) / entry["bridging_seeds_total"], 3)
            if entry["bridging_seeds_total"] else None
        )
        if found:
            # median_of, not sorted(...)[len // 2]. A NaN inside sorted()
            # settles wherever the sort leaves it, so an index into the
            # result is not the median of anything, and percentile_of
            # returns NaN when the reference distribution is empty: a host
            # without BINMAN's atlas would have produced a NaN percentile
            # for every pair rather than refusing (F76).
            percentiles = sorted(finite_values(
                item.bridge_percentile for item in found))
            entry["bridge_percentile"] = median_of(
                item.bridge_percentile for item in found)
            entry["bridge_percentile_range"] = (
                [percentiles[0], percentiles[-1]] if percentiles else None)
            entry["dsasa_total_median"] = median_of(
                item.dsasa_total for item in found)
            entry["bridging_balance_median"] = median_of(
                item.bridging_balance for item in found)
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

        # The peptide-to-receptor contact map (spec Phase 4). Computed here
        # because the droplet does no geometry at request time.
        if representative:
            try:
                entry["contact_map"] = geometry.contact_map(representative)
            except Exception as problem:            # noqa: BLE001
                entry.setdefault("errors", []).append(
                    f"contact_map: {type(problem).__name__}: {problem}"
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
                # A fingerprint that did not run has no canonical matches, and
                # dividing that by the number expected gives 0.0: a number
                # saying the prediction reproduced none of the canonical degron
                # contacts, where the truth is that nothing was measured. The
                # whole point of this module's CONECT gate is to refuse rather
                # than return a plausible fingerprint, and this turned the
                # refusal back into a figure, fed it to the weight fitter as an
                # observation and showed it on the Interactions tab (F32).
                if finger.status != "ok":
                    entry["plip_fingerprint_match"] = None
                    entry["plip_fingerprint_match_status"] = (
                        f"not_computed: {finger.status}"
                    )
                    entry["plip_glue_to_peptide_contacts"] = None
                else:
                    entry["plip_fingerprint_match"] = (
                        round(len(finger.canonical_matched) / expected, 3)
                        if expected else None
                    )
                    entry["plip_fingerprint_match_status"] = (
                        "ok" if expected else
                        "not_computed: no canonical fingerprint for "
                        f"{representative.get('e3_gene')}"
                    )
                    entry["plip_glue_to_peptide_contacts"] = len(finger.peptide_contacts)
            except Exception as problem:            # noqa: BLE001
                entry.setdefault("errors", []).append(
                    f"plip: {type(problem).__name__}: {problem}"
                )
        else:
            # A reason rather than an absent key. --no-plip is a real path,
            # and a pair scored without PLIP should say that instead of
            # looking like a pair whose fingerprint failed (F43).
            entry["plip_fingerprint_match"] = None
            entry["plip_fingerprint_match_status"] = (
                "not_computed: plip was not run for this campaign"
                if not with_plip else
                "not_computed: the pair has no ternary job to fingerprint"
            )
            entry["plip_glue_to_peptide_contacts"] = None

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
                 entry["conditioning_disagreement"] > FORCED_DISAGREEMENT)
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
            "bridge_reject_reasons",
            "dsasa_total_median", "bridging_balance_median",
            "convergence_score", "plip_fingerprint_match",
            "plip_glue_to_peptide_contacts", "plip", "lysine_reach",
            "seeds_docked", "seeds_total", "delta_iptm", "delta_iptm_median",
            "contact_map",
            "iptm_min_binary", "iptm_min_ternary", "conditioning_disagreement",
            "seed_collapse_affects_delta", "peptide_label", "peptide_gene",
            "ligand_key", "modality", "tier", "e3_gene", "construct",
            # Both of these are now set on every path above, so these two
            # entries are a floor rather than the fix: removing them changes
            # nothing today and catches the next branch that forgets. The
            # fix was setting them where they are produced (F43).
            "plip_fingerprint_match_status", "bridging_seeds_unmeasurable",
        ):
            entry.setdefault(key, None)
        entry.setdefault("bridging_unmeasurable_reasons", {})
        entry.setdefault("undocked_seeds", [])
        entry.setdefault("notes", [])
        entry.setdefault("seed_records", [])
        entry.setdefault("convergence", {})
        entry.setdefault("errors", [])
        scored.append(entry)

    suffix = "" if sampling_tier == 1 else f"_tier{sampling_tier}"
    output = campaign / f"scores{suffix}.jsonl"
    with output.open("w") as handle:
        for entry in scored:
            handle.write(json.dumps(entry, default=str) + "\n")

    # Spec 4.8: fit the weights, then apply them. Two passes are needed because
    # the fit reads the scored components, so the composite cannot be written
    # until every component exists. When the fit refuses, nobble_score stays
    # null and carries the refusal as its status, which is the honest output.
    #
    # Tier 1 only. The fit reads scores.jsonl and writes weights.json, both of
    # which the app, the atlas and tier-2 selection all read. Refitting them
    # from a refined decile would fit the composite on the pairs the composite
    # just selected, and the decile is not a sample of anything: it is the top
    # of the ranking by construction.
    if sampling_tier != 1:
        return {
            "campaign": str(campaign),
            "sampling_tier": sampling_tier,
            "scored": len(scored),
            "output": str(output),
            "note": (
                "tier-2 poses scored into their own file. The composite was "
                "not refitted: the decile is the top of the tier-1 ranking by "
                "construction, not a sample, so fitting on it would be fitting "
                "on the selection. Delta-ipTM here is not comparable to tier 1 "
                "(D-NOB-032)."
            ),
        }

    fit = weights.fit(campaign)
    (campaign / "weights.json").write_text(json.dumps(fit.to_dict(), indent=2))
    if fit.fitted:
        for entry in scored:
            entry["nobble_score"] = weights.apply(entry, fit.weights)
            # How many of the weighted components the pair had. The browser
            # has always shown this and the stored record did not, so a
            # score over three components and one over four sat in the same
            # column as the same quantity (F123).
            entry["nobble_score_coverage"] = weights.coverage(entry, fit.weights)
            entry["nobble_score_status"] = (
                f"fitted on {fit.labelled_pairs} labelled pairs, "
                f"in-sample AUC {fit.objective}"
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
        "sampling": _sampling_note(scored),
    }


def _sampling_note(scored: list[dict]) -> dict:
    """Whether every scored pair ran at the same number of diffusion samples.

    Said once for the campaign rather than left to be noticed pair by pair.
    `uniform` false means a minimum over poses is not comparable across these
    pairs, because a best-of-9 and a best-of-25 are different draws and the
    second wins on sample count alone (F298).

    `unknown` counts pairs whose jobs predate the recording, which is not the
    same as pairs that agree: a campaign scored before F298 has no counts at
    all and must not read as uniform.
    """
    counts: dict[str, list[str]] = {}
    unknown = []
    for entry in scored:
        seen = entry.get("diffusion_samples")
        if not seen:
            unknown.append(entry.get("pair_id"))
            continue
        counts.setdefault(",".join(str(value) for value in seen), []).append(
            entry.get("pair_id"))
    note = {
        "by_count": {key: sorted(filter(None, pairs))
                     for key, pairs in sorted(counts.items())},
        "pairs_without_a_recorded_count": sorted(filter(None, unknown)),
        "uniform": len(counts) <= 1 and not unknown,
    }
    if not note["uniform"]:
        note["caveat"] = (
            "these pairs did not all run at the same number of diffusion "
            "samples, so a quantity that is a minimum over poses is not "
            "comparable between them")
    return note


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a NOBBLE campaign")
    parser.add_argument("--campaign", type=Path, default=None)
    parser.add_argument("--no-plip", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--tier", type=int, default=1, choices=(1, 2),
                        help="sampling tier to score (default 1, the regime "
                             "Delta-ipTM is defined over)")
    args = parser.parse_args()

    campaign = args.campaign
    if campaign is None:
        from nobble.execute.campaign import latest
        campaign = latest("benchmark")
    if campaign is None:
        print("no campaign found", file=sys.stderr)
        return 2

    summary = score_campaign(Path(campaign), with_plip=not args.no_plip,
                             limit=args.limit, sampling_tier=args.tier)
    print(json.dumps(summary, indent=2))

    # Nothing scored is a non-zero exit, not a successful run of a scorer
    # that found nothing (F322).
    #
    # `score_campaign` carries a `status` only on the paths where it wrote no
    # scores: no results file, no rows for this tier. The success path has
    # `pairs_scored` and no status, so the key's presence is the
    # discriminator rather than a string match.
    #
    # This returned 0 regardless, which defeated three guards written for
    # exactly this case. `tools/tier2.sh` and `tools/run_chain.sh` both wrap
    # the scorer in `if ! ...` with comments citing F194 and F195 and saying
    # that "a silent scoring failure would leave 39 hours of inference
    # unread"; neither could fire, because the silence reported itself as
    # success. `tools/refresh.sh` gates publication on the same code and
    # would have published an atlas copying the previous run's
    # `scores.jsonl`, which is the stale-for-fresh substitution its own
    # comment warns about.
    #
    # 3 rather than 2, which already means "no campaign found": a campaign
    # that exists and has nothing to score is a different thing from no
    # campaign.
    if "status" in summary:
        print(f"scoring wrote nothing: {summary['status']}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
