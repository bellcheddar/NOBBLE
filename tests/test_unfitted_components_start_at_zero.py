"""A fit that selected two components, and three sliders still at their defaults.

`weights.json` has reported `fitted: false` on every campaign so far, so the
weights panel had never been rendered with a fit. Fitting on the Sievers
fixture rendered it for the first time: 127 labelled pairs, objective 0.8515,
and `components_used` naming two of the five, `bridge_percentile` and
`delta_iptm`, at 0.2 and 0.8.

The ledger's composite column then read 0.6578 for IKZF1 while the pipeline
had stored 0.6189, under the panel's own sentence saying the weights were
fitted on 127 labelled pairs and never by hand. The three components the fit
did not select had kept their hand-set defaults, 0.25, 0.15 and 0.00, and
went on contributing to a column presented as fitted.

A fit that leaves a component out has not declined to answer for it. It has
answered zero. That is F106's shape surviving for the components the fit did
not pick: there, the alias map made one fitted component render as its
default; here, every component the fit passed over did.

The rule now exists in two places because the server renders the slider and
the browser initialises it, the same necessity the alias map already carries,
so both are pinned below.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from nobble.app import create_app, data as app_data  # noqa: E402
from nobble.execute.campaign import latest  # noqa: E402
from nobble.score import weights as W  # noqa: E402

FIT = {"bridge_percentile": 0.2, "delta_iptm": 0.8}


def _benchmark() -> Path:
    """Selected by the project's own rule rather than by a pinned name, so
    this does not quietly render an absent campaign once the directory is
    rotated (F190)."""
    directory = latest("benchmark") or latest("campaign")
    if directory is None:
        pytest.skip("no complete campaign on this checkout")
    return directory


def _fitted_campaign(root: Path) -> Path:
    """A campaign whose weights.json reports a fit over a subset."""
    directory = root / "campaign"
    directory.mkdir(parents=True)
    source = _benchmark()
    for name in ("campaign.json", "queue.jsonl", "state.jsonl",
                 "results.jsonl"):
        shutil.copy(source / name, directory / name)
    rows = [json.loads(line) for line
            in (source / "scores.jsonl").read_text().splitlines()
            if line.strip()]
    assert rows, "the benchmark campaign has no scored rows to render"
    for row in rows:
        row["nobble_score"] = W.apply(row, FIT)
    (directory / "scores.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows))
    (directory / "weights.json").write_text(json.dumps({
        "status": "fitted",
        "weights": dict(FIT),
        "objective": 0.8515,
        "labelled_pairs": 127,
        "positives": 31,
        "negatives": 96,
        "components_used": sorted(FIT),
        "caveats": [],
        "per_component_auc": {},
        "seed_shapes": {},
        "fitted": True,
    }, indent=2))
    return directory


def _slider_values(body: str) -> dict[str, float]:
    found = {}
    for key in app_data.COMPONENTS:
        match = re.search(
            rf'id="w-{re.escape(key)}"[^>]*?value="([^"]+)"', body, re.S)
        assert match, f"no slider rendered for {key}"
        found[key] = float(match.group(1))
    return found


def _template_code() -> str:
    """campaign.html with its comments removed.

    Both the Jinja comment and the JavaScript one below it name the rule and
    the function that holds it, so a source check run over the raw file
    matches the explanation whether or not the code is there.
    """
    text = (ROOT / "nobble" / "app" / "templates" / "campaign.html").read_text()
    stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    stripped = re.sub(r"\{#.*?#\}", "", stripped, flags=re.S)
    assert "F205" in text and "F205" not in stripped, (
        "the comment strip did not take, so what follows may be matching a "
        "comment rather than the code"
    )
    return stripped


def test_the_fitted_weight_of_a_component_the_fit_left_out_is_zero():
    for key in ("lysine_reach", "cooperativity", "plip_contacts"):
        if key not in app_data.COMPONENTS:
            continue
        assert app_data.fitted_weight(FIT, key, 0.25) == 0, key


def test_a_fitted_component_still_gets_its_fitted_weight():
    assert app_data.fitted_weight(FIT, "delta_iptm", 0.35) == 0.8
    assert app_data.fitted_weight(FIT, "bridge_percentile", 0.35) == 0.2


def test_with_no_fit_the_hand_set_default_stands():
    """The zero is the fit's answer, not a blanket one. With nothing fitted
    the panel says so and the defaults are the right starting point."""
    for empty in ({}, None):
        assert app_data.fitted_weight(empty, "lysine_reach", 0.15) == 0.15


def test_the_rendered_sliders_are_the_fit_and_nothing_else(tmp_path):
    campaign = _fitted_campaign(tmp_path)
    body = create_app(str(campaign)).test_client().get("/campaign").get_data(
        as_text=True)
    assert "never by hand" in body, (
        "the panel does not claim a fit, so this renders the wrong state"
    )
    values = _slider_values(body)
    for key, value in values.items():
        expected = FIT.get(app_data.FITTED_ALIASES.get(key, key), 0)
        assert value == expected, (key, value, expected)
    assert sum(values.values()) == sum(FIT.values()), values


def test_the_sliders_reproduce_the_stored_score(tmp_path):
    """The defect as it was measured: the column and the pipeline differed.

    Both numbers are computed here rather than quoted, so this fails if
    either side's arithmetic moves, and the defaults case is asserted to
    differ so the comparison cannot pass by the two being equal anyway.
    """
    campaign = _fitted_campaign(tmp_path)
    row = json.loads((campaign / "scores.jsonl").read_text().splitlines()[0])
    body = create_app(str(campaign)).test_client().get("/campaign").get_data(
        as_text=True)

    from_page = W.apply(row, {
        app_data.FITTED_ALIASES.get(key, key): value
        for key, value in _slider_values(body).items()})
    assert from_page == row["nobble_score"], (from_page, row["nobble_score"])

    with_defaults = W.apply(row, {
        app_data.FITTED_ALIASES.get(key, key):
            FIT.get(app_data.FITTED_ALIASES.get(key, key),
                    meta["default_weight"])
        for key, meta in app_data.COMPONENTS.items()})
    assert with_defaults != row["nobble_score"], (
        "the defaults give the same composite as the fit on this row, so "
        "this test would have passed before the fix"
    )


def test_with_no_fit_the_rendered_sliders_are_the_defaults():
    """The other half of the branch, against a campaign that has no fit."""
    body = create_app(str(_benchmark())).test_client().get("/campaign").get_data(
        as_text=True)
    assert "Not fitted yet" in body
    values = _slider_values(body)
    for key, meta in app_data.COMPONENTS.items():
        assert values[key] == meta["default_weight"], key


def test_the_client_initialiser_carries_the_same_rule():
    """The browser recomputes the composite on every slider move, so a
    server that renders zero and a script that initialises to the default
    would disagree the moment the page loaded."""
    initialiser = _template_code().split(
        "const FITTED_RAW")[1].split("let weights")[0]
    assert "HAS_FIT" in initialiser
    assert "HAS_FIT ? 0 :" in initialiser, (
        "the JavaScript falls back to the default with a fit present, which "
        "is the defect on the client side"
    )


def test_the_rule_is_one_function_on_the_server_side():
    """The template renders the slider through data.fitted_weight rather
    than resolving the fallback itself, so the rule it shares with the
    JavaScript has one definition per side and not one per call site."""
    assert "fitted_weight(fitted_w, key" in _template_code(), (
        "the template resolves the weight itself rather than through the "
        "shared function"
    )
    page = create_app(str(_benchmark())).test_client().get("/campaign")
    assert page.status_code == 200
    assert callable(app_data.fitted_weight)
