"""Two name spaces for the same five components, joined by key.

The fitter names a component after the column it reads and the UI names it
after the signal. Four of the five agree exactly:

    bridge_percentile, delta_iptm, convergence_score, plip_fingerprint_match

and the fifth does not. `weights.CANDIDATES` has
`lysine_reach_exposed_fraction`, because the value is a fraction derived from
the row's `lysine_reach` object, and `data.COMPONENTS` is keyed
`lysine_reach`, after the signal the slider is labelled for.

A join by key therefore loses exactly one component, and
`fitted_w.get(key, meta.default_weight)` turns that miss into a plausible
number rather than an error: the slider would show 0.0 as though the fit had
chosen it. `campaign.html`'s JavaScript already resolved the alias, with a
comment saying so. The Jinja that renders the same slider's initial value did
not, so the two layers disagreed about how to resolve a name and only one was
right.

The map now lives in `data.py` and both read it. These tests hold the
invariant that makes the class impossible rather than the instance (F106).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.app import data as app_data  # noqa: E402
from nobble.score import weights  # noqa: E402


def test_every_ui_component_resolves_to_a_fitter_candidate():
    """The direction that matters: a UI key that resolves to nothing means a
    fitted weight the page cannot show."""
    candidates = set(weights.CANDIDATES)
    unresolved = {
        key: app_data.FITTED_ALIASES.get(key, key)
        for key in app_data.COMPONENTS
        if app_data.FITTED_ALIASES.get(key, key) not in candidates
    }
    assert not unresolved, unresolved


def test_every_fitter_candidate_is_reachable_from_some_ui_component():
    """The other direction: a candidate no UI key maps to is a weight that is
    fitted, published and never displayed."""
    reachable = {app_data.FITTED_ALIASES.get(key, key)
                 for key in app_data.COMPONENTS}
    assert set(weights.CANDIDATES) <= reachable, (
        set(weights.CANDIDATES) - reachable
    )


def test_the_mapping_is_one_to_one():
    """Two UI keys resolving to one candidate would show the same fitted
    weight on two sliders."""
    resolved = [app_data.FITTED_ALIASES.get(key, key)
                for key in app_data.COMPONENTS]
    assert len(resolved) == len(set(resolved)), resolved


def test_an_alias_is_only_there_for_a_name_that_differs():
    """An alias mapping a key to itself is noise that hides a real one."""
    for key, target in app_data.FITTED_ALIASES.items():
        assert key != target, key
        assert key in app_data.COMPONENTS, key
        assert target in set(weights.CANDIDATES), target


def test_fitted_weight_resolves_the_alias():
    fitted = {"lysine_reach_exposed_fraction": 0.25, "delta_iptm": 0.5}
    assert app_data.fitted_weight(fitted, "lysine_reach", 0.0) == 0.25
    assert app_data.fitted_weight(fitted, "delta_iptm", 0.0) == 0.5


def test_fitted_weight_falls_back_only_when_there_is_nothing_to_show():
    assert app_data.fitted_weight({}, "lysine_reach", 0.15) == 0.15
    assert app_data.fitted_weight(None, "lysine_reach", 0.15) == 0.15
    assert app_data.fitted_weight({"other": 1.0}, "lysine_reach", 0.15) == 0.15
    # A fitted zero is a decision, not an absence, and must not be replaced
    # by the default.
    assert app_data.fitted_weight(
        {"lysine_reach_exposed_fraction": 0.0}, "lysine_reach", 0.15) == 0.0


def test_the_template_resolves_through_the_shared_map():
    template = (ROOT / "nobble" / "app" / "templates" / "campaign.html").read_text()
    assert "fitted_weight(fitted_w, key, meta.default_weight)" in template, (
        "the slider's initial value is joined by bare key again"
    )
    assert "{{ fitted_aliases|tojson }}" in template, (
        "the JavaScript carries its own copy of the alias map again"
    )
    assert "lysine_reach: 'lysine_reach_exposed_fraction'" not in template


def test_the_route_supplies_both():
    routes = (ROOT / "nobble" / "app" / "routes.py").read_text()
    assert "fitted_aliases=data.FITTED_ALIASES" in routes
    assert "fitted_weight=data.fitted_weight" in routes


def test_the_campaign_page_renders_with_a_fitted_lysine_weight(monkeypatch):
    """End to end, on the state that has never existed: the fit has not
    produced weights yet, so this is the first time the join is exercised
    with a value on the far side of the alias."""
    from nobble.app import create_app

    monkeypatch.setattr(app_data, "weight_fit", lambda: {
        "fitted": True,
        "weights": {"lysine_reach_exposed_fraction": 0.25,
                    "bridge_percentile": 0.75},
        "status": "fitted",
    })
    client = create_app().test_client()
    response = client.get("/campaign")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    # The server-rendered initial value, which is what missed before.
    assert 'value="0.25"' in body, (
        "the fitted lysine weight did not reach the slider's initial value"
    )
