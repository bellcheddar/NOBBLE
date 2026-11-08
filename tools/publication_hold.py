"""Refuse to publish while the atlas is held, and say what is being held and why.

Called from deploy/deploy.sh's pre-flight, before any connection to the
droplet is opened, so a held atlas costs nothing and touches nothing.

Two things about the shape of this, both deliberate:

  - No cutoff is defined here or in config/thresholds.toml. "Good enough to
    publish" is not a measurement, and inventing a success radius so that a
    script could decide it would be inventing the headline. The hold is a
    recorded decision (config/publication_hold.toml) and this reads it.

  - It still prints the live pose-recovery curve next to the recorded reason,
    read out of the campaign's own validation.json rather than copied into
    the config. A hold that quotes numbers from the day it was written goes
    stale silently, and the point of re-reading it on every deploy attempt is
    that the person releasing it sees what is true now.
"""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble import paths  # noqa: E402

DEFAULT_CONFIG = paths.CONFIG / "publication_hold.toml"


def read_hold(config: Path) -> dict:
    """The recorded decision. A missing file is a refusal, not a release."""
    if not config.exists():
        return {
            "held": True,
            "decision": "",
            "reason": f"{config} is missing, and an absent hold file is read as "
                      "held: a publication gate that opens when its own "
                      "configuration is deleted is not a gate.",
            "released_by": "",
        }
    with config.open("rb") as handle:
        return tomllib.load(handle)


def newest_validation() -> Path | None:
    """The most recent campaign that got as far as writing validation.json."""
    found = sorted(paths.CAMPAIGNS.glob("campaign_*/validation.json"))
    return found[-1] if found else None


def recovery_now(validation: Path | None) -> dict | None:
    """The pose-recovery layer's own summary, or None if it is not computed."""
    if validation is None or not validation.exists():
        return None
    try:
        layers = json.loads(validation.read_text()).get("layers", {})
    except json.JSONDecodeError:
        return None
    layer = layers.get("pose_recovery")
    if not isinstance(layer, dict) or not layer.get("computed"):
        return None
    summary = layer.get("summary")
    return summary if isinstance(summary, dict) else None


def confounded_pairs(campaign: Path | None) -> set[str] | None:
    """Pairs whose poses came from an input no longer on disk (F219).

    The validation layer cannot work this out, because it would mean a module
    under `nobble/` importing from `tools/` (D-NOB-080). This file is in
    `tools/`, so it can, and it must: without it the footprint below presents
    a confounded pair as measurable, which is F222's mistake one file over.

    None means the comparison could not be made, which is not the same as no
    pair being confounded.
    """
    if campaign is None:
        return None
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import stale_featurisation as featurisation
    except ImportError:
        return None
    try:
        rows = featurisation.disagreements(campaign)
    except OSError:
        return None
    return {row["job_id"].split("__")[0] for row in rows}


