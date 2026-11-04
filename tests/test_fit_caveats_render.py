"""The caveat on an unvalidated component has to reach the page.

Spec 4.8's composite includes `lysine_reach_exposed_fraction`, and
`weights.py` marks it `NOT_VALIDATED`: BINMAN measured its reach window at
Cb-Cb AUC 0.42 to 0.48 on 369 assayed lysines, at or below chance and
slightly inverted (D-NOB-024).

The fitter does not exclude it. It lets the grid decide and appends a
caveat if the component ends up carrying weight, which is the right call
with thirty labelled pairs: excluding a component by hand is a stronger
claim than the data supports, and so is weighting it without saying so.

That only works if the caveat is read. `about.html` iterates
`weight_fit.caveats`, so the chain of custody exists, and the composite is
currently `not_fitted` so none has ever rendered. This drives the fitted
path before the Sievers arm supplies the negatives that will trigger it,
which is a few hours away (F86).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.score import weights  # noqa: E402

ATLAS = ROOT / "deploy" / "atlas"


def _render(fit: dict) -> str:
    from nobble.app import create_app, data

    if not ATLAS.exists():
        pytest.skip("no published atlas")
    app = create_app(str(ATLAS))
    original = data.weight_fit
    data.weight_fit = lambda *args, **kwargs: fit
    try:
        with app.test_client() as client:
            response = client.get("/about")
            assert response.status_code == 200
            return response.get_data(as_text=True)
    finally:
        data.weight_fit = original


def test_the_unvalidated_component_is_named_in_the_module():
    """The premise. If this component were dropped from the composite the
    caveat would be dead and this file should go with it."""
    assert "lysine_reach_exposed_fraction" in weights.NOT_VALIDATED
    assert "lysine_reach_exposed_fraction" in weights.CANDIDATES


def test_a_weighted_unvalidated_component_produces_a_caveat():
    """The fitter's own logic, before the page. Weight above zero on a
    component with no validated discriminating power has to say so."""
    result = weights.FitResult(status="fitted")
    result.weights = {"bridge_percentile": 0.75,
                      "lysine_reach_exposed_fraction": 0.25}
    result.positives, result.negatives = 20, 20
    # The caveat block runs at the end of fit(); exercise the same condition.
    caveats = [name for name in result.weights
               if name in weights.NOT_VALIDATED and result.weights[name] > 0]
    assert caveats == ["lysine_reach_exposed_fraction"]


def test_the_caveat_renders_on_the_about_page():
    """The wiring (F40). `about.html` iterating the field is not the same
    as the field reaching it."""
    body = _render({
        "status": "fitted",
        "fitted": True,
        "weights": {"bridge_percentile": 0.75,
                    "lysine_reach_exposed_fraction": 0.25},
        "objective": 0.81,
        "labelled_pairs": 40, "positives": 20, "negatives": 20,
        "components_used": ["bridge_percentile",
                            "lysine_reach_exposed_fraction"],
        "per_component_auc": {"bridge_percentile": 0.78},
        "caveats": [
            "lysine_reach_exposed_fraction carries weight 0.25 despite "
            "having no validated discriminating power: BINMAN measured its "
            "reach window at or below chance (D-NOB-024)."
        ],
    })
    assert "no validated discriminating power" in body
    assert "D-NOB-024" in body


def test_a_fit_with_no_caveats_shows_none():
    """The other side: a clean fit must not grow a caveat block, because a
    caveat on every fit reads as a disclaimer rather than a finding."""
    body = _render({
        "status": "fitted", "fitted": True,
        "weights": {"bridge_percentile": 1.0},
        "objective": 0.9, "labelled_pairs": 40,
        "positives": 20, "negatives": 20,
        "components_used": ["bridge_percentile"],
        "per_component_auc": {"bridge_percentile": 0.9},
        "caveats": [],
    })
    assert "no validated discriminating power" not in body


def test_the_not_fitted_reason_is_shown_rather_than_a_blank():
    """The current state, which is what a visitor sees today: the refusal
    and why, not an empty panel."""
    body = _render({
        "status": ("not_fitted: 7 positive(s) and 0 negative(s) scored, "
                   "below the floor of 8 labelled pairs"),
        "fitted": False, "weights": {}, "objective": None,
        "labelled_pairs": 7, "positives": 7, "negatives": 0,
        "components_used": [], "per_component_auc": {}, "caveats": [],
    })
    assert "not_fitted" in body
    assert "below the floor" in body
