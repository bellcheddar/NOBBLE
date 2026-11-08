"""The composite's cross-validated estimate (F312).

`weights.fit` reports its objective as in-sample and caveats it correctly.
It also says "The matched-control ROC is the held-out measurement", which is
true of `delta_iptm` and false of the composite: `_label` is deliberately not
scoped to one arm because spec 4.8 fits on the panel and the Sievers matched
set, so the pairs spec 5.3's ROC evaluates are inside the fit's training
data. A raw statistic is held out from a fit it took no part in; a fitted
composite is not.

These check the arithmetic and the two properties that make the figure worth
quoting: the folds are deterministic, and a fold never scores a pair it was
fitted on.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import composite_crossval as cv                            # noqa: E402
from nobble.score import weights as W                      # noqa: E402


def _labelled(positives: int, negatives: int):
    rows = []
    for index in range(positives):
        rows.append({"pair_id": f"pos{index:03d}", "peptide_label": "degraded"})
    for index in range(negatives):
        rows.append({"pair_id": f"neg{index:03d}",
                     "peptide_label": "not_degraded"})
    return [(row, W._label(row)) for row in rows]


def test_the_folds_are_stratified():
    """31 positives over 5 folds must not leave a fold with none, or its
    held-out AUC is undefined and the pooled figure quietly rests on four."""
    labelled = _labelled(31, 127)
    assigned = cv.folds(labelled, 5)
    assert len(assigned) == 5
    for fold in assigned:
        sides = [labelled[index][1] for index in fold]
        assert "positive" in sides, "a fold holds no positive"
        assert "negative" in sides, "a fold holds no negative"


def test_every_pair_is_held_out_exactly_once():
    """Otherwise the pooled AUC double counts or drops pairs."""
    labelled = _labelled(31, 127)
    assigned = cv.folds(labelled, 5)
    flat = [index for fold in assigned for index in fold]
    assert sorted(flat) == list(range(len(labelled)))


def test_the_folds_do_not_move_between_runs():
    """A cross-validated number that changes run to run is the first thing
    anyone distrusts, so the split is dealt from sorted pair ids rather than
    from a seed."""
    labelled = _labelled(31, 127)
    assert cv.folds(labelled, 5) == cv.folds(labelled, 5)
    shuffled = list(reversed(labelled))
    # Same pairs in a different order must give the same partition of pairs.
    def as_ids(assignment, source):
        return sorted(sorted(str(source[i][0]["pair_id"]) for i in fold)
                      for fold in assignment)
    assert as_ids(cv.folds(labelled, 5), labelled) == \
        as_ids(cv.folds(shuffled, 5), shuffled)


def test_a_fold_never_scores_a_pair_it_was_fitted_on():
    """The property the whole figure rests on, checked on the real campaign
    rather than argued from the code."""
    import pytest

    from nobble import paths
    from nobble.execute.campaign import latest

    campaign = latest("campaign") or latest("benchmark")
    if campaign is None or not (campaign / "scores.jsonl").exists():
        pytest.skip("no scored campaign on this checkout")
    rows = paths.read_jsonl(campaign / "scores.jsonl", tolerate_torn=True)
    labelled = [(row, W._label(row)) for row in rows if W._label(row)]
    if len(labelled) < 10:
        pytest.skip("too few labelled pairs to fold")

    for fold in cv.folds(labelled, 5):
        held = {str(labelled[index][0].get("pair_id")) for index in fold}
        train = {str(row.get("pair_id")) for index, (row, _) in
                 enumerate(labelled) if index not in set(fold)}
        assert not (held & train), sorted(held & train)


def test_the_report_states_what_the_pooled_figure_estimates():
    """It estimates the procedure, not the published weights, because each
    held-out score comes from a different fold's fit. Quoting it as the
    performance of the shipped weighting would be the error this tool
    exists to prevent."""
    # Whitespace normalised before matching. The first version of this
    # looked for "not a confidence interval" in the raw text and failed,
    # because the phrase is split across a line break in the docstring. A
    # prose assertion that respects the author's line wrapping is asserting
    # the wrapping, which is the fourth text-matching slip of the day and
    # the one with the cheapest fix.
    import re

    source = re.sub(r"\s+", " ",
                    (ROOT / "tools" / "composite_crossval.py").read_text())
    assert "estimates the procedure" in source
    assert "not a confidence interval" in source


def test_it_measures_the_optimism_rather_than_asserting_it():
    import pytest

    from nobble import paths
    from nobble.execute.campaign import latest

    campaign = latest("campaign") or latest("benchmark")
    if campaign is None or not (campaign / "scores.jsonl").exists():
        pytest.skip("no scored campaign on this checkout")
    rows = paths.read_jsonl(campaign / "scores.jsonl", tolerate_torn=True)
    report = cv.crossval(rows, 5)
    if report["status"] != "measured":
        pytest.skip(report["status"])
    assert report["out_of_sample_auc"] is not None
    assert report["in_sample_auc"] is not None
    assert report["optimism"] == round(
        report["in_sample_auc"] - report["out_of_sample_auc"], 4)
    assert report["held_out_positives"] == report["labelled_pairs"] - \
        report["held_out_negatives"]


def test_fit_rows_is_what_the_campaign_fit_uses():
    """One spelling of the grid search, or the cross-validated figure
    describes a fit the campaign never performs."""
    import ast

    source = (ROOT / "nobble" / "score" / "weights.py").read_text()
    tree = ast.parse(source)
    fit = next(node for node in ast.walk(tree)
               if isinstance(node, ast.FunctionDef) and node.name == "fit")
    called = {node.func.id for node in ast.walk(fit)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "fit_rows" in called
    tool = (ROOT / "tools" / "composite_crossval.py").read_text()
    assert "W.fit_rows" in tool


# --------------------------------------------------------------------------- #
# On the page, beside the in-sample figure
# --------------------------------------------------------------------------- #

def _about(tmp_path, weights_json):
    import json

    from nobble.app import create_app

    (tmp_path / "weights.json").write_text(json.dumps(weights_json))
    app = create_app(str(tmp_path))
    app.config["TESTING"] = True
    body = app.test_client().get("/about")
    assert body.status_code == 200, body.status_code
    return body.get_data(as_text=True)


FITTED = {
    "fitted": True, "status": "fitted", "objective": 0.6988,
    "labelled_pairs": 158, "positives": 31, "negatives": 127,
    "weights": {"bridge_percentile": 0.4444, "delta_iptm": 0.0},
    "per_component_auc": {"bridge_percentile": 0.558, "delta_iptm": 0.5196},
    "components_used": ["bridge_percentile", "delta_iptm"],
    "caveats": [],
}


def test_the_page_prints_both_figures_when_the_fit_carries_them(tmp_path):
    """The in-sample number alone is the one most likely to be quoted as
    performance, which is why it is not alone any more."""
    page = _about(tmp_path, dict(FITTED, cross_validated={
        "status": "computed", "auc": 0.5836, "folds": 5,
        "held_out_positives": 31, "held_out_negatives": 127}))
    assert "0.6988 in sample" in page
    assert "0.5836" in page
    assert "5 held-out folds" in page


def test_an_older_fit_prints_the_in_sample_figure_alone(tmp_path):
    """A bundle scored before the estimate existed has no key, and the panel
    must not render a dangling "and" or a zero."""
    page = _about(tmp_path, FITTED)
    assert "0.6988 in sample" in page
    assert "held-out folds" not in page
    assert "and  across" not in page


def test_a_refused_estimate_does_not_print_as_a_number(tmp_path):
    """`not_computed` carries no AUC, and reading a missing estimate as
    reassuring is the shape the project keeps finding."""
    page = _about(tmp_path, dict(FITTED, cross_validated={
        "status": "not_computed: 1 positive(s), so no fold can hold one out "
                  "and still fit"}))
    assert "0.6988 in sample" in page
    assert "held-out folds" not in page


def test_the_standalone_column_no_longer_reads_as_a_fair_comparison(tmp_path):
    """A component's AUC carries no optimism because nothing was fitted to
    produce it, and the panel says so: without that, an in-sample composite
    sitting above in-sample components invites exactly the comparison F312
    shows does not survive."""
    page = _about(tmp_path, FITTED)
    assert "carries no optimism" in page


def test_the_fit_attaches_the_caveat_in_words():
    """A number in a dict is not a caveat. The fit's own caveat list is what
    `tools/status.sh` and the panel's refusal text read."""
    import pytest

    from nobble.execute.campaign import latest
    from nobble.score import weights

    campaign = latest("campaign") or latest("benchmark")
    if campaign is None or not (campaign / "scores.jsonl").exists():
        pytest.skip("no scored campaign on this checkout")
    result = weights.fit(campaign)
    if result.status != "fitted" or not result.cross_validated.get("auc"):
        pytest.skip(f"no estimate: {result.cross_validated.get('status')}")
    assert any("out of sample" in caveat for caveat in result.caveats)
    assert any("optimism" in caveat for caveat in result.caveats)


def test_a_cross_validation_failure_does_not_take_the_fit_with_it(monkeypatch):
    """The fit is the product; the estimate is commentary on it."""
    import pytest

    from nobble.execute.campaign import latest
    from nobble.score import weights

    campaign = latest("campaign") or latest("benchmark")
    if campaign is None or not (campaign / "scores.jsonl").exists():
        pytest.skip("no scored campaign on this checkout")

    def explode(rows, k=5):
        raise RuntimeError("deliberate")

    monkeypatch.setattr(weights, "cross_validate", explode)
    result = weights.fit(campaign)
    assert result.status == "fitted"
    assert result.objective is not None
    assert "RuntimeError" in result.cross_validated["status"]