def representation_contrast() -> list[str]:
    """What the same pipeline does with the whole domain instead of a 15-mer.

    The hold's reason is that pose recovery fails its positive control. That
    is true of the campaign the atlas is built from, whose substrates are
    15-mer peptides, and not true of the method: the corrected-construct
    campaign supplies the whole folded domain and recovers six of seven pairs
    (F236). Whoever reads this is deciding whether to release the hold, and
    the comparison is the difference between "this cannot place a degron" and
    "this places a degron given its domain".

    Absent campaigns print as absent. The comparison costs about four
    seconds, which a deploy pre-flight can afford.
    """
    import glob

    benchmarks = sorted(glob.glob("campaigns/benchmark_*"))
    corrected = sorted(glob.glob("campaigns/corrected_*"))
    if not benchmarks or not corrected:
        return ["    representation: no corrected-construct campaign to compare"]
    try:
        from nobble.validate import compare

        report = compare.compare(Path(benchmarks[-1]), Path(corrected[-1]))
    except Exception as problem:                        # noqa: BLE001
        return [f"    representation: not compared "
                f"({type(problem).__name__}: {problem})"]

    improved = report.get("improved") or []
    worse = report.get("worse") or []
    compared = report.get("pairs_compared")

    # The same curve, in the same units the failure is quoted in.
    #
    # The hold's reason is "no pose reaches 3 A". That is the main campaign's
    # overall_curve, so what answers it is the corrected campaign's
    # overall_curve rather than a list of per-pair medians: 0 of 65 within
    # 3 A at a median of 17.54 A, against 53.8 per cent within 3 A at a
    # median of 2.494 A. Side by side, because they are one measurement on
    # two representations and the gate is about which the atlas is built from.
    curve_lines: list[str] = []
    corrected_summary = recovery_now(Path(corrected[-1]) / "validation.json")
    if corrected_summary:
        curve = corrected_summary.get("overall_curve") or {}
        within = ", ".join(
            f"within {key.removeprefix('within_').removesuffix('A')} A: {value}"
            for key, value in sorted(curve.items()) if key.startswith("within_"))
        curve_lines = [
            f"    the same curve on the whole-domain campaign: "
            f"{curve.get('n')} pose(s), median {curve.get('median_rmsd')} A",
            f"      {within}",
            # The caveat the time-split layer exists to make, beside the
            # number rather than only beside the retrospective one. All
            # seven depositions predate the 2021-09-30 training cutoff, so
            # there is no blind set: the 15-mer failure is not explained by
            # novelty and the whole-domain success is not generalisation
            # (F282).
            "      neither arm is prospective: all seven depositions predate "
            "the 2021-09-30 training cutoff, so the failure is not explained "
            "by novelty and the recovery is consistent with recall",
        ]

    lines = [
        f"    with the whole domain instead of a 15-mer: {len(improved)} of "
        f"{compared} pair(s) improved by more than 2 A, {len(worse)} worse, "
        f"control held: {report.get('control_held')}"
    ]
    # The control is named, because a row that does not move reads as a
    # failure to improve unless you know it is the row that must not move:
    # IKZF1's substrate is a linear epitope and was left as a 15-mer in both
    # campaigns, so its 0.000 is the comparison working.
    control = report.get("control") or {}
    control_gene = control.get("gene")
    for row in report.get("comparisons") or []:
        base = row.get("baseline_median_rmsd")
        corr = row.get("corrected_median_rmsd")
        if base is None or corr is None:
            continue
        gene = (row.get("gene") or row.get("pair_id")
                or row.get("corrected_pair") or "pair")
        note = ""
        if control_gene and gene == control_gene:
            # What the control controls for, which is not sampling noise.
            # It is the same 15-mer, PFQCNQCGASFTQKG, with the same five
            # seeds, re-run in a separate campaign, and Boltz is
            # deterministic given an input and a seed: F219 measured a re-run
            # as ipTM bit-identical to sixteen significant figures. So an
            # exact match is what a sound apparatus produces, and what this
            # rules out is a campaign-to-campaign offset in the comparison
            # itself rather than run-to-run variation. What rules out noise
            # is the size of the six improvements, 1.7 to 39.6 A (F269).
            note = ("   <- control: the same 15-mer and seeds re-run, so an "
                    "exact match is the apparatus agreeing with itself, not "
                    "an effect surviving noise")
        lines.append(f"      {str(gene):22s} {base:7.3f} -> {corr:7.3f} A{note}")
    return lines + curve_lines


