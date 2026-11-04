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

from nobble import paths  # noqa: E402
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

    # What else was assembled or running when this slice was built. The
    # droplet cannot see the Studio's queues, so without this the header
    # says COMPLETE while the main campaign is still to run and a visitor
    # concludes the science is finished. Recorded as a fact about build
    # time, not a live feed: it is only as fresh as the last deploy, and
    # the note on the panel says so.
    outstanding = []
    for other in sorted(paths.CAMPAIGNS.glob("*")):
        if not other.is_dir() or other.name == campaign.name:
            continue
        queue = other / "queue.jsonl"
        if not queue.exists():
            continue
        total = sum(1 for line in queue.read_text().splitlines() if line.strip())
        state = other / "state.jsonl"
        done = 0
        if state.exists():
            import json as _json
            done = len({
                _json.loads(line)["job_id"]
                for line in state.read_text().splitlines()
                if line.strip() and _json.loads(line).get("status") == "done"
            })
        if done < total:
            outstanding.append({"campaign": other.name, "jobs_done": done,
                                "jobs_total": total})
    summary["outstanding"] = outstanding

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

    # The design arm (DESIGN_ARM.md). Built here rather than at request time
    # like everything else: the generator imports the curation stack, and the
    # droplet has no gemmi.
    from nobble.design import report as design_report

    design = design_report.build()
    (OUT / "design.json").write_text(json.dumps(design, indent=2, default=str))
    summary["files"]["design.json"] = len(design.get("parents", []))

    # Bridge rate against pose recovery (FINDINGS.md F9). Computed here, with
    # the correlation, so the application renders a static result and does no
    # statistics at request time.
    try:
        from scipy import stats as _stats

        validation = json.loads((campaign / "validation.json").read_text())
        recovery = validation["layers"]["pose_recovery"]["summary"]["by_pair"]
        scored = {
            json.loads(line)["pair_id"]: json.loads(line)
            for line in (campaign / "scores.jsonl").read_text().splitlines() if line.strip()
        }
        points = []
        for pair_id, stats_row in sorted(recovery.items()):
            row = scored.get(pair_id, {})
            total = row.get("bridging_seeds_total") or 0
            if not total:
                continue
            points.append({
                "pair_id": pair_id,
                "gene": row.get("peptide_gene") or pair_id,
                "e3": row.get("e3_gene"),
                "bridge_rate": round((row.get("bridging_seeds_with_bridge") or 0) / total, 3),
                "bridging": f"{row.get('bridging_seeds_with_bridge') or 0}/{total}",
                "median_rmsd": stats_row["median_rmsd"],
                "best_rmsd": stats_row["best_rmsd"],
                "convergence": row.get("convergence_score"),
            })
        payload = {"points": points, "n": len(points)}
        if len(points) >= 3:
            xs = [item["bridge_rate"] for item in points]
            ys = [item["median_rmsd"] for item in points]
            r_value, p_value = _stats.pearsonr(xs, ys)
            rho, rho_p = _stats.spearmanr(xs, ys)
            payload |= {
                "pearson_r": round(float(r_value), 3), "pearson_p": round(float(p_value), 4),
                "spearman_rho": round(float(rho), 3), "spearman_p": round(float(rho_p), 4),
            }
        (OUT / "recovery_vs_bridge.json").write_text(json.dumps(payload, indent=2))
        summary["files"]["recovery_vs_bridge.json"] = len(points)
    except Exception as problem:                   # noqa: BLE001
        summary["recovery_vs_bridge_error"] = f"{type(problem).__name__}: {problem}"

    # If a corrected-construct campaign exists, publish the comparison that
    # answers F6. Computed here, on the build machine, because the droplet
    # computes nothing: the app renders a static verdict.
    corrected = sorted(
        (item for item in (ROOT / "campaigns").iterdir()
         if item.is_dir() and item.name.startswith("corrected_")),
        key=lambda item: item.name,
    )
    if corrected:
        from nobble.validate.compare import compare

        try:
            report = compare(campaign, corrected[-1])
            (OUT / "comparison.json").write_text(
                json.dumps(redact(report), indent=2, default=str)
            )
            summary["files"]["comparison.json"] = len(report.get("comparisons", []))
            summary["comparison_conclusion"] = report.get("conclusion")
        except Exception as problem:               # noqa: BLE001
            summary["comparison_error"] = f"{type(problem).__name__}: {problem}"

    # The queue itself is not published (it is large and carries the YAML
    # paths of the build machine), but its size must be, or the deployed app
    # has no denominator: it then reads 75 of 0 jobs and reports a running
    # campaign as complete, which is a status panel telling a lie.
    source_queue = campaign / "queue.jsonl"
    if source_queue.exists():
        summary["jobs_total"] = sum(
            1 for line in source_queue.read_text().splitlines() if line.strip()
        )
        pair_ids = set()
        for line in source_queue.read_text().splitlines():
            if line.strip():
                pair_ids.add(json.loads(line).get("pair_id"))
        summary["pairs_total"] = len(pair_ids)

    structures = list((OUT / "structures").glob("*.cif"))
    summary["structures"] = len(structures)
    summary["bytes"] = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    (OUT / "ATLAS.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))
    print(f"\nverified: no PROTAC-DB chemistry in the published bundle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
