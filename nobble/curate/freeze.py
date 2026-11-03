"""Freeze the Tier B selection so a campaign is reproducible (spec 3.3).

The selection depends on BINMAN's triage scores. Those can be re-run, so the
chosen set and its scores are written to disk once and the campaign reads the
frozen file rather than re-deriving the ranking.
"""
from __future__ import annotations

import json

import pandas

from nobble import paths
from nobble.curate import tiers

PROVENANCE = paths.DATA / "tier_b_selection.provenance.json"


def write_tier_b(force: bool = False) -> dict:
    """Write data/tier_b_selection.parquet. Idempotent unless forced."""
    if paths.TIER_B_SELECTION.exists() and not force:
        frame = pandas.read_parquet(paths.TIER_B_SELECTION)
        return {"written": False, "rows": len(frame), "path": str(paths.TIER_B_SELECTION)}

    selection = tiers.tier_b()
    frame = pandas.DataFrame(selection["selected"])
    # reasons is a list per row: store as text so the parquet stays flat.
    if "reasons" in frame.columns:
        frame["reasons"] = frame["reasons"].map(lambda value: " | ".join(value))
    if "best_window" in frame.columns:
        frame["best_window"] = frame["best_window"].map(
            lambda value: json.dumps(value) if value is not None else None
        )
    frame.to_parquet(paths.TIER_B_SELECTION, index=False)

    PROVENANCE.write_text(json.dumps(
        {
            "funnel": selection["funnel"],
            "tumour_enrichment_status": selection["tumour_enrichment_status"],
            "candidates_after_filters": selection["candidates_after_filters"],
            "spec_expected_members": selection["spec_expected_members"],
            "spec_expected_present": selection["spec_expected_present"],
            "spec_expected_absent": selection["spec_expected_absent"],
            "thresholds": paths.thresholds()["tier_b"],
        },
        indent=2,
    ))
    return {"written": True, "rows": len(frame), "path": str(paths.TIER_B_SELECTION)}
