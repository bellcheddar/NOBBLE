"""The F236 contrast is in the template and not in the published bundle.

Pose recovery fails on the 15-mer campaign, 0 of 65 within 3 A at a median of
17.54 A, and passes on the whole-domain one, 35 of 65 at 2.494 A. That
contrast is the reframing of this project's headline, so benchmark.html
carries a two-row table for it, guarded on both curves being computed.

The published bundle's comparison.json has neither key: it was built before
`nobble.validate.compare` learned to emit them. So the route walk renders the
page with the guard false and the table never appears in any test, which is
F260's lesson one file over. A Jinja error inside that block would pass the
whole suite (F261).

The live `corrected_*` campaign does have both curves computed, so the data
exists; it is the published slice that lacks it, and the atlas rebuild that
would carry it across is itself refused while the bench02 featurisation is
stale (F219).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "deploy" / "atlas"


def _live_curves() -> dict | None:
    """Both curves from whichever corrected campaign has them, or None."""
    for directory in sorted((ROOT / "campaigns").glob("corrected_*")):
        path = directory / "comparison.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        base = payload.get("baseline_recovery_curve") or {}
        corrected = payload.get("corrected_recovery_curve") or {}
        if base.get("status") == "computed" and corrected.get(
                "status") == "computed":
            return {"baseline_recovery_curve": base,
                    "corrected_recovery_curve": corrected}
    return None


def test_the_contrast_table_renders_when_both_curves_are_computed():
    """Rendered with the real curves, not a hand-made pair of numbers."""
    if not (ATLAS / "comparison.json").exists():
        pytest.skip("no published bundle to serve")
    curves = _live_curves()
    if curves is None:
        pytest.skip("no corrected campaign on disk carries both curves")

    from nobble.app import create_app, data

    real = data.precomputed

    def with_curves(name):
        payload = real(name)
        if name != "comparison.json":
            return payload
        payload = copy.deepcopy(payload) if payload else {}
        payload.update(curves)
        return payload

    app = create_app(str(ATLAS))
    app.config["TESTING"] = True
    original = data.precomputed
    data.precomputed = with_curves
    try:
        page = app.test_client().get("/benchmark")
    finally:
        data.precomputed = original
    assert page.status_code == 200, page.status_code
    text = page.get_data(as_text=True)
    assert "whole domain" in text, "the contrast table did not render"
    # The fragment cell reads "fragment (15-mer)" rather than "15-mer",
    # because a bare `<td>15-mer</td>` puts `>15` in the markup and
    # test_template_cutoffs reads that as a literal comparison.
    assert "fragment (15-mer)" in text, text[:0]
    assert str(curves["corrected_recovery_curve"]["median_rmsd"]) in text


def test_the_published_bundle_is_missing_the_curves():
    """Recorded as a fact, not asserted as correct.

    This is why the site shows the 15-mer failure without the whole-domain
    contrast beside it. When a rebuilt atlas carries the curves this test
    says so and can be deleted, which is the point of writing it as a
    statement about the bundle rather than as a guard.
    """
    path = ATLAS / "comparison.json"
    if not path.exists():
        pytest.skip("no published bundle to serve")
    payload = json.loads(path.read_text())
    present = [key for key in ("baseline_recovery_curve",
                               "corrected_recovery_curve")
               if (payload.get(key) or {}).get("status") == "computed"]
    if len(present) == 2:
        pytest.skip("the published bundle now carries both curves, so the "
                    "site shows the contrast and this test has served out")
    assert not present, (
        f"the bundle carries {present} and not the other, which would render "
        "half a contrast: the guard needs both")
