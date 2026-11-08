"""Tier B's selection records which of its filters actually ran (F314).

`config/thresholds.toml` gates Tier B membership on a pocket druggability
floor, a plDDT floor and being above the median tumour enrichment, then takes
the top 15. Three filters and a cut.

One of the three never ran. `data/tier_b_selection.provenance.json` records
`tumour_enrichment_filter_applied: false`, with the reason in two forms: the
status is `not_computed: open_targets_enrichment_unpopulated`, and the funnel
gives the column one distinct value at a median of 0.0. So the frozen set of
154 pairs, 32.8 hours of GPU, is the product of two filters and a cut rather
than three and a cut.

That is recorded honestly at the source and reported nowhere else, because
Tier B has never run and appears in no page and no README. The risk is
forward: when its results are written up, "selected on druggability, fold
confidence and tumour enrichment" is the sentence that writes itself, and it
would be wrong.

So this guards the one place the fact lives. A funnel that omits the flag
reads as a filter that ran.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROVENANCE = ROOT / "data" / "tier_b_selection.provenance.json"


def _provenance() -> dict:
    if not PROVENANCE.exists():
        pytest.skip("no Tier B selection frozen on this checkout")
    return json.loads(PROVENANCE.read_text())


# The three thresholds that decide membership, as against the ones that size
# a construct. Named rather than taken from the config block, because the
# first version of this asked for every key under `tier_b` and failed on
# `construct_peptide_residues` and two others, which do not filter anything:
# they set how long a peptide window is. A test that cannot tell a filter
# from a construct parameter is not asking about filters.
MEMBERSHIP_FILTERS = ("pocket_druggability_min", "mean_plddt_min",
                      "tumour_enrichment_above_median")


def test_the_membership_filters_are_recorded_with_the_selection():
    """What it was filtered on has to travel with the frozen set, or the
    cutoffs behind 154 pairs are whatever config happens to say today."""
    recorded = _provenance().get("thresholds") or {}
    missing = [name for name in MEMBERSHIP_FILTERS if name not in recorded]
    assert not missing, (
        f"the frozen selection records no value for {missing}, so which "
        "cutoff it used cannot be checked"
    )


def test_the_recorded_cutoffs_still_match_config():
    """Drift is the live hazard: the set was frozen on 5 November and
    `config/thresholds.toml` is editable. A selection made at one cutoff and
    described by another is the F97 shape in a parquet file.

    Checked in the direction the provenance allows. Every value it records
    must match config; a new filter added to config and not recorded here
    would not be caught, and that is a limit of the check rather than a
    property of the selection.
    """
    from nobble import paths

    recorded = _provenance().get("thresholds") or {}
    configured = paths.thresholds().get("tier_b") or {}
    if not configured:
        pytest.skip("no tier_b block in thresholds.toml")
    drifted = {name: (value, configured.get(name))
               for name, value in recorded.items()
               if name in configured and configured[name] != value}
    assert not drifted, (
        f"the frozen selection was made at cutoffs config no longer holds: "
        f"{drifted}. Re-freeze or restore the values before Tier B runs"
    )


def test_a_filter_that_did_not_run_says_so_rather_than_being_absent():
    """The honesty property. `tumour_enrichment_filter_applied: false` is
    the only place in the project that says the Tier B set is the product of
    two filters rather than three, and a funnel without the key reads as a
    filter that ran."""
    funnel = _provenance().get("funnel") or {}
    assert "tumour_enrichment_filter_applied" in funnel, (
        "the funnel no longer says whether the tumour enrichment filter was "
        "applied, so a reader cannot tell"
    )
    applied = funnel["tumour_enrichment_filter_applied"]
    assert isinstance(applied, bool), applied
    if not applied:
        status = str(_provenance().get("tumour_enrichment_status") or "")
        assert status.startswith("not_computed"), (
            f"the filter did not run and the status does not say why: {status}"
        )
        assert "not_computed" in str(funnel.get("tumour_enriched_above_median")), (
            "the funnel's count for the unapplied filter reads as a count "
            "rather than as absent"
        )


def test_the_funnel_counts_narrow_monotonically():
    """Each stage can only shrink the set. A stage that grows it means the
    counts are not the funnel they are presented as."""
    funnel = _provenance().get("funnel") or {}
    stages = [funnel.get("ligandable_unproven"),
              funnel.get("pocket_score_ge_0.85"),
              funnel.get("best_window_plddt_ge_80.0")]
    counts = [value for value in stages if isinstance(value, int)]
    assert len(counts) >= 2, f"too few numeric stages to check: {stages}"
    assert counts == sorted(counts, reverse=True), counts


def test_the_frozen_set_is_what_the_funnel_ends_on():
    """`candidates_after_filters` is the number the take_top cut is applied
    to, so it has to match the last funnel stage rather than be a third
    figure."""
    provenance = _provenance()
    funnel = provenance.get("funnel") or {}
    after = provenance.get("candidates_after_filters")
    last = funnel.get("best_window_plddt_ge_80.0")
    if after is None or last is None:
        pytest.skip("the funnel does not carry both figures")
    assert after == last, (
        f"the funnel ends on {last} and the selection says "
        f"{after} candidates survived the filters"
    )
