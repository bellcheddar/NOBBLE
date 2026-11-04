"""Cutoffs in the templates that have a twin in the configuration.

F28 swept Python for hard-coded cutoffs in three places: comparisons,
module constants and default arguments. F54 found a fourth, and it was in
another language: delta.html refused to draw the ROC below a literal 3
while the Python layer read the same floor from thresholds.toml, so the
chart and the validation report were one edit from disagreeing about
whether a curve may be drawn at all.

This is the sweep that should have followed. Every numeric comparison in
the templates, checked for a twin in the configuration.

Three were found. The ROC floor, fixed in F54. benchmark.html's first
colour band, whose own comment says it is "banded on the success-rate
breakpoints the curve already uses" and which was a literal 5 beside a
configured [1, 2, 3, 5]. And the significance level the same page applies
to its Pearson p, a literal 0.05 with no Python twin at all, so an ad-hoc
grep for divergence would never have found it: nothing disagreed with it
because nothing else held it. All three are F55.

The rest are the chart's own: the near-miss bands at 10 and 15 angstrom
have no twin, and `lift < 0` is a sign test rather than a cutoff, on the
same reasoning that keeps 0 and 1 out of the Python integer sweep.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEMPLATES = sorted((ROOT / "nobble" / "app" / "templates").glob("*.html"))

# Comparisons against a literal that are the chart's own, with the reason.
# Anything else must read its value from the configuration.
ALLOWED = {
    "p.median_rmsd <= 10":
        "near-miss band, the chart's own: close enough to be worth refining",
    "p.median_rmsd <= 15":
        "near-miss band, the chart's own: beyond this is a different site",
    "p.lift < 0":
        "a sign test, not a cutoff: negative lift is coloured as a loss",
}


def _comparisons() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    pattern = re.compile(r"[A-Za-z_][\w.]*\s*[<>]=?\s*-?\d+(?:\.\d+)?")
    for template in TEMPLATES:
        for number, line in enumerate(template.read_text().splitlines(), start=1):
            stripped = line.strip()
            # Comments carry example numbers and are not code.
            if stripped.startswith(("*", "/*", "{#", "<!--", "//")):
                continue
            for match in pattern.finditer(line):
                text = " ".join(match.group(0).split())
                found.setdefault(text, []).append(f"{template.name}:{number}")
    return found


def test_no_template_compares_against_an_unexplained_literal():
    found = _comparisons()
    unexplained = {text: where for text, where in found.items()
                   if text not in ALLOWED}
    assert not unexplained, (
        "template comparison(s) against a literal with no entry saying why "
        f"they are not configured: {unexplained}"
    )


def test_the_allowances_are_all_still_real():
    """An allowlist that outlives what it allows is a hole."""
    found = _comparisons()
    stale = [text for text in ALLOWED if text not in found]
    assert not stale, f"ALLOWED names comparisons that are gone: {stale}"


def _rendered(page: str, name: str):
    from nobble.app import create_app

    atlas = ROOT / "deploy" / "atlas"
    if not atlas.exists():
        pytest.skip("no published atlas")
    app = create_app(str(atlas))
    with app.test_client() as client:
        response = client.get(page)
        assert response.status_code == 200
        body = response.get_data(as_text=True)
    match = re.search(rf"const {name} = ([\d.]+);", body)
    assert match, f"{name} is not rendered into {page}"
    return float(match.group(1))


def test_the_recovered_band_is_the_curves_loosest_breakpoint():
    """The chart's comment claims the band matches the curve. It does now
    because both read one value, not because two literals agree."""
    from nobble import paths

    breakpoints = paths.thresholds()["scoring"]["rmsd_breakpoints"]
    assert _rendered("/benchmark", "RECOVERED_A") == float(max(breakpoints))


def test_a_changed_breakpoint_moves_the_band(monkeypatch):
    """The only check that would have caught the divergence."""
    import json

    from nobble import paths

    original = paths.thresholds()

    def fake():
        altered = json.loads(json.dumps(original))
        altered["scoring"]["rmsd_breakpoints"] = [1.0, 2.0, 3.0, 4.0]
        return altered

    monkeypatch.setattr(paths, "thresholds", fake)
    assert _rendered("/benchmark", "RECOVERED_A") == 4.0


def _pearson() -> tuple[str, float | None]:
    """The rendered class on the Pearson stat.

    The alpha is applied in a Jinja condition rather than rendered as a
    constant, so the only honest check is the effect it has on the page.
    """
    from nobble.app import create_app

    atlas = ROOT / "deploy" / "atlas"
    if not atlas.exists():
        pytest.skip("no published atlas")
    app = create_app(str(atlas))
    with app.test_client() as client:
        response = client.get("/benchmark")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
    match = re.search(
        r'<div class="stat([^"]*)">\s*<span class="stat__label">Pearson r'
        r'</span>.*?<span class="stat__sub">p = ([^<]*)</span>',
        body, re.S,
    )
    assert match, "the Pearson stat is no longer on the page"
    shown = match.group(2).strip()
    observed = None if shown in ("", "\u2014", "None") else float(shown)
    return match.group(1).strip(), observed


def test_the_rendered_class_agrees_with_the_configured_alpha():
    from nobble import paths

    alpha = float(paths.thresholds()["scoring"]["significance_alpha"])
    rendered, observed = _pearson()
    if observed is None:
        pytest.skip("no correlation computed on this atlas")
    assert rendered == ("stat--good" if observed < alpha else "stat--warn")


@pytest.mark.parametrize("alpha,expected", [(0.0, "stat--warn"),
                                            (1.0, "stat--good")])
def test_a_changed_alpha_moves_the_colour(monkeypatch, alpha, expected):
    """The check that would have caught a literal left behind. Both ends,
    because a page that ignores the value would pass one of them by luck."""
    import json

    from nobble import paths

    if _pearson()[1] is None:
        pytest.skip("no correlation computed on this atlas")

    original = paths.thresholds()

    def fake():
        altered = json.loads(json.dumps(original))
        altered["scoring"]["significance_alpha"] = alpha
        return altered

    monkeypatch.setattr(paths, "thresholds", fake)
    assert _pearson()[0] == expected
