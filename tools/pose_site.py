#!/usr/bin/env python3
"""Is the predicted degron at the wrong site, or in the wrong pose there?

Pose recovery fails: 0 of 65 poses within 3 A, median 17.54 A (F212), and
tier-2 refinement sharpens without recovering (F215). Two very different
things fit that number. The peptide could be bound somewhere else on the
complex, in which case the model has not found the degron site at all. Or it
could be in the right groove in the wrong register, in which case it has
found the site and placed the chain along it badly. A single RMSD cannot
tell them apart, and the headline reads differently depending on which it is.

This asks the question the RMSD cannot: superpose on the receptor exactly as
`poses.recovery_against_crystal` does, then compare footprints. Which
receptor residues does the deposited degron window touch, which does the
predicted peptide touch, and how many of the window's own residues does the
prediction land on.

**No verdict is emitted and no cutoff is introduced.** Calling a Jaccard of
0.3 "the right site" would be inventing an acceptance threshold to decide a
gate, which is the thing D-NOB-076 explicitly refused to do for pose
recovery. The contact distance comes from `config/thresholds.toml`.

Two states are reported rather than scored:

* `not_measurable`: the deposited window makes no contact with the receptor
  chain within the cutoff, so the overlap is zero however good the pose is.
  bench03_BRD4_CRBN is this: its window sits on BRD4 against the glue, not
  against CRBN.
* `confounded`: the pair's tier-1 poses were folded from a superseded input
  (F219), so its footprint is not a measurement of the current input.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths
from nobble.curate import constructs as C
from nobble.curate import numbering, structures
from nobble.score import poses
from nobble.validate.layers import recovery_target


def contact_cutoff() -> float:
    """The peptide-receptor heavy-atom contact distance, from config."""
    for section in paths.thresholds().values():
        if isinstance(section, dict) and "contact_cutoff_a" in section:
            return float(section["contact_cutoff_a"])
    raise KeyError("contact_cutoff_a is not in config/thresholds.toml")


def _heavy(residue) -> list:
    return [atom.pos for atom in residue if atom.element.name != "H"]


def _touched(probe: list, residues: dict, cutoff: float) -> set:
    return {number for number, atoms in residues.items()
            if any(a.dist(p) <= cutoff for a in atoms for p in probe)}


def _centroid(points: list) -> tuple[float, float, float]:
    count = len(points)
    return (sum(p.x for p in points) / count,
            sum(p.y for p in points) / count,
            sum(p.z for p in points) / count)


def _confounded(campaign: Path) -> set[str]:
    """Pairs whose poses came from an input no longer on disk (F219)."""
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import stale_featurisation as featurisation
    except ImportError:
        return set()
    try:
        rows = featurisation.disagreements(campaign)
    except OSError:
        return set()
    return {row["job_id"].split("__")[0] for row in rows}


def _best_per_pair(campaign: Path) -> dict[str, dict]:
    validation = campaign / "validation.json"
    if not validation.exists():
        return {}
    layer = json.loads(validation.read_text())["layers"].get("pose_recovery", {})
    best: dict[str, dict] = {}
    for row in layer.get("detail") or []:
        if row.get("rmsd") is None:
            continue
        current = best.get(row["pair_id"])
        if current is None or row["rmsd"] < current["rmsd"]:
            best[row["pair_id"]] = row
    return best


def footprints(campaign: Path, cutoff: float | None = None,
               only: set[str] | None = None) -> list[dict]:
    """One record per pair, for the lowest-RMSD ternary pose it has.

    `only` restricts to named pairs. Each record reads two structures off
    disk and walks every residue pair, so a test that needs one pair
    should ask for one pair.
    """
    campaign = Path(campaign)
    cutoff = contact_cutoff() if cutoff is None else cutoff
    confounded = _confounded(campaign)
    results = {row["job_id"]: row for row in
               (json.loads(line) for line
                in (campaign / "results.jsonl").read_text().splitlines()
                if line.strip())}

    records = []
    for pair_id, best in sorted(_best_per_pair(campaign).items()):
        if only is not None and pair_id not in only:
            continue
        record = {"pair_id": pair_id, "job_id": best["job_id"],
                  "rmsd": best["rmsd"], "status": "measured"}
        if pair_id in confounded:
            record["status"] = "confounded"
        target = recovery_target(pair_id)
        job = results.get(best["job_id"])
        if target is None or job is None or not job.get("structure"):
            record["status"] = "no_structure"
            records.append(record)
            continue

        predicted = poses._load(job["structure"])
        deposited = structures.read_assembly(target["pdb_id"])
        construct = C.by_name(job["construct"])
        index = next((i for i, segment in enumerate(construct.segments)
                      if segment.accession == target["receptor_acc"]), None)
        if index is None:
            record["status"] = "receptor_not_a_segment"
            records.append(record)
            continue
        segment_start, _ = construct.segments[index].range()
        predicted_receptor = "ABCDEFGH"[index]
        receptor_frame = numbering.resolve_frame(
            target["pdb_id"], target["receptor_chain"], target["receptor_acc"])
        substrate_frame = numbering.resolve_frame(
            target["pdb_id"], target["substrate_chain"], target["substrate_acc"])

        receptor_residues: dict[int, list] = {}
        backbone: dict[tuple[int, str], object] = {}
        substrate_residues: dict[int, list] = {}
        for chain in deposited[0]:
            if chain.name == target["receptor_chain"]:
                for residue in chain:
                    receptor_residues[residue.seqid.num] = _heavy(residue)
                    for atom in residue:
                        if atom.name in poses.BACKBONE:
                            backbone[(residue.seqid.num, atom.name)] = atom.pos
            if chain.name == target["substrate_chain"]:
                for residue in chain:
                    substrate_residues[residue.seqid.num] = _heavy(residue)

        moving, fixed = [], []
        for chain in predicted[0]:
            if chain.name != predicted_receptor:
                continue
            for residue in chain:
                number = receptor_frame.to_deposited(
                    segment_start + residue.seqid.num - 1)
                for atom in residue:
                    if atom.name not in poses.BACKBONE:
                        continue
                    anchor = backbone.get((number, atom.name))
                    if anchor is not None:
                        moving.append(atom.pos)
                        fixed.append(anchor)
        transform = poses._superpose(moving, fixed)
        if transform is None:
            record["status"] = "receptor_anchor_too_small"
            records.append(record)
            continue
        record["receptor_anchor_atoms"] = len(moving)

        start = job.get("peptide_start_res") or poses._peptide_start_from_library(
            job.get("peptide_id"))
        if start is None:
            record["status"] = "peptide_start_unknown"
            records.append(record)
            continue

        window: set[int] = set()
        predicted_peptide = []
        for chain in predicted[0]:
            if chain.name != poses.PEPTIDE_CHAIN:
                continue
            for residue in chain:
                number = substrate_frame.to_deposited(start + residue.seqid.num - 1)
                if number in substrate_residues:
                    window.add(number)
                for atom in residue:
                    if atom.element.name == "H":
                        continue
                    moved = transform.apply(atom.pos)
                    predicted_peptide.append(
                        type(atom.pos)(moved.x, moved.y, moved.z))
        window_atoms = [atom for number in window
                        for atom in substrate_residues[number]]
        if not window_atoms or not predicted_peptide:
            record["status"] = "window_unresolved"
            records.append(record)
            continue

        true_site = _touched(window_atoms, receptor_residues, cutoff)
        predicted_site = _touched(predicted_peptide, receptor_residues, cutoff)
        shared = true_site & predicted_site
        union = true_site | predicted_site
        record.update({
            "window_residues": len(window),
            "centroid_gap_a": round(math.dist(
                _centroid(predicted_peptide), _centroid(window_atoms)), 2),
            "deposited_contacts": len(true_site),
            "predicted_contacts": len(predicted_site),
            "shared_contacts": len(shared),
            "jaccard": round(len(shared) / len(union), 3) if union else None,
            "window_residues_touched": len(_touched(
                predicted_peptide,
                {number: substrate_residues[number] for number in window},
                cutoff)),
            "cutoff_a": cutoff,
        })
        if not true_site:
            # Zero overlap is guaranteed here whatever the pose is, so the
            # Jaccard is not a measurement of this prediction.
            record["status"] = ("not_measurable: the deposited window makes no "
                                "receptor contact within the cutoff")
        records.append(record)
    return records


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", nargs="?", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    campaign = args.campaign
    if campaign is None:
        from nobble.execute.campaign import latest
        campaign = latest("campaign") or latest("benchmark")
    if campaign is None:
        print("no campaign found", file=sys.stderr)
        return 2

    records = footprints(Path(campaign))
    if args.json:
        print(json.dumps(records, indent=2))
        return 0
    if not records:
        print("no pose recovery detail to read: run validation first")
        return 2

    cutoff = records[0].get("cutoff_a", contact_cutoff())
    print(f"footprint of the lowest-RMSD pose per pair, contacts within "
          f"{cutoff} A\n")
    print(f"{'pair':24} {'rmsd':>6} {'gap':>6} {'dep':>4} {'pred':>5} "
          f"{'shared':>6} {'jacc':>6} {'onWindow':>9}")
    for record in records:
        if "jaccard" not in record:
            print(f"{record['pair_id']:24} {record['rmsd']:6.2f}"
                  f"{'':40} {record['status']}")
            continue
        flag = "" if record["status"] == "measured" else f"  <- {record['status']}"
        print(f"{record['pair_id']:24} {record['rmsd']:6.2f} "
              f"{record['centroid_gap_a']:6.2f} {record['deposited_contacts']:4d} "
              f"{record['predicted_contacts']:5d} {record['shared_contacts']:6d} "
              f"{record['jaccard'] if record['jaccard'] is not None else '--':>6} "
              f"{record['window_residues_touched']:4d}"
              f"/{record['window_residues']:<4d}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