def detector_control() -> list[str]:
    """Whether the primary signal finds the bridges in the crystals (F297).

    Decision-relevant to a release and not derivable from the lines above.
    The hold's reason is that pose recovery fails its positive control, which
    is a statement about where a peptide lands; spec 4.1's primary signal is
    the bridge geometry, and until F297 nothing had checked that against
    anything but its own output. Someone reading "the positive control fails"
    should also see that the filter the score is built on finds every bridge
    present in deposited coordinates.

    Crystals only. Rescoring the predictions beside them is the calibration
    and takes minutes; `tools/bridge_on_crystals.py --against-predictions`
    makes it. This is the verdict, and it costs about three seconds.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import bridge_on_crystals

        rows = bridge_on_crystals.crystal_rows()
    except Exception as problem:                        # noqa: BLE001
        return [f"    bridge detector: not checked "
                f"({type(problem).__name__}: {problem})"]

    measurable = [row for row in rows if row["measurable"]]
    found = [row for row in measurable if row["found"]]
    lines = [f"    bridge detector on deposited coordinates: {len(found)} of "
             f"{len(measurable)} measurable deposition(s) bridge, of "
             f"{len(rows)} benchmark pair(s)"]
    for row in rows:
        if not row["measurable"]:
            lines.append(f"      {row['pair_id']:28s} not measurable: "
                         f"{row['reject_reason']}")
        elif not row["found"]:
            lines.append(f"      {row['pair_id']:28s} MISSED: "
                         f"{row['reject_reason']}")
    return lines


def discrimination(campaign: Path | None) -> list[str]:
    """What the two paired designs say, for the person releasing the hold.

    The hold's recorded reason is that pose recovery fails its positive
    control, and this file already prints that curve live rather than quoting
    the day it was written. The same argument applies to discrimination,
    which is the other half of what a release claims: by the time anyone
    reads this, the question will be whether the score separates anything,
    and the answer moved twice on 2026-11-08.

    Three rows, because three is what fits beside everything else here and
    because they are the ones that decide a release:

      * the composite held out, which is what it does on a pair it was not
        fitted on (F312);
      * Delta-ipTM within the matched arm's own blocks, which is the
        best-controlled question the data can answer (F317);
      * Delta-ipTM against its own scramble, which is the easier question it
        passes (F316), included so the first two are not read as the whole
        picture.

    Absent tools or an unscored campaign print as absent. Nothing here
    recomputes a number this project computes elsewhere.
    """
    if campaign is None or not (campaign / "scores.jsonl").exists():
        return ["    discrimination: no scored campaign to read"]

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    lines: list[str] = []
    try:
        from nobble import paths as _paths

        import matched_arm_stratified
        import scramble_paired_test

        rows = _paths.read_jsonl(campaign / "scores.jsonl", tolerate_torn=True)
        blocks = matched_arm_stratified.report(rows)
        scrambles = scramble_paired_test.report({
            row["pair_id"]: row for row in rows if row.get("pair_id")})
    except Exception as problem:                        # noqa: BLE001
        return [f"    discrimination: not computed "
                f"({type(problem).__name__}: {problem})"]

    def row_of(report_, name, key="statistic"):
        for entry in report_.get("results") or []:
            if entry.get(key) == name:
                return entry
        return None

    held = row_of(blocks, "composite, held out")
    if held and held.get("mean_within_block_auc") is not None:
        lines.append(
            f"    composite, held out, within the matched arm's own blocks: "
            f"AUC {held['mean_within_block_auc']} over {held['blocks']} "
            f"block(s), p {held['p_two_sided']}")
    delta = row_of(blocks, "delta_iptm")
    if delta and delta.get("mean_within_block_auc") is not None:
        lines.append(
            f"    Delta-ipTM in the same blocks: "
            f"{delta['mean_within_block_auc']}"
            + ("  <- below chance" if delta["mean_within_block_auc"] < 0.5
               else ""))
    against = row_of(scrambles, "delta_iptm")
    if against and against.get("p_two_sided") is not None:
        lines.append(
            f"    Delta-ipTM against its own scramble: "
            f"{against['parent_higher']} to {against['scramble_higher']}, "
            f"p {against['p_two_sided']}. Telling a motif from its shuffle "
            "is the easier question and it passes that one")

    # The best single component, and the strongest result the project has
    # (F349). This printed the composite's held-out row and Delta-ipTM,
    # which are the two weakest readings in the table, and omitted the one
    # above them: a reader of the hold saw the project at its worst in one
    # direction and had no way to see it at its best in the other.
    best = row_of(blocks, "convergence_score")
    if best and best.get("mean_within_block_auc") is not None:
        lines.append(
            f"    convergence_score in the same blocks: "
            f"{best['mean_within_block_auc']}, p {best['p_two_sided']}  "
            f"<- the best single component, and still not significant")
    best_scramble = row_of(scrambles, "convergence_score")
    if best_scramble and best_scramble.get("p_two_sided") is not None:
        lines.append(
            f"    convergence_score against its own scramble: "
            f"{best_scramble['parent_higher']} to "
            f"{best_scramble['scramble_higher']}, "
            f"p {best_scramble['p_two_sided']}: the strongest thing here, "
            "with a mechanism (F342) and its confound measured (F344)")

    # And why "not significant" above is a power limit rather than an
    # absence, because without this the p values read as a weak result
    # (F349). The arithmetic is the project's own sign test over the
    # observed rate, not a figure typed in.
    lines.extend(_power_note(blocks))
    return lines or ["    discrimination: nothing comparable in this campaign"]


def _power_note(blocks: dict) -> list[str]:
    """The arm's own power figure, read rather than recomputed.

    This inverted the sign test here when F350 added it, which put a second
    copy of that arithmetic one directory from the first. It now lives in
    `matched_arm_stratified._power`, beside the arm it describes and the
    report the atlas already publishes, so the hold and `about.json` say
    the same thing by construction rather than by agreement (D-NOB-007).
    """
    power = blocks.get("power")
    if not power:
        return []
    if power.get("status"):
        return [f"    power: {power['status']}"]
    return [
        f"    power: at the best unfitted discrimination, "
        f"{power['statistic']}'s "
        f"{power['blocks_above_half']}/{power['decisive']}, clearing "
        f"{power['threshold']:g} needs about {power['needed_decisive']} "
        f"decisive blocks and the arm has {power['decisive']}. The screen "
        f"holds {power['positives_in_screen']} degraded zinc fingers of "
        f"which {power['positives_modellable']} are modellable, so this is "
        f"a limit of the design and not a measurement of the biology (F349)"]

def describe(summary: dict | None, confounded: set[str] | None = None) -> list[str]:
    """The curve as lines, or one line saying there is no curve to read."""
    if summary is None:
        return ["    pose recovery: not computed in the newest campaign"]
    curve = summary.get("overall_curve", {})
    pairs = summary.get("by_pair", {})
    lines = [
        f"    pose recovery over {curve.get('n')} pose(s) in "
        f"{len(pairs)} pair(s), median {curve.get('median_rmsd')} A",
    ]
    for key, value in sorted(curve.items()):
        if key.startswith("within_"):
            radius = key.removeprefix("within_").removesuffix("A")
            lines.append(f"      within {radius} A: {value}")
    for pair_id, record in sorted(pairs.items()):
        lines.append(f"      {pair_id:28s} median {record.get('median_rmsd')} A")

    # And where the poses are, not only how far.
    #
    # An RMSD alone cannot distinguish a model that never found the degron
    # site from one that found it and laid the chain along it in the wrong
    # register (F227), and the two read differently for a decision about
    # publishing. Whoever reads this is deciding whether to release the hold,
    # so the decision-relevant split belongs here rather than in a tool they
    # would have to know to run. Taken from the layer's own summary
    # (D-NOB-080), so it is the same numbers the campaign computed.
    footprint = summary.get("footprint")
    if not isinstance(footprint, dict) or not footprint:
        lines.append("    footprint: not computed in this campaign")
        return lines

    stale = confounded or set()
    measured = {pair: record for pair, record in footprint.items()
                if record.get("status") == "measured"
                and record.get("jaccard") is not None
                and pair not in stale}
    others = sorted(pair for pair in footprint if pair not in measured)
    unknown = "" if confounded is not None else (
        " (whether any pair is confounded could not be checked)")
    lines.append(f"    footprint of each pair's best pose, {len(measured)} of "
                 f"{len(footprint)} measurable{unknown}:")
    for pair_id, record in sorted(measured.items()):
        lines.append(
            f"      {pair_id:28s} contact jaccard {record.get('jaccard')}, "
            f"{record.get('window_residues_touched')} of "
            f"{record.get('window_residues')} window residue(s) touched")
    for pair_id in others:
        status = ("confounded: folded from a superseded input"
                  if pair_id in stale else
                  str(footprint[pair_id].get("status", "")).split(":")[0])
        lines.append(f"      {pair_id:28s} {status}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="the recorded decision to read")
    parser.add_argument("--campaign", type=Path, default=None,
                        help="a specific campaign directory, instead of the newest")
    args = parser.parse_args()

    hold = read_hold(args.config)
    validation = (args.campaign / "validation.json" if args.campaign
                  else newest_validation())
    lines = describe(recovery_now(validation),
                     confounded_pairs(validation.parent if validation else None))
    lines += representation_contrast()
    lines += detector_control()
    lines += discrimination(validation.parent if validation else None)

    if not hold.get("held"):
        released = str(hold.get("released_by") or "").strip()
        if not released:
            print("publication hold: the hold is marked released but names no "
                  "decision in `released_by`. Refusing: an unattributed release "
                  "is indistinguishable from an accident.", file=sys.stderr)
            return 2
        print(f"    publication released by {released}")
        for line in lines:
            print(line)
        return 0

    decision = str(hold.get("decision") or "an unrecorded decision").strip()
    reason = str(hold.get("reason") or "no reason recorded").strip()
    print(f"deploy: publication is held by {decision}.", file=sys.stderr)
    for paragraph in reason.splitlines():
        if paragraph.strip():
            print(f"        {paragraph.strip()}", file=sys.stderr)
    print("        What the newest campaign measures today:", file=sys.stderr)
    for line in lines:
        print(f"    {line.strip()}", file=sys.stderr)
    print(f"        To publish anyway, edit {args.config}: set held = false and "
          "name the authorising decision in `released_by`.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
