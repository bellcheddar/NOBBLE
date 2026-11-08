"""The paired scramble panel (F316).

The page already says the bridge filter finds six of six deposited bridges
(F297). The paired test says the same statistic is higher on the scramble in
14 of 23 comparisons. Both are true and they answer different questions, so
the panel exists to stop the page answering only the flattering one.

These check that a statistic pointing the wrong way is visible as such, that
the family-wise threshold travels with the p-values, and that a bundle
without the test says so.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MEASURED = {
    "status": "measured",
    "statistics_tested": 6,
    "any_one_crossing_by_chance": 0.265,
    "bonferroni_threshold": 0.00833,
    "results": [
        {"statistic": "convergence_score", "parent_higher": 25,
         "scramble_higher": 1, "tied": 5, "p_two_sided": 0.0,
         "direction": "parent", "compared": 26},
        {"statistic": "delta_iptm", "parent_higher": 22,
         "scramble_higher": 9, "tied": 0, "p_two_sided": 0.02945,
         "direction": "parent", "compared": 31},
        {"statistic": "bridge_percentile", "parent_higher": 9,
         "scramble_higher": 14, "tied": 0, "p_two_sided": 0.40487,
         "direction": "scramble", "compared": 23},
    ],
}


def _page(tmp_path: Path, about: dict | None) -> str:
    from nobble.app import create_app

    if about is not None:
        (tmp_path / "about.json").write_text(json.dumps(about))
    app = create_app(str(tmp_path))
    app.config["TESTING"] = True
    body = app.test_client().get("/about")
    assert body.status_code == 200, body.status_code
    return body.get_data(as_text=True)


def test_a_statistic_that_loses_shows_both_columns(tmp_path):
    """9 and 14 side by side. A panel printing only the p would show 0.40487
    for the primary signal and leave which way it went unsaid."""
    page = _page(tmp_path, {"paired_scrambles": MEASURED})
    assert "Each pair against its own scramble" in page
    assert "bridge_percentile" in page
    assert "0.40487" in page
    # The losing counts are both present, so the direction is readable.
    assert ">9<" in page and ">14<" in page


def test_the_threshold_travels_with_the_p_values(tmp_path):
    """Six p-values and no family is an invitation to read the smallest."""
    page = _page(tmp_path, {"paired_scrambles": MEASURED})
    assert "6 statistics" in page
    assert "0.00833" in page


def test_only_a_p_below_the_threshold_is_marked(tmp_path):
    """delta_iptm at 0.029 is not marked and convergence_score at 0.0 is,
    which is the whole point of printing the threshold."""
    page = _page(tmp_path, {"paired_scrambles": MEASURED})
    rows = page[page.index("convergence_score"):page.index("Beating a scramble")]
    convergence = rows[:rows.index("delta_iptm")]
    delta = rows[rows.index("delta_iptm"):rows.index("bridge_percentile")]
    assert "*" in convergence, convergence
    assert "*" not in delta, delta


def test_the_panel_says_a_scramble_is_the_easy_question(tmp_path):
    """Without it, two statistics clearing a corrected threshold reads as
    validation."""
    page = _page(tmp_path, {"paired_scrambles": MEASURED})
    assert "necessary and not sufficient" in page


def test_an_older_bundle_says_so(tmp_path):
    page = _page(tmp_path, {"sources": {}})
    assert "Each pair against its own scramble" in page
    assert "built before the test existed" in page


def test_a_failed_computation_carries_its_reason(tmp_path):
    page = _page(tmp_path, {"paired_scrambles": {
        "status": "unavailable: KeyError: 'nobble_score'", "results": []}})
    assert "KeyError" in page


def test_the_build_computes_it_in_its_own_guard():
    """A failure here must not take the rest of about.json with it."""
    source = (ROOT / "deploy" / "build_atlas.py").read_text()
    assert "scramble_paired_test" in source
    assert '"paired_scrambles": paired_scrambles' in source
    position = source.index("import scramble_paired_test")
    assert "except Exception as problem" in source[position:position + 900]
