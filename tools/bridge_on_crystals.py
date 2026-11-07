"""Does the bridge detector find the bridge in the crystals, and get its size right?

Spec 4.1's primary signal is BINMAN's bridging filter, and every claim resting
on it (the bridge-formation rate, the bridge percentile, the whole-domain
contrast) assumes the filter finds a glue bridge when one is there and
measures it correctly. Until now that assumption was tested only against
predictions the filter had already scored as bridging
(`tests/test_geometry_real_bridge.py`), which asks whether it still agrees
with its own earlier verdict. The label came from the filter, so the test
cannot say whether the filter is right.

This puts the independent question. The seven benchmark pairs are compared
against seven deposited ternaries, each titled as a glue or degrader complex,
so a bridge is there as a matter of experimental record. The filter runs on
those coordinates through the same `geometry.bridge_from_groups` the campaign
used, and a deposition it does not call bridging is a false negative of the
instrument rather than a fact about the structure.

`--against-predictions` goes further and asks whether the measured area is
right, by rescoring each pair's predicted ternaries and printing the crystal
beside them. Two representations are printed because they answer different
questions: the main campaign submits a 15-mer substrate and the corrected
campaign submits the folded domain.

**Which crystal chains count as the receptor** is derived, not chosen. A
construct with one accession (CRBN_CULT, DDB1_BPC) is compared against the
one deposited receptor chain; a construct with several (VHL_VCB, which is
VHL with ElonginB and ElonginC, and DCAF15_DDB1_DDA1) is compared against
every non-substrate protein chain in the assembly, because that is the
surface its own prediction offers the glue. Comparing a multi-segment
prediction against a single deposited chain understates the crystal, which
is the F293 error in a geometry: the denominator has to be what was
intended.

Every one of these depositions predates the 2021-09-30 training cutoff
(F282), so agreement here is consistent with recall and is not evidence of
generalisation. The printed output says so.

Writes nothing. Needs gemmi, FreeSASA and BINMAN's pipeline package.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.curate import constructs as C                   # noqa: E402
from nobble.curate import structures                        # noqa: E402
from nobble.numeric import median_of                        # noqa: E402
from nobble.score import geometry                           # noqa: E402
from nobble.validate.layers import RECOVERY_TARGETS         # noqa: E402

# The pair id prefix each campaign gives the same benchmark member. The
# corrected campaign renamed bench01 to corr01 so the two could sit side by
# side, and this is the only place that correspondence is written down.
REPRESENTATIONS = (
    ("15-mer", "benchmark_*", "bench"),
    ("whole domain", "corrected_*", "corr"),
)


def glue_of(pdb_id: str) -> tuple[str | None, int | None]:
    """The largest modelled heteroatom, or (None, None) when there is none.

    Largest rather than first: an assembly can carry a metal or a buffer
    component beside the glue. The size floor is BINMAN's
    `ligand_min_heavy_atoms`, read from config by `structures.ligand_chains`,
    so this never decides for itself what counts as a compound.
    """
    found = structures.ligand_chains(pdb_id)
    if not found:
        return None, None
    best = max(found, key=lambda row: row["heavy_atoms"])
    return best["ccd"], best["seqid"]


def construct_of(pair_id: str) -> str | None:
    """The construct a benchmark pair's own jobs were built on."""
    for _label, pattern, _prefix in REPRESENTATIONS:
        for results in sorted(Path("campaigns").glob(f"{pattern}/results.jsonl")):
            for line in results.read_text().splitlines():
                if not line.strip():
                    continue
                job = json.loads(line)
                if job.get("pair_id") == pair_id:
                    return job.get("construct")
    return None


def receptor_side(pair_id: str, target: dict) -> tuple[str | None, str]:
    """(crystal receptor chain or None for every chain, why).

    None means every non-substrate protein chain, which is the comparator a
    multi-segment construct earns.
    """
    construct_name = construct_of(pair_id)
    if construct_name is None:
        return target["receptor_chain"], "no job found, so the named chain"
    accessions = {segment.accession
                  for segment in C.by_name(construct_name).segments}
    if len(accessions) > 1:
        return None, (f"{construct_name} offers {len(accessions)} accessions, "
                      "so every non-substrate chain")
    return target["receptor_chain"], f"{construct_name} is one accession"


def crystal_rows(force_whole: bool | None = None) -> list[dict]:
    out = []
    for pair_id, target in sorted(RECOVERY_TARGETS.items()):
        pdb_id = target["pdb_id"]
        ccd, seqid = glue_of(pdb_id)
        if force_whole is None:
            chain, why = receptor_side(pair_id, target)
        else:
            chain = None if force_whole else target["receptor_chain"]
            why = "forced on the command line"
        score = geometry.score_deposition(
            pdb_id, chain, target["substrate_chain"], ccd, seqid)
        record = score.to_dict()
        record.update({
            "pair_id": pair_id, "pdb_id": pdb_id, "glue_ccd": ccd,
            "receptor_chain": chain, "receptor_choice": why,
            "substrate_chain": target["substrate_chain"],
            "measurable": score.reject_reason not in (
                "deposition_not_cached", "glue_not_modelled_in_deposition"),
        })
        out.append(record)
    return out


