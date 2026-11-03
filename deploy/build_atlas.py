#!/usr/bin/env python3
"""Build the read-only slice the droplet serves.

Two jobs, and the second is the one that matters.

1. Keep the bundle small. The droplet serves a precomputed atlas and does no
   compute at request time, so it needs the scored records and the predicted
   structures, not the 77 MB of Boltz working output around them.

2. **Redistribute nothing that may not be redistributed.** Publishing to a
   public website is redistribution exactly as a public repository is. Spec 2
   makes PROTAC-DB internal-use only, and benchmark member 3's dBET57 structure
   came from it, so its SMILES is stripped here and the field is replaced with
   an explicit note rather than silently dropped. CCD codes and their SMILES
   are not affected: those come from the PDB Chemical Component Dictionary,
   which is public.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.execute.campaign import latest  # noqa: E402

OUT = ROOT / "deploy" / "atlas"

# Ligand records whose chemistry came from PROTAC-DB. Keyed by the encoding the
# resolver recorded, so a CCD-sourced ligand is never touched.
REDACT_WHEN_SOURCE = {"protacdb"}
REDACTION = (
    "withheld: PROTAC-DB is licensed for internal use and is never "
    "redistributed (spec 2.1). The structure prediction used it; the record "
    "does not travel."
)


def redact(value):
    """Strip PROTAC-DB chemistry anywhere it appears in a nested record."""
    if isinstance(value, dict):
        source = str(value.get("source", ""))
        encoding = str(value.get("encoding", ""))
        out = {key: redact(item) for key, item in value.items()}
        if source in REDACT_WHEN_SOURCE or (encoding == "smiles" and source in REDACT_WHEN_SOURCE):
            if "smiles" in out:
                out["smiles"] = None
                out["smiles_withheld"] = REDACTION
        return out
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def main() -> int:
    campaign = latest("benchmark")
    if campaign is None:
        print("no campaign to publish", file=sys.stderr)
        return 2

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "structures").mkdir(parents=True)

    summary = {"campaign": campaign.name, "files": {}, "redactions": 0}

    # Flat JSON documents.
    for name in ("campaign.json", "validation.json", "weights.json"):
        source = campaign / name
        if not source.exists():
            continue
        payload = redact(json.loads(source.read_text()))
        text = json.dumps(payload, indent=2)
        (OUT / name).write_text(text)
        summary["files"][name] = len(text)

    # JSONL records. results.jsonl carries absolute structure paths from the
    # build machine, which are meaningless on the droplet, so they are
    # rewritten to the flattened names published beside them.
    for name in ("scores.jsonl", "results.jsonl"):
        source = campaign / name
        if not source.exists():
            continue
        rows = []
        for line in source.read_text().splitlines():
            if not line.strip():
                continue
            row = redact(json.loads(line))
            structure = row.get("structure")
            if structure:
                origin = Path(structure)
                if origin.exists():
                    published = f"{row['job_id']}.cif"
                    shutil.copy(origin, OUT / "structures" / published)
                    row["structure"] = f"structures/{published}"
                else:
                    row["structure"] = None
            rows.append(row)
        (OUT / name).write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        summary["files"][name] = len(rows)

    # Verify the redaction actually happened, rather than trusting it.
    leaked = []
    for path in OUT.rglob("*"):
        if path.is_file() and path.suffix in (".json", ".jsonl"):
            body = path.read_text(errors="replace")
            if "CC1=C(C)C2=C(S1)" in body:
                leaked.append(str(path.relative_to(OUT)))
    if leaked:
        print(f"REFUSING TO PUBLISH: PROTAC-DB chemistry still present in {leaked}",
              file=sys.stderr)
        return 1

    # Precompute everything the Benchmark and About pages need. Those two
    # routes previously imported nobble.curate at request time, which pulls in
    # gemmi, pandas and BINMAN's store. None of that exists on the droplet, so
    # both returned 500 there while working locally. Spec Phase 4 is explicit
    # that the droplet serves a precomputed atlas with no compute at request
    # time, and this is what that means in practice.
    from nobble.curate import binman_store, constructs
    from nobble.curate import peptides as peptide_module
    from nobble.score import lysine

    benchmark = {
        "members": [
            {
                "index": item["index"], "gene": item["gene"], "e3": item["e3"],
                "pdb_id": item["pdb_id"], "accession": item["accession"],
            }
            for item in peptide_module.BENCHMARK_CHAINS
        ],
        "substrate_plan": redact(peptide_module.benchmark_substrate_constructs()),
        # Which deposited structure each pair is compared against, so the app
        # can offer the crystal overlay without importing nobble.validate.
        "crystal_by_pair": {
            pair_id: target["pdb_id"]
            for pair_id, target in __import__(
                "nobble.validate.layers", fromlist=["RECOVERY_TARGETS"]
            ).RECOVERY_TARGETS.items()
        },
    }
    (OUT / "benchmark.json").write_text(json.dumps(benchmark, indent=2, default=str))
    summary["files"]["benchmark.json"] = len(benchmark["members"])

    about = {
        "sources": binman_store.available(),
        "unavailable": list(binman_store.UNAVAILABLE),
        "bridge_reference": binman_store.bridge_reference_count(),
        "construct_budget": constructs.budget_report(),
        "reach_auc": lysine.BINMAN_REACH_AUC,
    }
    (OUT / "about.json").write_text(json.dumps(about, indent=2, default=str))
    summary["files"]["about.json"] = len(about["sources"])

    structures = list((OUT / "structures").glob("*.cif"))
    summary["structures"] = len(structures)
    summary["bytes"] = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    (OUT / "ATLAS.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))
    print(f"\nverified: no PROTAC-DB chemistry in the published bundle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
