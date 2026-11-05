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
            job_tokens: list[int] | None = None,
            parent_id: str | None = None) -> dict:
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
    basis = projection.get("basis")
    # The subject, not just the method. Two parents of the same length emit
    # the same number of jobs and different token totals, so GSPT1's scan
    # costs 4.7 hours and IKZF1's 4.4. I compared those two figures as
    # though they described one scan, which they do not, and a basis that
    # named its parent would have said so (F89).
    if parent_id and basis:
        basis = f"{parent_id}: {basis}"
    return {
        "variants": count,
        "jobs": projection.get("jobs"),
        "projected_hours": projection.get("projected_hours"),
        "status": projection.get("status"),
        "basis": basis,
        "parent": parent_id,
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


def _score_validation(campaign: Path | None = None) -> tuple[dict, str]:
    """The matched-control ROC's actual state, and the caveat that follows.

    This used to read `data/atlas/validation.json`, a path that has never
    existed: `data/atlas` is empty and the layer statuses live in the
    campaign, which is where `build_atlas` reads them for everything else.
    So `score_validation` was published as `{}` on every build, and the
    caveat beside it asserted "the matched-control ROC reports not_computed"
    as a literal string.

    That literal is true today and becomes false the moment the Sievers arm
    finishes, which is the moment the project's headline result arrives: the
    design page would go on saying the score is not validated while the
    curve that validates it sat one file away. F96 was a caveat that never
    reached the page; this is a caveat that reaches the page and cannot
    change (F105).

    An unreadable status falls back to the conservative reading rather than
    to silence. Not validated until shown otherwise is the safe direction
    for a page that ranks variants.
    """
    from nobble.execute.campaign import latest

    def relative(path: Path) -> str:
        """Project-relative, so the record is stable and leaks nothing.

        Recording the resolved path published an absolute home-directory path
        into the atlas, and made the value depend on how the build was
        invoked: the chain passes a relative campaign path and the drift check
        passes an absolute one, so the same campaign produced two different
        strings and the drift check could never settle (F105).
        """
        try:
            return str(Path(path).resolve().relative_to(paths.ROOT.resolve()))
        except ValueError:
            return Path(path).name

    searched: list[str] = []
    candidates: list[Path] = []
    if campaign is not None:
        candidates.append(Path(campaign) / "validation.json")
    newest = latest("campaign")
    if newest is not None:
        candidates.append(Path(newest) / "validation.json")
    candidates.append(paths.ROOT / "deploy" / "atlas" / "validation.json")

    layer: dict = {}
    for candidate in candidates:
        searched.append(relative(candidate))
        if not candidate.exists():
            continue
        try:
            document = json.loads(candidate.read_text())
        except Exception:                                  # noqa: BLE001
            continue
        found = (document.get("layers") or {}).get("matched_control_roc")
        if isinstance(found, dict):
            layer = found
            break

    status = layer.get("status")
    summary = layer.get("summary") or {}
    validation = {
        "matched_control_roc": status,
        "auc": summary.get("auc"),
        "ci95": summary.get("ci95"),
        "interpretation": summary.get("interpretation"),
        "read_from": searched[-1] if layer and searched else None,
        "searched": searched,
    }

    # Kept short on purpose. This is the sentence the page renders, and the
    # UI copy budget is under 40 words a panel; the layer's own reason can
    # run to three lines, so it stays in `score_validation` where a reader
    # of the JSON finds it and the panel does not carry it.
    ordering = "Read the ordering of positions, not the absolute lift."

    if status == "computed" and summary.get("auc") is not None:
        interpretation = str(summary.get("interpretation") or "")
        low, high = (summary.get("ci95") or [None, None])[:2]
        # The level from the layer that computed the interval, with the
        # configured one as the fallback, rather than a literal of my own:
        # F105 wrote "95 per cent" here while layers.py had it in two more
        # places, and all four agreed with config by coincidence (F119).
        from nobble.validate.layers import confidence_level

        level = summary.get("confidence_level") or confidence_level()
        band = (f", {level:g} per cent CI {low} to {high}"
                if low is not None else "")
        # Three cases, because the layer produces three. This was `if above
        # chance ... else "is not distinguishable from chance"`, so a curve
        # separating in the opposite direction was described as showing no
        # separation at all: an AUC of 0.25 with its whole interval below
        # 0.5 read as indistinguishable from chance. That is the mistake
        # `_verdict`'s own comment records, "reads as exhaustive and is
        # not", repeated a module away, and it understates a real finding:
        # a composite that orders pairs backwards is a result (F199).
        if interpretation.startswith("above chance"):
            caveat = (f"The composite separates the matched controls at AUC "
                      f"{summary['auc']}{band}, above chance. {ordering}")
        elif interpretation.startswith("below chance"):
            caveat = (f"The composite is not validated: the matched-control "
                      f"ROC computed at AUC {summary['auc']}{band} and "
                      f"separates the controls in the opposite direction to "
                      f"the prediction, which is a result rather than an "
                      f"absence of one. {ordering}")
        else:
            caveat = (f"The composite is not validated: the matched-control "
                      f"ROC computed at AUC {summary['auc']}{band} and is not "
                      f"distinguishable from chance. {ordering}")
    elif status:
        caveat = ("The composite is not validated: the matched-control ROC "
                  f"has not computed. {ordering}")
    else:
        caveat = ("The composite is not validated: no matched-control ROC "
                  f"status could be read. {ordering}")
    return validation, caveat


def build(parent_id: str | None = None,
          campaign: Path | None = None) -> dict:
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
                            job_tokens=_scan_job_tokens(chosen["peptide_id"]),
                            parent_id=chosen["peptide_id"]),
        }

    # Lifts, if a design campaign has actually run.
    lifts: dict = {"status": "no design campaign has run yet", "lifts": []}
    profile: dict = {}
    # Named for what it is. This was `campaign`, which shadowed the `campaign`
    # argument added for the validation lookup below: a campaign passed in was
    # silently replaced by the campaigns directory, so the argument could
    # never have been read (F105).
    campaigns_root = paths.CAMPAIGNS
    scored = (sorted(campaigns_root.glob("design_*/scores.jsonl"))
              if campaigns_root.exists() else [])
    if scored:
        # The parent the scan actually ran on, from the campaign's own
        # record, not the one this report happens to rank first (F147).
        #
        # `chosen` is selected here and now, from the current scores. The
        # design campaign was assembled for whichever parent led when it was
        # assembled. Those agree in the chain, which re-assembles the scan
        # from this report's own preview, and they do not have to: a report
        # run after more pairs score, or with an explicit `parent_id`, asks
        # a campaign built for one parent about the variants of another.
        # `from_scores` then matches no variant and returns "parent not
        # scored", so the profile silently does not appear and nothing says
        # the campaign was about something else.
        #
        # campaign.json carries `parent` and `parent_sequence`, written by
        # the assembler. Reading the artefact's own record rather than
        # re-deriving is the same lesson as F137.
        design_dir = scored[-1].parent
        recorded = {}
        meta_path = design_dir / "campaign.json"
        if meta_path.exists():
            try:
                recorded = json.loads(meta_path.read_text())
            except (OSError, json.JSONDecodeError):
                recorded = {}
        scan_parent = recorded.get("parent")
        scan_sequence = recorded.get("parent_sequence")
        if not scan_parent and chosen:
            scan_parent = chosen["peptide_id"]
            scan_sequence = chosen["sequence"]

        if scan_parent:
            lifts = lift_module.from_scores(scored[-1], scan_parent)
            lifts["scan_parent"] = scan_parent
            lifts["scan_campaign"] = design_dir.name
            if chosen and chosen["peptide_id"] != scan_parent:
                lifts["note"] = (
                    f"the scan ran on {scan_parent} and this report ranks "
                    f"{chosen['peptide_id']} first, so the profile below is "
                    "the scan's parent and not the ranking's"
                )
            if lifts.get("lifts") and scan_sequence:
                objects = [lift_module.Lift(**item) for item in lifts["lifts"]]
                profile = lift_module.scan_profile(objects, scan_sequence)

    # The validation state of the score the arm would rank by. Reported
    # next to the rankings rather than buried: a ranked list reads as a
    # recommendation whatever the caption says.
    validation, caveat = _score_validation(campaign)

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
        # Derived from the status above, not asserted. See _score_validation.
        "caveat": caveat,
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
