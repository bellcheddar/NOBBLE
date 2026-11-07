"""The app shows every statistic put to the Sievers labels, not just one.

F280 put four statistics to the matched-control split and every interval
contained 0.5, which is a stronger result than the primary statistic's null
alone: the bridge geometry over the same poses and pairs does not separate
the classes either. The about page showed only Delta-ipTM's 0.4583, and the
campaign page offers a sortable Bridge rate column with nothing to say that
the rate has no validated discriminating power.

So the companions travel with the primary curve into `validation.json` and
onto the page, with the count of statistics stated, because "the fourth
measure we tried" and "the measure the spec names" are different claims and
only the second is in the specification.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.validate import layers


def _campaign() -> Path | None:
    from nobble.execute.campaign import latest

    found = latest("campaign")
    return Path(found) if found else None


def test_the_companion_list_is_the_statistics_actually_tried():
    """Named in code, so the count is a fact rather than a reconstruction."""
    assert layers.ROC_COMPANIONS, "no companion statistics are declared"
    assert "delta_iptm" not in layers.ROC_COMPANIONS, (
        "the primary statistic is listed as its own companion, which would "
        "double it in the table and in the count")


def test_each_companion_curve_carries_its_own_coverage():
    """Because they do not share a denominator.

    `bridge_percentile` is absent for pairs in which nothing bridged, so it
    runs on a subset selected on the outcome it measures. A table of AUCs
    without that line invites reading four curves as four views of one
    sample.
    """
    campaign = _campaign()
    if campaign is None:
        pytest.skip("no campaign assembled")
    rows = layers.roc_companions(campaign)
    if not any(row["computed"] for row in rows):
        pytest.skip("no companion curve is computable on this campaign")
    for row in rows:
        if not row["computed"]:
            continue
        assert row["coverage"], row
        assert row["positives"] is not None, row
        assert row["matched_negatives"] is not None, row


def test_the_primary_curve_states_how_many_were_tried():
    campaign = _campaign()
    if campaign is None:
        pytest.skip("no campaign assembled")
    layer = layers.matched_control_roc(campaign)
    if not layer.computed:
        pytest.skip(layer.status)
    # `run` attaches them; the layer on its own does not, which keeps a
    # single-statistic call cheap.
    report = layers.run(campaign)
    summary = report["layers"]["matched_control_roc"]["summary"]
    assert summary["statistics_tried"] == 1 + len(layers.ROC_COMPANIONS)
    assert len(summary["companions"]) == len(layers.ROC_COMPANIONS)


def test_the_page_shows_all_of_them():
    campaign = _campaign()
    if campaign is None:
        pytest.skip("no campaign assembled")
    from nobble.app import create_app

    app = create_app(str(campaign))
    app.config["TESTING"] = True
    text = app.test_client().get("/about").get_data(as_text=True)
    if "Matched-control ROC" not in text:
        pytest.skip("the about page has no ROC section in this bundle")
    for statistic in layers.ROC_COMPANIONS:
        assert statistic in text, (
            f"{statistic} was tried against these labels and the page does "
            "not show it")
    assert "statistics put to this split" in text, (
        "the page does not say how many statistics were tried")


def test_the_page_says_nothing_extra_when_there_are_no_companions():
    """An older validation.json has no companions, and must render clean.

    The published bundle predates this, so the guard matters now rather than
    hypothetically.
    """
    template = (ROOT / "nobble" / "app" / "templates" / "about.html").read_text()
    guard = template[template.index("roc.summary.interpretation"):]
    assert "roc.summary.get('companions')" in guard[:1200], guard[:400]
