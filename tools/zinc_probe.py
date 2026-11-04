"""Does a Sievers zinc finger fold without its zinc? Measure, do not assume.

D-NOB-034 added a ZN ion to every complete C2H2 finger in the Sievers arm,
reasoning from the chemistry: the fold is held together by a Zn(2+) ion
coordinated by two cysteines and two histidines, so a finger without one is
a disordered 23-mer rather than a domain. That reasoning is sound and still
might not matter in practice, because AlphaFold2 and Boltz generally predict
zinc-finger folds from sequence alone, having learned the mapping from
structures that did contain the ion.

So this probe measures it. Four peptide-only folds, no receptor and no glue:
one degraded finger and one non-degraded control, each with and without the
ion. Peptide-only is deliberate: the question is whether the chain folds,
and adding a 400-residue receptor would bury that in a number dominated by
the receptor.

What it reports is the mean pLDDT over the peptide chain. If the no-zinc
folds come back comparable, the ion is cheap insurance and the decision
stands on its own merits. If they come back materially worse, D-NOB-034 was
load-bearing and the arm would have measured noise without it.

Cost: four jobs of about 25 tokens. Seconds, not hours.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble import paths
from nobble.curate import library as LM
from nobble.execute import msa as msa_module
from nobble.execute import runner
from nobble.execute import yaml_gen as Y

PROBE = paths.CAMPAIGNS / "zinc_probe"


def _document(sequence: str, with_zinc: bool) -> dict:
    sequences: list[dict] = [{
        "protein": {"id": Y.PEPTIDE_CHAIN, "sequence": sequence,
                    "msa": msa_module.EMPTY},
    }]
    if with_zinc:
        sequences.append({"ligand": {"id": Y.COFACTOR_CHAIN, "ccd": "ZN"}})
    return {"version": 1, "sequences": sequences}


def _peptide_plddt(output_dir: Path) -> float | None:
    """Mean pLDDT over the peptide chain, read from the mmCIF B-factors."""
    import gemmi

    candidates = sorted(output_dir.rglob("*.cif"))
    if not candidates:
        return None
    structure = gemmi.read_structure(str(candidates[0]),
                                     format=gemmi.CoorFormat.Mmcif)
    values: list[float] = []
    for model in structure:
        for chain in model:
            for residue in chain:
                # Polymer only: the ion carries its own B-factor and would
                # otherwise be averaged into the chain's score.
                if residue.name == "ZN":
                    continue
                for atom in residue:
                    values.append(atom.b_iso)
        break
    return round(sum(values) / len(values), 2) if values else None


def main() -> int:
    library = LM.load()
    if library is None:
        print("no library manifest: run nobble.curate.library first", file=sys.stderr)
        return 2

    fingers = [r for r in library["peptides"] if r["source"] == "sievers_zf"]
    degraded = next(r for r in fingers if r["label"] == "degraded")
    control = next(r for r in fingers if r["label"] == "not_degraded")

    PROBE.mkdir(parents=True, exist_ok=True)
    settings = runner.settings_from_config(tier=1)

    results = []
    for row, role in ((degraded, "degraded"), (control, "not_degraded")):
        for with_zinc in (True, False):
            tag = f"{role}_{'zinc' if with_zinc else 'nozinc'}"
            yaml_path = PROBE / f"{tag}.yaml"
            yaml_path.write_text(Y.to_yaml_text(_document(row["sequence"], with_zinc)))
            job = {"job_id": tag, "yaml": str(yaml_path), "seed": 1,
                   "tokens": len(row["sequence"]) + (1 if with_zinc else 0)}
            print(f"--- {tag} ({row['gene']}, {len(row['sequence'])} aa)", flush=True)
            started = time.monotonic()
            outcome = runner.run_job(job, PROBE, settings)
            plddt = (_peptide_plddt(PROBE / "outputs" / tag)
                     if outcome.status == "done" else None)
            results.append({
                "tag": tag, "role": role, "zinc": with_zinc,
                "gene": row["gene"], "sequence": row["sequence"],
                "status": outcome.status,
                "seconds": round(time.monotonic() - started, 1),
                "peptide_plddt": plddt,
            })
            print(f"    {outcome.status}, peptide pLDDT {plddt}", flush=True)

    verdict = {"results": results}
    paired = {}
    for item in results:
        paired.setdefault(item["role"], {})[item["zinc"]] = item["peptide_plddt"]
    deltas = {
        role: (round(values[True] - values[False], 2)
               if values.get(True) is not None and values.get(False) is not None
               else None)
        for role, values in paired.items()
    }
    verdict["plddt_gain_from_zinc"] = deltas
    verdict["note"] = (
        "Positive gain means the ion improved the fold and D-NOB-034 is "
        "load-bearing. A gain near zero means Boltz already predicts the "
        "finger from sequence alone and the ion is cheap insurance rather "
        "than a fix. This is one finger per class and a single seed: it "
        "settles whether the effect is large, not its exact size."
    )
    (PROBE / "verdict.json").write_text(json.dumps(verdict, indent=2))
    print(json.dumps(verdict, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
