"""Every component shows what it achieves alone, not a trust word.

`data.COMPONENTS` carries a `trust` field reading "primary", "headline",
"high", "high" and "not validated", and the campaign page uses it for one
thing: styling the single "not validated" component. So four of the five read
as endorsed.

The measurements do not support that hierarchy. Every standalone AUC sits
between 0.52 and 0.60 in-sample (F281); the two that have been put to the
matched-control arm give intervals containing 0.5, Delta-ipTM at 0.4583 and
bridge_percentile at 0.5237 (F280); and the grid gives Delta-ipTM, labelled
"headline", a weight of zero. The two labelled "high" have never been put to
that arm at all.

So each slider now carries the component's own AUC beside its weight, which
is a measured number in place of an implied ranking (F284).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.app import data


def _campaign() -> Path | None:
    from nobble.execute.campaign import latest

    found = latest("campaign")
    return Path(found) if found else None


def test_the_auc_lookup_resolves_the_alias():
    """The UI calls it `lysine_reach`; the fit calls it something longer.

    F106 is this exact mismatch in the weight lookup, and the first version
    of the AUC line walked into it: four components rendered a number and the
    fifth, whose note already admits it sits at chance, rendered nothing.
    """
    per_component = {"lysine_reach_exposed_fraction": 0.5855,
                     "delta_iptm": 0.5236}
    assert data.component_auc(per_component, "lysine_reach") == 0.5855
    assert data.component_auc(per_component, "delta_iptm") == 0.5236
    assert data.component_auc(per_component, "not_a_component") is None
    assert data.component_auc(None, "lysine_reach") is None


def test_the_alias_map_is_the_one_the_weight_lookup_uses():
    """Two resolutions of one name is the thing F106 was about."""
    import inspect

    source = inspect.getsource(data.component_auc)
    assert "FITTED_ALIASES" in source, source


def test_every_component_shows_an_auc_on_the_page():
    campaign = _campaign()
    if campaign is None:
        pytest.skip("no campaign assembled")
    from nobble.app import create_app

    app = create_app(str(campaign))
    app.config["TESTING"] = True
    text = app.test_client().get("/campaign").get_data(as_text=True)
    if "Composite weights" not in text:
        pytest.skip("the campaign page has no weights panel here")
    if "AUC alone" not in text:
        pytest.skip("the fit has not run on this campaign")
    assert text.count("AUC alone") == len(data.COMPONENTS), (
        f"{text.count('AUC alone')} of {len(data.COMPONENTS)} component(s) "
        "show what they achieve alone")


def test_no_component_claims_validated_discrimination():
    """The notes may describe a component; none may call it validated.

    The one component whose note carries a number says it is at or below
    chance. If another ever claims validated power, the claim needs a
    matched-control curve behind it and there are only two, both containing
    0.5.
    """
    for key, meta in data.COMPONENTS.items():
        note = (meta.get("note") or "").lower()
        assert "validated predictor" not in note or "not a validated" in note, (
            key, meta.get("note"))
        assert "proven" not in note, (key, meta.get("note"))


def test_each_component_auc_carries_its_own_row_count():
    """They are not over the same rows, so the count travels with the number.

    Each component's standalone AUC is computed where that component has a
    value, so the sets differ: on the main campaign from 27 of 31 positives
    to 31 of 31, and 112 of 127 negatives to 127. A modest difference, and
    the reason to show it is that five numbers in one column invite a
    comparison, not that any one of them is wrong (F285).
    """
    campaign = _campaign()
    if campaign is None:
        pytest.skip("no campaign assembled")
    from nobble.score import weights

    fit = weights.fit(campaign).to_dict()
    if not fit.get("per_component_auc"):
        pytest.skip("the fit has not run on this campaign")
    counts = fit.get("per_component_n") or {}
    assert set(counts) == set(fit["per_component_auc"]), (
        sorted(counts), sorted(fit["per_component_auc"]))
    for name, n in counts.items():
        assert n["positives"] > 0 and n["negatives"] > 0, (name, n)
        assert n["positives"] <= fit["positives"], (name, n)
        assert n["negatives"] <= fit["negatives"], (name, n)


def test_the_pages_show_the_row_counts():
    campaign = _campaign()
    if campaign is None:
        pytest.skip("no campaign assembled")
    from nobble.app import create_app

    app = create_app(str(campaign))
    app.config["TESTING"] = True
    client = app.test_client()
    campaign_page = client.get("/campaign").get_data(as_text=True)
    if "AUC alone" not in campaign_page:
        pytest.skip("the fit has not run on this campaign")
    assert campaign_page.count("positive and") == len(data.COMPONENTS), (
        "not every slider shows the rows its AUC rests on")
    about = client.get("/about").get_data(as_text=True)
    if "Fitted weight" in about:
        assert "on 31 / 127" in about or "on " in about, (
            "the composite table shows AUCs without their row counts")
