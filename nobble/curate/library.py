"""Persist the reduced peptide library (spec 3.4, CLAUDE.md manifest rule).

The library was being assembled in memory and thrown away. Phase 1 reported
"25,567 candidates reduced to 220" and nothing on disk could reproduce it:
`reduce_library` and `campaign_budget` had no callers anywhere in the tree,
and `data/manifests/` held only the benchmark panel. That breaks the project
rule that every stage writes a manifest and is resumable and idempotent, and
it matters more than the usual bookkeeping here because assembly takes over
twenty minutes and reaches out to UniProt and InterPro on the way.

So this module is the committed entry point. It writes
`data/manifests/library.jsonl` (one peptide per line, in queue priority
order) and `library.summary.json` (the reduction's own account of itself,
including whether it came in over budget and why it was not trimmed).

Idempotent: a second run with the manifest already present reloads it rather
than rebuilding, unless `force=True`. The selection is deterministic anyway
(`SEED` is fixed and k-means is seeded), but determinism is not the same as
free.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from nobble import paths
from nobble.curate import peptides as P
from nobble.curate.diversity import campaign_budget, projected_hours, reduce_library

MANIFEST = paths.MANIFESTS / "library.jsonl"
SUMMARY = paths.MANIFESTS / "library.summary.json"


def _peptide_row(peptide) -> dict:
    row = asdict(peptide) if hasattr(peptide, "__dataclass_fields__") else dict(peptide)
    return row


def load() -> dict | None:
    """Return the persisted library, or None if it has not been built."""
    if not MANIFEST.exists() or not SUMMARY.exists():
        return None
    # Strict: the manifest is written in one pass by `build` and nothing
    # appends to it, so an unparseable line is damage rather than a torn
    # tail (F111).
    peptides = paths.read_jsonl(MANIFEST)
    return {"peptides": peptides, "summary": json.loads(SUMMARY.read_text())}


def build(force: bool = False, budget: int | None = None) -> dict:
    """Assemble, reduce and persist. Reloads an existing manifest unless forced."""
    if not force:
        existing = load()
        if existing is not None:
            existing["summary"]["status"] = "loaded from manifest, not rebuilt"
            return existing

    library = P.build()
    candidates = library["peptides"]
    budget = campaign_budget() if budget is None else budget

    reduction = reduce_library(candidates, budget=budget)
    by_id = {peptide.peptide_id: peptide for peptide in candidates}
    selected = [by_id[pid] for pid in reduction.selected_ids if pid in by_id]

    with MANIFEST.open("w") as handle:
        for peptide in selected:
            handle.write(json.dumps(_peptide_row(peptide), default=str) + "\n")

    sources: dict[str, int] = {}
    for peptide in selected:
        sources[peptide.source] = sources.get(peptide.source, 0) + 1

    summary = reduction.to_dict()
    summary["sources"] = dict(sorted(sources.items()))
    # Every selected peptide is one pair, so the compute projection is the
    # selection size. Gate G1 is judged here rather than left to a reader.
    summary["compute"] = projected_hours(len(selected))
    SUMMARY.write_text(json.dumps(summary, indent=2, default=str))

    return {"peptides": [_peptide_row(p) for p in selected], "summary": summary}


def main() -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Assemble, reduce and persist the peptide library."
    )
    parser.add_argument("--force", action="store_true",
                        help="rebuild even if the manifest already exists")
    parser.add_argument("--budget", type=int, default=None,
                        help="override the measured campaign budget")
    args = parser.parse_args()

    result = build(force=args.force, budget=args.budget)
    summary = result["summary"]
    print(json.dumps({k: v for k, v in summary.items() if k != "selected_ids"},
                     indent=2, default=str))

    # An over-budget selection is a reported fact, not a failure: the mandatory
    # members are deliberately not trimmed. Gate G1 is the thing that stops a
    # build, and it is judged on max_compute_hours.
    if summary.get("compute", {}).get("gate_g1_open"):
        print("GATE G1 OPEN: the minimum viable set exceeds max_compute_hours",
              file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
