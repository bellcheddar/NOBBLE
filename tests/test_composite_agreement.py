"""Two implementations of spec 4.8, compared by running both.

The composite is computed twice. `nobble/score/weights.py` computes it for
the pipeline and stores it as `nobble_score`; `nobble/app/static/js/nobble.js`
recomputes it in the browser on every slider move, which is what lets the
ranking re-derive without a round trip.

They agree. They are also the kind of pair that agrees until it does not, and
nothing compared them: a normalisation changed on one side would silently
give the page a different ranking from the pipeline, and the page is where the
ranking is read.

So this runs both. The JavaScript is loaded under node with the smallest
browser stubs that let it initialise, by `qc/composite_harness.mjs`, and its
real `composite` is called on the same rows and weights as Python's `apply`.
Transcribing the formula into Python would have tested my transcription
(F123).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.app import data as app_data  # noqa: E402
from nobble.score import weights  # noqa: E402

HARNESS = ROOT / "qc" / "composite_harness.mjs"
SCRIPT = ROOT / "nobble" / "app" / "static" / "js" / "nobble.js"


def _rows() -> list[dict]:
    for scores in sorted((ROOT / "campaigns").glob("*/scores.jsonl")):
        rows = [json.loads(line) for line in scores.read_text().splitlines()
                if line.strip()]
        if rows:
            return rows
    return []


def _ui_weights() -> dict:
    return {key: meta["default_weight"] for key, meta in app_data.COMPONENTS.items()}


def _fitter_weights(ui: dict) -> dict:
    return {app_data.FITTED_ALIASES.get(key, key): value
            for key, value in ui.items()}


def _javascript(rows: list[dict], ui_weights: dict, tmp_path: Path) -> list[dict]:
    if not shutil.which("node"):
        pytest.skip("node is not available")
    payload = tmp_path / "input.json"
    payload.write_text(json.dumps({"rows": rows, "weights": ui_weights}))
    result = subprocess.run(
        ["node", str(HARNESS), str(SCRIPT), str(payload)],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr[-600:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_the_two_implementations_agree_on_every_scored_pair(tmp_path):
    rows = _rows()
    if not rows:
        pytest.skip("no scored campaign on this checkout")

    ui = _ui_weights()
    js = _javascript(rows, ui, tmp_path)
    assert len(js) == len(rows)

    worst = 0.0
    for row, from_js in zip(rows, js):
        from_python = weights.apply(row, _fitter_weights(ui))
        assert (from_python is None) == (from_js["score"] is None), (
            row["pair_id"], from_python, from_js["score"]
        )
        if from_python is None:
            continue
        # Python rounds to four decimals and the browser does not, so they
        # agree to that and no closer.
        worst = max(worst, abs(from_python - from_js["score"]))
    assert worst < 1e-4, worst


def test_the_coverage_agrees_too(tmp_path):
    """The number the page shows beside the score, and the one F123 added to
    the stored record."""
    rows = _rows()
    if not rows:
        pytest.skip("no scored campaign on this checkout")

    ui = _ui_weights()
    js = _javascript(rows, ui, tmp_path)
    for row, from_js in zip(rows, js):
        from_python = weights.coverage(row, _fitter_weights(ui))
        assert from_python["components"] == from_js["components"], row["pair_id"]
        assert from_python["requested"] == from_js["requested"], row["pair_id"]
        assert from_python["complete"] == from_js["complete"], row["pair_id"]


def test_the_panel_really_does_contain_an_incomplete_pair(tmp_path):
    """Otherwise the two tests above agree about a distinction neither is
    exercising. Two of the seven benchmark pairs score on fewer components
    than the weights ask for."""
    rows = _rows()
    if not rows:
        pytest.skip("no scored campaign on this checkout")
    ui = _fitter_weights(_ui_weights())
    incomplete = [row["pair_id"] for row in rows
                  if not weights.coverage(row, ui)["complete"]]
    assert incomplete, "every pair is complete, so the coverage check is idle"


def test_the_stored_record_carries_the_coverage():
    """A score without it is not comparable to another score, which is the
    whole reason the browser reports it."""
    source = (ROOT / "nobble" / "score" / "run.py").read_text()
    assert 'entry["nobble_score_coverage"] = weights.coverage(' in source


def test_a_zero_weight_is_not_requested():
    """A component weighted zero is not missing from the score, it is
    excluded from it, so it must not count against coverage. The lysine
    component defaults to zero weight, which is D-NOB-024."""
    row = {"bridge_percentile": 50.0, "delta_iptm": 0.1,
           "convergence_score": 0.5, "plip_fingerprint_match": 0.5}
    full = weights.coverage(row, {"bridge_percentile": 1.0, "delta_iptm": 1.0,
                                  "convergence_score": 1.0,
                                  "plip_fingerprint_match": 1.0,
                                  "lysine_reach_exposed_fraction": 0.0})
    assert full == {"components": 4, "requested": 4, "complete": True}, full


def test_a_missing_component_is_requested_but_not_available():
    row = {"bridge_percentile": 50.0, "delta_iptm": 0.1,
           "convergence_score": None, "plip_fingerprint_match": None}
    partial = weights.coverage(row, {"bridge_percentile": 1.0,
                                     "delta_iptm": 1.0,
                                     "convergence_score": 1.0,
                                     "plip_fingerprint_match": 1.0})
    assert partial == {"components": 2, "requested": 4, "complete": False}, partial
    # And the score is still produced, over what was there.
    assert weights.apply(row, {"bridge_percentile": 1.0, "delta_iptm": 1.0,
                               "convergence_score": 1.0,
                               "plip_fingerprint_match": 1.0}) is not None
