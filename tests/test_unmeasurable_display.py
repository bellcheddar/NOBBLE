"""Unmeasurable seeds have to be on screen, or the rate reads as perfect.

F33 made bridge_formation_rate's denominator the seeds whose geometry
could actually be measured, which is right and makes the number honest.
It also means a pair with four usable ternaries that all bridged and four
whose output had no ligand chain now shows "4/4 seeds bridged": a perfect
rate, with half the evidence missing and nothing saying so.

So the count travels to all four places the ratio is displayed, and is
silent when it is zero, which is every pair so far.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ATLAS = ROOT / "deploy" / "atlas"
TEMPLATES = ROOT / "nobble" / "app" / "templates"

HELPER_RE = re.compile(
    r"const bridgedOf = p => .*?unmeasurable\)' : ''\);", re.S
)


def _render(monkeypatch, page, scores):
    # Patched through routes.data, not through a fresh `from nobble.app import
    # data`. test_deployed_app's droplet fixture deletes nobble.* from
    # sys.modules, so a later import builds a new module object while routes
    # still holds the old one: patching the new one passed this file alone and
    # did nothing in the full suite.
    from nobble.app import routes

    monkeypatch.setenv("NOBBLE_CAMPAIGN", str(ATLAS))
    routes.data.configure(str(ATLAS))
    monkeypatch.setattr(routes.data, "scores", lambda: scores)

    from nobble.app import create_app
    app = create_app()
    with app.test_client() as client:
        response = client.get(page)
        assert response.status_code == 200, (page, response.status_code)
        return response.get_data(as_text=True)


def _bench_score(unmeasurable):
    return {
        "pair_id": "bench01_GSPT1_CRBN", "e3_gene": "CRBN",
        "peptide_gene": "GSPT1", "tier": "benchmark",
        "bridging_seeds_with_bridge": 4, "bridging_seeds_total": 4,
        "bridging_seeds_unmeasurable": unmeasurable,
        "bridge_percentile": 88.0,
    }


@pytest.mark.skipif(not ATLAS.exists(), reason="no published atlas")
def test_the_benchmark_card_names_unmeasurable_seeds(monkeypatch):
    body = _render(monkeypatch, "/benchmark", [_bench_score(4)])
    assert "4/4 seeds bridged, 4 unmeasurable" in re.sub(r"\s+", " ", body)


@pytest.mark.skipif(not ATLAS.exists(), reason="no published atlas")
def test_the_benchmark_card_stays_quiet_when_there_are_none(monkeypatch):
    """A note on every pair would be noise: CLAUDE.md is explicit that a
    caveat repeated everywhere reads as a lack of confidence."""
    body = re.sub(r"\s+", " ", _render(monkeypatch, "/benchmark", [_bench_score(0)]))
    assert "4/4 seeds bridged" in body
    assert "unmeasurable" not in body


def _run_helper(rows):
    """Execute the real bridgedOf helper under node against given rows."""
    source = (TEMPLATES / "delta.html").read_text()
    match = HELPER_RE.search(source)
    assert match, "the bridgedOf helper is no longer in delta.html"
    script = match.group(0) + "\nconsole.log(JSON.stringify(" + json.dumps(rows) \
        + ".map(bridgedOf)));"
    completed = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, timeout=30
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_the_javascript_helper_appends_only_when_there_is_something_to_say():
    """Executed, not pattern-matched: the template's own helper run under
    node against the cases that matter."""
    out = _run_helper([
        {"bridging_seeds_with_bridge": 4, "bridging_seeds_total": 4,
         "bridging_seeds_unmeasurable": 4},
        {"bridging_seeds_with_bridge": 4, "bridging_seeds_total": 4,
         "bridging_seeds_unmeasurable": 0},
        {"bridging_seeds_with_bridge": 3, "bridging_seeds_total": 10},
        {},
    ])
    assert out == [
        "4/4 (+4 unmeasurable)",
        "4/4",
        "3/10",
        "0/0",
    ], out


def test_every_display_site_uses_the_helper():
    """Four sites showed the raw ratio. A fifth added later would reproduce
    the problem, so none may build it by hand."""
    raw = re.compile(
        r"bridging_seeds_with_bridge \|\| 0\) \+ '/' \+ \(p\.bridging_seeds_total"
    )
    for name in ("delta.html", "campaign.html"):
        source = (TEMPLATES / name).read_text()
        hand_built = [m for m in raw.finditer(source)
                      if "const bridgedOf" not in source[max(0, m.start() - 200):m.start()]]
        assert not hand_built, (
            f"{name} builds the bridged ratio by hand instead of using bridgedOf"
        )
        assert "bridgedOf(p)" in source, f"{name} does not call bridgedOf"
