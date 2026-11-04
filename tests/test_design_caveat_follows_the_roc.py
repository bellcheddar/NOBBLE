"""The design arm's caveat has to follow the ROC, not assert it.

The design page ranks variants, and a ranked list reads as a recommendation
whatever the caption says, so the caveat beside it carries weight. It read:
"the matched-control ROC reports not_computed until the Sievers arm runs",
as a literal string, on every build.

Two things were wrong with that. `score_validation`, the field meant to carry
the real status, read `data/atlas/validation.json`: a path that has never
existed, since `data/atlas` is empty and the layer statuses live in the
campaign, where `build_atlas` reads them for everything else. So the field
was published as `{}` on every build and the lookup silently fell through its
`if exists()`.

And the literal is true today and false the moment the Sievers arm finishes,
which is the moment the headline result arrives: the page would go on saying
the score is not validated while the curve that validates it sat one file
away. F96 was a caveat that never reached the page. This is one that reaches
the page and cannot change (F105).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.design import report  # noqa: E402

ORDERING = "Read the ordering of positions"


def _campaign(tmp_path: Path, layer: dict | None) -> Path:
    campaign = tmp_path / "campaign_caveat"
    campaign.mkdir(exist_ok=True)
    if layer is not None:
        (campaign / "validation.json").write_text(json.dumps(
            {"layers": {"matched_control_roc": layer}}))
    return campaign


def test_the_dead_path_is_gone():
    source = (ROOT / "nobble" / "design" / "report.py").read_text()
    assert 'paths.DATA / "atlas" / "validation.json"' not in source, (
        "the validation lookup points at data/atlas again, which is empty"
    )


def test_a_computed_curve_above_chance_changes_the_caveat(tmp_path):
    """The case the literal could not express. This is what the page will
    need to say when the Sievers arm lands."""
    campaign = _campaign(tmp_path, {
        "status": "computed",
        "summary": {"auc": 0.8125, "ci95": [0.68, 0.92],
                    "interpretation": "above chance"},
    })
    built = report.build(campaign=campaign)
    caveat = built["caveat"]

    assert "0.8125" in caveat, caveat
    assert "above chance" in caveat
    assert "not validated" not in caveat, caveat
    assert "not_computed" not in caveat
    assert ORDERING in caveat, "the scan's durable claim was dropped"
    assert built["score_validation"]["auc"] == 0.8125
    assert built["score_validation"]["ci95"] == [0.68, 0.92]


def test_a_computed_curve_at_chance_still_says_not_validated(tmp_path):
    """A curve that computed is not a curve that passed. Reporting an AUC
    without its verdict is how a ranked list becomes a recommendation."""
    campaign = _campaign(tmp_path, {
        "status": "computed",
        "summary": {
            "auc": 0.5102, "ci95": [0.38, 0.64],
            "interpretation": ("not distinguishable from chance at 95 per "
                               "cent confidence"),
        },
    })
    caveat = report.build(campaign=campaign)["caveat"]
    assert "not validated" in caveat, caveat
    assert "0.5102" in caveat
    assert "not distinguishable from chance" in caveat


def test_a_not_computed_curve_carries_its_own_reason_in_the_field(tmp_path):
    """The reason belongs in `score_validation`, not in the panel. The
    layer's status can run to three lines and the UI copy budget is under 40
    words a panel, so the sentence says that the curve has not computed and
    the field says why."""
    campaign = _campaign(tmp_path, {
        "status": "not_computed: 3 positive(s) and 0 matched negative(s) scored",
        "summary": {},
    })
    built = report.build(campaign=campaign)
    assert "not validated" in built["caveat"]
    assert "has not computed" in built["caveat"], built["caveat"]
    assert "3 positive(s) and 0 matched negative(s)" in (
        built["score_validation"]["matched_control_roc"]
    ), built["score_validation"]


def test_the_rendered_caveat_stays_inside_the_copy_budget(tmp_path):
    """Under 40 words a panel (CLAUDE.md). The first version of this carried
    the layer's full status into the sentence and ran to 55."""
    for layer in (
        {"status": "computed",
         "summary": {"auc": 0.8125, "ci95": [0.68, 0.92],
                     "interpretation": "above chance"}},
        {"status": "computed",
         "summary": {"auc": 0.51, "ci95": [0.38, 0.64],
                     "interpretation": "not distinguishable from chance at 95 "
                                       "per cent confidence"}},
        {"status": "not_computed: " + "x" * 300, "summary": {}},
    ):
        caveat = report.build(campaign=_campaign(tmp_path, layer))["caveat"]
        assert len(caveat.split()) < 40, (len(caveat.split()), caveat)


