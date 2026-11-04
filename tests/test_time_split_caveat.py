"""A recovery RMSD must say whether its targets could have been memorised.

Every benchmark deposition is from 2016 to 2020, years before Boltz-2's
2021-09-30 training cutoff, so the pose-recovery numbers are entirely
retrospective. The time_split layer knows this and reports it, and the
page showed the RMSDs without it.

CLAUDE.md allows a disclaimer only where a figure would be actively
misread, and then one sentence. A recovery number a reader would take as
"how well this predicts" when every target predates the model's training
is that case. The line is generated from the layer rather than written
into the template, so it follows the data instead of needing to be
remembered.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ATLAS = ROOT / "deploy" / "atlas"


def _hints(monkeypatch, time_split):
    from nobble.app import data, routes

    # Without this the recovery panel does not render at all, and the test
    # would pass by finding no caveat because there was no figure.
    monkeypatch.setenv("NOBBLE_CAMPAIGN", str(ATLAS))
    data.configure(str(ATLAS))

    real = data.precomputed

    def fake(name):
        if name == "validation.json":
            return {"layers": {"time_split": {"summary": time_split}}}
        return real(name)

    monkeypatch.setattr(routes.data, "precomputed", fake)

    from nobble.app import create_app
    app = create_app()
    with app.test_client() as client:
        response = client.get("/benchmark")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
    return [re.sub(r"\s+", " ", h).strip()
            for h in re.findall(r'<p class="panel__hint">(.*?)</p>', body, re.S)]


@pytest.mark.skipif(not ATLAS.exists(), reason="no published atlas")
def test_an_all_retrospective_panel_says_so(monkeypatch):
    hints = _hints(monkeypatch, {
        "training_cutoff": "2021-09-30",
        "retrospective": {"n": 7, "median_rmsd": 19.235},
        "prospective": {"n": 0, "median_rmsd": None},
    })
    line = next((h for h in hints if "retrospective" in h), None)
    assert line, hints
    assert "All 7" in line
    assert "2021-09-30" in line
    # One sentence, as the house rule requires.
    assert line.count(".") == 1, line


@pytest.mark.skipif(not ATLAS.exists(), reason="no published atlas")
def test_a_blind_set_is_reported_as_a_number_not_a_caveat(monkeypatch):
    """If a post-cutoff deposition ever enters the panel, the line becomes
    the result rather than the warning. That is the point of generating it."""
    hints = _hints(monkeypatch, {
        "training_cutoff": "2021-09-30",
        "retrospective": {"n": 5, "median_rmsd": 19.2},
        "prospective": {"n": 2, "median_rmsd": 8.4},
    })
    line = next((h for h in hints if "postdate" in h), None)
    assert line, hints
    assert "2 of 7" in line
    assert "8.4" in line and "19.2" in line
    assert not any("All 7 predate" in h for h in hints)


@pytest.mark.skipif(not ATLAS.exists(), reason="no published atlas")
def test_no_line_at_all_when_the_layer_has_nothing_to_say(monkeypatch):
    """An empty summary must not render an empty claim."""
    hints = _hints(monkeypatch, {})
    assert not any("cutoff" in h for h in hints), hints


@pytest.mark.skipif(not ATLAS.exists(), reason="no published atlas")
def test_the_benchmark_page_stays_inside_the_prose_budget(monkeypatch):
    """CLAUDE.md: under 150 prose words per page, excluding tables, labels
    and pipeline-generated status text."""
    from nobble.app import create_app, data

    monkeypatch.setenv("NOBBLE_CAMPAIGN", str(ATLAS))
    data.configure(str(ATLAS))

    app = create_app()
    with app.test_client() as client:
        body = client.get("/benchmark").get_data(as_text=True)

    prose = " ".join(
        re.sub(r"<[^>]+>", " ", block)
        for block in re.findall(
            r'<p class="panel__hint">(.*?)</p>|<p class="lede">(.*?)</p>',
            body, re.S,
        )
        for block in [block[0] or block[1]]
    )
    words = len(prose.split())
    # The rule's budget, counted conservatively: the generated caveat is
    # arguably pipeline status text and excluded, and is counted anyway.
    assert words < 150, f"{words} words of hint prose on /benchmark"