def predicted_rows() -> dict[tuple[str, str], dict]:
    """Rescored predicted ternaries, keyed by (representation, benchmark number).

    Rescored rather than read out of `scores.jsonl`, which persists only
    `dsasa_total_median`: the receptor and substrate halves are what separate
    a glue sitting correctly in the E3 pocket from a substrate burying enough
    surface, and that is the whole point of the comparison.
    """
    out: dict[tuple[str, str], dict] = {}
    for label, pattern, prefix in REPRESENTATIONS:
        per: dict[str, list[tuple]] = {}
        for results in sorted(Path("campaigns").glob(f"{pattern}/results.jsonl")):
            for line in results.read_text().splitlines():
                if not line.strip():
                    continue
                job = json.loads(line)
                pair_id = str(job.get("pair_id") or "")
                if (job.get("complex_type") != "ternary"
                        or not pair_id.startswith(prefix)):
                    continue
                number = pair_id[len(prefix):len(prefix) + 2]
                try:
                    score = geometry.score_structure(job)
                except Exception as problem:                # noqa: BLE001
                    per.setdefault(number, [])
                    continue
                per.setdefault(number, [])
                if score.found:
                    per[number].append(
                        (score.dsasa_receptor, score.dsasa_peptide,
                         score.dsasa_total))
        for number, values in per.items():
            out[(label, number)] = {
                "n_bridged": len(values),
                "receptor": median_of([v[0] for v in values]) if values else None,
                "substrate": median_of([v[1] for v in values]) if values else None,
                "total": median_of([v[2] for v in values]) if values else None,
            }
    return out


def _ratio(predicted, crystal) -> str:
    if not predicted or not crystal:
        return "    -"
    return f"{predicted / crystal:5.2f}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--whole-assembly", action="store_true",
                       help="force every non-substrate chain as the receptor")
    group.add_argument("--named-chain-only", action="store_true",
                       help="force the one named receptor chain")
    parser.add_argument("--against-predictions", action="store_true",
                        help="rescore the predictions and print them beside")
    parser.add_argument("--json", action="store_true", help="rows as JSON")
    args = parser.parse_args(argv)

    forced = (True if args.whole_assembly
              else False if args.named_chain_only else None)
    crystals = crystal_rows(forced)
    predictions = predicted_rows() if args.against_predictions else {}

    if args.json:
        print(json.dumps({"crystals": crystals,
                          "predictions": {f"{k[0]}|{k[1]}": v
                                          for k, v in predictions.items()}},
                         indent=2))
        return 0

    measurable = [row for row in crystals if row["measurable"]]
    found = [row for row in measurable if row["found"]]
    print("bridge detector on deposited coordinates")
    print(f"  {len(found)} of {len(measurable)} measurable deposition(s) found "
          f"to bridge, out of {len(crystals)} benchmark pair(s)")
    for row in crystals:
        if not row["measurable"]:
            print(f"  {row['pair_id']:24s} {row['pdb_id']}  not measurable: "
                  f"{row['reject_reason']}")
            for note in row["notes"]:
                print(f"      {note}")
            continue
        if not row["found"]:
            print(f"  {row['pair_id']:24s} {row['pdb_id']}  MISSED: "
                  f"{row['reject_reason']}")
            for note in row["notes"]:
                print(f"      {note}")
            continue
        chain = row["receptor_chain"] or "all"
        print(f"  {row['pair_id']:24s} {row['pdb_id']}  {row['glue_ccd']:>4s}  "
              f"receptor {row['dsasa_receptor']:7.1f}  "
              f"substrate {row['dsasa_peptide']:7.1f}  "
              f"total {row['dsasa_total']:7.1f} A^2  "
              f"percentile {row['bridge_percentile']:6.2f}  "
              f"[receptor chain {chain}: {row['receptor_choice']}]")

    if not args.against_predictions:
        return 0

    print()
    print("  the same bridge as predicted, median over the seeds that bridged")
    print(f"  {'pair':24s} {'representation':14s} {'n':>3s} "
          f"{'receptor':>9s} {'substrate':>10s} {'total':>9s} "
          f"{'total/xtal':>10s}")
    for row in crystals:
        number = row["pair_id"][len("bench"):len("bench") + 2]
        for label, _pattern, _prefix in REPRESENTATIONS:
            record = predictions.get((label, number))
            if record is None:
                continue
            if record["total"] is None:
                print(f"  {row['pair_id']:24s} {label:14s} "
                      f"{record['n_bridged']:3d} "
                      f"{'no seed bridged':>31s}")
                continue
            print(f"  {row['pair_id']:24s} {label:14s} {record['n_bridged']:3d} "
                  f"{record['receptor']:9.1f} {record['substrate']:10.1f} "
                  f"{record['total']:9.1f} "
                  f"{_ratio(record['total'], row['dsasa_total']):>10s}")
    print()
    print("  every deposition above predates the 2021-09-30 training cutoff "
          "(F282),")
    print("  so agreement is consistent with recall and is not evidence of "
          "generalisation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