def test_the_template_renders_the_derived_sentence(tmp_path):
    """The layer that actually reaches the reader. The panel used to check
    `design.caveat` and then render a literal of its own, so the derived
    sentence was computed, published and never shown."""
    template = (ROOT / "nobble" / "app" / "templates" / "design.html").read_text()
    assert "{{ design.get('caveat') }}" in template, (
        "the design panel no longer renders the derived caveat"
    )
    assert "The composite is not validated yet, so read" not in template, (
        "the hard-coded caveat literal is back in the template"
    )


def test_an_unreadable_status_falls_back_to_not_validated(tmp_path):
    """The safe direction for a page that ranks variants. Silence would let
    the arm look validated by omission."""
    campaign = tmp_path / "campaign_empty"
    campaign.mkdir()
    built = report.build(campaign=campaign)
    assert "not validated" in built["caveat"], built["caveat"]
    assert ORDERING in built["caveat"]


def test_a_malformed_validation_file_does_not_crash_the_build(tmp_path):
    campaign = tmp_path / "campaign_broken"
    campaign.mkdir()
    (campaign / "validation.json").write_text("{not json")
    built = report.build(campaign=campaign)
    assert "not validated" in built["caveat"]


def test_the_campaign_argument_is_actually_read(tmp_path):
    """It was not, at first. `build` already had a local named `campaign`
    holding the campaigns directory, assigned before the validation lookup,
    so the argument was shadowed and a passed campaign was silently replaced
    by `campaigns/`. Caught by reading `searched` in the output rather than
    by any test, which is why there is one now."""
    campaign = _campaign(tmp_path, {
        "status": "computed",
        "summary": {"auc": 0.77, "ci95": [0.6, 0.9],
                    "interpretation": "above chance"},
    })
    built = report.build(campaign=campaign)
    validation = built["score_validation"]

    # Behavioural, not positional. Only the file just written says 0.77: a
    # shadowed argument falls through to the campaigns directory, which holds
    # no validation.json, and then to the published atlas, whose curve has
    # not computed and whose AUC is therefore None.
    assert validation["auc"] == 0.77, validation
    assert validation["ci95"] == [0.6, 0.9]
    assert "0.77" in built["caveat"], built["caveat"]

    # And it is the first place looked, ahead of the fallbacks.
    assert validation["searched"][0] == validation["read_from"], validation
    # A tmp campaign sits outside the project root, so the recorded form is
    # the basename rather than an absolute path. That is the leak guard in
    # tests/test_no_local_paths_published.py doing its job, not a defect:
    # a real campaign is inside the root and records a relative path.
    assert validation["read_from"] == "validation.json", validation


def test_the_atlas_build_passes_its_own_campaign():
    """So the caveat describes the campaign the rest of the page is built
    from, not whichever file a global lookup found first."""
    source = (ROOT / "deploy" / "build_atlas.py").read_text()
    assert "design_report.build(campaign=campaign)" in source


def test_the_live_build_reads_a_file_that_exists():
    """The regression that matters: the old lookup resolved to nothing on
    every build and nothing noticed, because an empty dict is what the
    failure and the honest answer both look like."""
    built = report.build()
    validation = built["score_validation"]
    assert validation["matched_control_roc"], validation
    assert validation["read_from"], validation["searched"]
    assert Path(validation["read_from"]).exists()
