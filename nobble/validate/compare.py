"""Compare two campaigns on the same benchmark pairs (FINDINGS.md F6).

The corrected-construct campaign changes exactly one thing: whether a
domain-mediated substrate is submitted as a 15-mer or as its whole domain.
Everything else, the receptor, the ligand, the seeds, the deposited structure
compared against, is held constant. So a pair-by-pair difference in pose
recovery is attributable to the construct, and this module computes it.

Two things make the comparison honest rather than flattering:

- **The control is reported first.** IKZF1 keeps its 15-mer in both campaigns
  and already recovers at about 5 angstrom. If its number moves, something
  other than the construct changed and the whole comparison is suspect, so it
  is checked before anything else is believed.
- **The frame quality travels with every number.** A pose RMSD means nothing
  without the receptor anchor it was measured against, and a change in RMSD
  means nothing if the anchor also changed.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from nobble import paths
from nobble.numeric import finite, finite_values, median_of

# The control: unchanged between campaigns by design.
CONTROL_GENE = "IKZF1"
# A control that moves by more than this invalidates the comparison.
CONTROL_TOLERANCE_A = float(paths.thresholds()["scoring"]["control_tolerance_a"])
# The cutoff behind "F6 supported". It was a literal here, which is exactly
# what CLAUDE.md forbids: the number that decides the headline conclusion
# could not be changed or even found without reading this function.
CHANGE_MARGIN_A = float(paths.thresholds()["scoring"]["campaign_change_margin_a"])


@dataclass
class PairComparison:
    gene: str
    e3: str
    baseline_pair: str | None
    corrected_pair: str | None
    substrate_mode: str | None = None
    baseline_median_rmsd: float | None = None
    corrected_median_rmsd: float | None = None
    delta_rmsd: float | None = None
    baseline_anchor_rmsd: float | None = None
    corrected_anchor_rmsd: float | None = None
    baseline_poses: int = 0
    corrected_poses: int = 0
    # Bridge formation, which is independent evidence rather than a second
    # view of the same thing: pose recovery compares a prediction to a
    # deposited crystal, while bridge formation asks only whether the glue
    # touches both chains inside the prediction. F17 found the two agree,
    # and the comparison was reporting only the first.
    baseline_bridged: str | None = None
    corrected_bridged: str | None = None
    bridge_rate_change: float | None = None
    is_control: bool = False
    verdict: str = "pending"

    def to_dict(self) -> dict:
        return asdict(self)


def _recovery_by_pair(campaign: Path) -> dict[str, dict]:
    """Median peptide RMSD and median anchor RMSD per pair."""
    from nobble.validate.layers import pose_recovery

    layer = pose_recovery(campaign)
    if not layer.computed:
        return {}

    anchors: dict[str, list[float]] = {}
    for record in layer.detail:
        job = record.get("job_id") or ""
        pair = job.split("__")[0] if "__" in job else None
        value = record.get("receptor_rmsd")
        if pair and finite(value):
            anchors.setdefault(pair, []).append(value)

    out = {}
    for pair_id, stats in layer.summary["by_pair"].items():
        anchor = sorted(finite_values(anchors.get(pair_id, [])))
        out[pair_id] = {
            "median_rmsd": stats["median_rmsd"],
            "poses": stats["n"],
            "anchor_rmsd": median_of(anchor),
        }
    return out


def _bridging_by_pair(campaign: Path) -> dict[str, dict]:
    """Seeds that produced a bridge, per pair, from the scored records."""
    scores = campaign / "scores.jsonl"
    if not scores.exists():
        return {}
    out: dict[str, dict] = {}
    for line in scores.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        total = row.get("bridging_seeds_total")
        if not total:
            continue
        out[row["pair_id"]] = {
            "with_bridge": row.get("bridging_seeds_with_bridge") or 0,
            "total": total,
            "rate": row.get("bridge_formation_rate"),
            "reject_reasons": row.get("bridge_reject_reasons") or {},
        }
    return out


def _gene_of(pair_id: str) -> tuple[str, str]:
    """bench01_GSPT1_CRBN or corr01_GSPT1_CRBN to (GSPT1, CRBN)."""
    parts = pair_id.split("_")
    return (parts[1], parts[2]) if len(parts) >= 3 else (pair_id, "")


def _recovery_curve(campaign: Path) -> dict:
    """A campaign's own pose-recovery curve, or why there is none.

    Read from the campaign's `validation.json` rather than recomputed: the
    layer that wrote it is the same one whose number the headline quotes, and
    recomputing would put a second answer to one question in the bundle.
    """
    path = Path(campaign) / "validation.json"
    if not path.exists():
        return {"status": f"not computed: no validation.json in {Path(campaign).name}"}
    try:
        layers = json.loads(path.read_text()).get("layers", {})
    except (OSError, json.JSONDecodeError) as problem:
        return {"status": f"not read: {type(problem).__name__}: {problem}"}
    layer = layers.get("pose_recovery") or {}
    if not layer.get("computed"):
        return {"status": layer.get("status") or "not computed"}
    curve = (layer.get("summary") or {}).get("overall_curve")
    if not curve:
        return {"status": "computed, but the layer wrote no overall curve"}
    return {"status": "computed", "campaign": Path(campaign).name, **curve}


def compare(baseline: Path, corrected: Path) -> dict:
    base_recovery = _recovery_by_pair(baseline)
    corr_recovery = _recovery_by_pair(corrected)
    base_bridging = _bridging_by_pair(baseline)
    corr_bridging = _bridging_by_pair(corrected)

    # The two campaign builders disagreed on one key: the benchmark one writes
    # `pairs` as a count with the records under `pair_detail`, the corrected one
    # writes the records under `pairs`. Both files already exist on disk, so the
    # reader accepts either rather than only the newer shape.
    modes = {}
    campaign_json = corrected / "campaign.json"
    if campaign_json.exists():
        payload = json.loads(campaign_json.read_text())
        records = payload.get("pairs")
        if not isinstance(records, list):
            records = payload.get("pair_detail") or []
        for pair in records:
            if not isinstance(pair, dict):
                continue
            gene = pair.get("gene") or pair.get("peptide_gene")
            e3 = pair.get("e3") or pair.get("e3_gene")
            if gene and e3:
                modes[(gene, e3)] = pair.get("substrate_mode")

    keyed_base = {_gene_of(p): (p, v) for p, v in base_recovery.items()}
    keyed_corr = {_gene_of(p): (p, v) for p, v in corr_recovery.items()}
    bridge_base = {_gene_of(p): v for p, v in base_bridging.items()}
    bridge_corr = {_gene_of(p): v for p, v in corr_bridging.items()}

    comparisons = []
    for key in sorted(set(keyed_base) | set(keyed_corr)):
        gene, e3 = key
        bp, bv = keyed_base.get(key, (None, {}))
        cp, cv = keyed_corr.get(key, (None, {}))
        item = PairComparison(
            gene=gene, e3=e3, baseline_pair=bp, corrected_pair=cp,
            substrate_mode=modes.get(key),
            baseline_median_rmsd=bv.get("median_rmsd"),
            corrected_median_rmsd=cv.get("median_rmsd"),
            baseline_anchor_rmsd=bv.get("anchor_rmsd"),
            corrected_anchor_rmsd=cv.get("anchor_rmsd"),
            baseline_bridged=(
                f"{bridge_base[key]['with_bridge']}/{bridge_base[key]['total']}"
                if key in bridge_base else None),
            corrected_bridged=(
                f"{bridge_corr[key]['with_bridge']}/{bridge_corr[key]['total']}"
                if key in bridge_corr else None),
            bridge_rate_change=(
                round((bridge_corr[key].get("rate") or 0)
                      - (bridge_base[key].get("rate") or 0), 3)
                if key in bridge_base and key in bridge_corr else None),
            baseline_poses=bv.get("poses", 0),
            corrected_poses=cv.get("poses", 0),
            is_control=(gene == CONTROL_GENE),
        )
        if item.baseline_median_rmsd is not None and item.corrected_median_rmsd is not None:
            item.delta_rmsd = round(
                item.corrected_median_rmsd - item.baseline_median_rmsd, 3
            )
            if item.is_control:
                item.verdict = (
                    "control held" if abs(item.delta_rmsd) <= CONTROL_TOLERANCE_A
                    else "CONTROL MOVED: the comparison is not trustworthy"
                )
            elif item.delta_rmsd < -CHANGE_MARGIN_A:
                item.verdict = "improved"
            elif item.delta_rmsd > CHANGE_MARGIN_A:
                item.verdict = "worse"
            else:
                item.verdict = "unchanged"
        else:
            item.verdict = "incomplete: one campaign has no recovery number yet"
        comparisons.append(item)

    control = next((c for c in comparisons if c.is_control), None)
    control_ok = control is not None and control.verdict == "control held"
    improved = [c for c in comparisons if c.verdict == "improved"]
    worse = [c for c in comparisons if c.verdict == "worse"]

    if control is None or control.delta_rmsd is None:
        conclusion = (
            "not concluded: the IKZF1 control has no number in both campaigns, "
            "so a difference in the other pairs cannot yet be attributed to the "
            "construct"
        )
    elif not control_ok:
        conclusion = (
            "NOT TRUSTWORTHY: the control moved by "
            f"{control.delta_rmsd} A. Something other than the substrate "
            "construct differs between these campaigns, and the other "
            "differences cannot be attributed to the construct until that is "
            "explained"
        )
    elif improved and not worse:
        conclusion = (
            f"F6 supported: {len(improved)} pair(s) improved by more than "
            f"{CHANGE_MARGIN_A:g} A with the whole domain, the control held, "
            "and none got worse"
        )
    elif not improved and not worse:
        conclusion = (
            "F6 not supported: the control held, and no pair changed by more "
            f"than {CHANGE_MARGIN_A:g} A. The 15-mer was not what limited pose "
            "recovery, so the limitation is the model or the sampling, not the "
            "construct"
        )
    elif worse and not improved:
        # The direction this function had no word for. "mixed" was used
        # for it, and nothing is mixed when every pair that changed got
        # worse: it is F6 contradicted, the whole domain recovering poses
        # less well than the 15-mer, which is a result and the kind this
        # project publishes rather than softens (F200).
        conclusion = (
            f"F6 contradicted: {len(worse)} pair(s) got worse by more than "
            f"{CHANGE_MARGIN_A:g} A with the whole domain, the control held, "
            "and none improved. The 15-mer was not the limitation for these "
            "pairs and the whole domain is worse for them"
        )
    else:
        # Both directions present, which is the only reading of "mixed".
        # The control is held by construction here: the two branches above
        # the F6 ones return for every state in which it is not, so this
        # said `'held' if control_ok else 'moved'` with a false arm that
        # could never run (F200).
        conclusion = (
            f"mixed: {len(improved)} improved, {len(worse)} worse, control held"
        )

    # Bridge formation, reported beside the verdict rather than folded into
    # it. The verdict stays RMSD-based because that is what F6 is about and
    # what the 2 A thresholds are calibrated on; silently widening the
    # criterion would change what "F6 supported" means without saying so.
    # But a reader of the conclusion should see that a second, independent
    # measurement moved the same way (F17), because two measurements
    # agreeing is a much stronger claim than either alone.
    gained = [c for c in comparisons
              if c.bridge_rate_change is not None and c.bridge_rate_change > 0]
    lost = [c for c in comparisons
            if c.bridge_rate_change is not None and c.bridge_rate_change < 0]
    if gained and not lost:
        conclusion += (
            f". Bridge formation agrees and is independent of the crystal: "
            f"{len(gained)} pair(s) bridged in more seeds and none in fewer"
        )
    elif lost:
        conclusion += (
            f". Bridge formation disagrees: {len(lost)} pair(s) bridged in "
            f"fewer seeds with the whole domain"
        )

    # A verdict over a partially run campaign is a verdict about whichever
    # pairs happen to have finished. Saying so is the difference between a
    # result and a progress report, and the conclusion is the line that gets
    # quoted: the per-pair table already marks the gaps, but nobody reads a
    # table to check whether the sentence above it was qualified.
    incomplete = [c for c in comparisons if c.verdict.startswith("incomplete")]
    if incomplete and not conclusion.startswith("not concluded"):
        missing = ", ".join(sorted(c.gene for c in incomplete))
        conclusion += (
            f". Provisional: {len(incomplete)} of {len(comparisons)} pair(s) "
            f"have not finished in both campaigns ({missing})"
        )

    # A pair whose corrected construct is not the domain the plan now
    # specifies is still a measurement, of a different construct. The
    # boundaries come from an InterPro lookup, so a fix to how an ambiguous
    # entry is resolved moves them, and a campaign run before that fix holds
    # an input the code would no longer emit.
    #
    # Said on the conclusion rather than only in the table, for the same
    # reason the incomplete caveat is: the sentence is the line that gets
    # quoted, and CSNK1A1 is one of the pairs in the improved list (F93).
    from nobble.validate import inputs as input_check

    superseded = input_check.superseded_substrates(corrected)
    if superseded:
        genes = ", ".join(sorted(
            next((c.gene for c in comparisons
                  if c.corrected_pair == row["pair_id"]), row["pair_id"])
            for row in superseded))
        conclusion += (
            f". {len(superseded)} pair(s) used a substrate domain the plan no "
            f"longer specifies ({genes}): the measurement stands and describes "
            "a different construct from the one the plan beside it gives"
        )

    return {
        "baseline": baseline.name,
        "corrected": corrected.name,
        "pairs_compared": len(comparisons) - len(incomplete),
        "pairs_incomplete": len(incomplete),
        "provisional": bool(incomplete),
        "superseded_substrates": superseded,
        # Each campaign's own pose-recovery curve, in the units the headline
        # failure is quoted in.
        #
        # The published bundle said "0 of 65 within 3 A, median 17.535" in
        # validation.json and told the whole-domain story in comparison.json,
        # with no curve in it and no cross-reference either way. So a reader
        # of the validation tab saw the negative without the measurement that
        # scopes it: the same statistic on the whole-domain campaign is 53.8
        # per cent within 3 A at a median of 2.494 A (F236).
        #
        # Here rather than in `layers.pose_recovery`, which is about one
        # campaign and should not go looking for another, and rather than in
        # the atlas build, which would make the contrast a property of
        # publishing. This function's whole job is the two campaigns.
        "baseline_recovery_curve": _recovery_curve(baseline),
        "corrected_recovery_curve": _recovery_curve(corrected),
        "control": control.to_dict() if control else None,
        "control_held": control_ok,
        "comparisons": [c.to_dict() for c in comparisons],
        "improved": [c.gene for c in improved],
        "worse": [c.gene for c in worse],
        "conclusion": conclusion,
    }


def run(baseline: Path, corrected: Path) -> dict:
    report = compare(baseline, corrected)
    (corrected / "comparison.json").write_text(json.dumps(report, indent=2, default=str))
    return report
