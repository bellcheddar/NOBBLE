"""Spec 1.2's natural-language component had no way to reach it.

    Natural language | Query translation, evidence triage, abstention |
    BINMAN-LM (binman-qwen-2.5-3b-4bit-round15), no new heads

Head A translates a question into a query object and Head C abstains when
the campaign has not run the pair in question. Both are implemented in
`nobble/app/lm.py`, both are tested, and `/api/ask` serves them.

Nothing called it. The app's only fetch targets were `/api/pair/` and
`/api/status`, so no user could ask a question. PROGRESS.md described the
query head as part of a complete Phase 4, which was true of the backend and
not of anything a reader could use: the project's own recurring shape, a
component whose output nothing reads.

The panel renders the count and the matched pair identifiers, which the
executor computed in Python, and the translated query labelled as the
model's reading of the question and kept away from the figures. The
no-arithmetic contract is why that separation exists (F69, D-NOB-058).
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

TEMPLATE = ROOT / "nobble" / "app" / "templates" / "campaign.html"
ATLAS = ROOT / "deploy" / "atlas"


def _page(available: bool) -> str:
    from nobble.app import create_app, routes

    if not ATLAS.exists():
        pytest.skip("no published atlas")
    app = create_app(str(ATLAS))
    original = routes._lm_available
    routes._lm_available = lambda: available
    try:
        with app.test_client() as client:
            response = client.get("/campaign")
            assert response.status_code == 200
            return response.get_data(as_text=True)
    finally:
        routes._lm_available = original


def test_the_panel_offers_a_question_when_a_model_is_configured():
    body = _page(True)
    assert "Ask the ledger" in body
    assert 'id="ask-form"' in body
    assert "/api/ask" in body, "the form is not wired to the endpoint"


def test_the_panel_says_so_when_no_model_is_configured():
    """The droplet serves a precomputed atlas and has no model behind it,
    so unavailable is a normal state rather than a failure."""
    body = _page(False)
    assert "Ask the ledger" in body
    assert "No model is configured" in body
    assert 'id="ask-form"' not in body
    assert "/api/ask" not in body, (
        "a form that cannot work is still wired to the endpoint"
    )


def test_the_unavailable_message_does_not_undermine_the_page():
    """One sentence, and it says the figures do not depend on the model.
    A panel that reads as broken would make a reader doubt the numbers
    beside it, which are computed in Python either way."""
    body = _page(False)
    assert "does not depend on it" in body


def _run_panel(answer: dict) -> str:
    """Run the template's own askPanel helper under node (F50)."""
    source = TEMPLATE.read_text()
    match = re.search(r"const askPanel = answer => \{.*?\n  \};\n", source, re.S)
    assert match, "askPanel is no longer a named helper in campaign.html"
    script = match.group(0) + (
        f"console.log(askPanel({json.dumps(answer)}));")
    completed = subprocess.run(["node", "-e", script], capture_output=True,
                               text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    return completed.stdout


def test_an_answered_question_shows_the_count_and_the_pairs():
    html = _run_panel({
        "status": "answered", "row_count": 2,
        "rows": [{"pair_id": "sv001_ZNF1_CRBN"}, {"pair_id": "sv002_ZNF2_CRBN"}],
        "explanation": "2 pair(s) matched.",
        "query": {"field": "delta_iptm", "op": "gt", "value": 0.3},
    })
    assert "<strong>2</strong>" in html
    assert "sv001_ZNF1_CRBN" in html and "sv002_ZNF2_CRBN" in html


def test_the_translated_query_is_labelled_as_the_model_s_reading():
    """The no-arithmetic contract's edge. A threshold in the query was
    chosen by the model, so it is shown as what was asked and must never
    sit among the figures as though it were measured."""
    html = _run_panel({
        "status": "answered", "row_count": 1,
        "rows": [{"pair_id": "p1"}], "explanation": "1 pair(s) matched.",
        "query": {"field": "delta_iptm", "op": "gt", "value": 0.5},
    })
    assert "Read as a filter" in html
    position = html.index("Read as a filter")
    assert html.index("<strong>1</strong>") < position, (
        "the model's query is rendered above the computed count"
    )


def test_an_abstention_shows_its_reason_and_no_count():
    """Head C's job. An abstention with no reason is the thing this
    project keeps finding, and a count of zero would read as a result."""
    html = _run_panel({
        "status": "abstained", "row_count": 0, "rows": [],
        "explanation": "The query is valid but no scored pair matches it.",
    })
    assert "no scored pair matches" in html
    assert "<strong>" not in html, "an abstention rendered a figure"


def test_an_unavailable_answer_still_says_something():
    html = _run_panel({"status": "unavailable", "explanation": ""})
    assert html.strip(), "the panel rendered nothing at all"
    assert "unavailable" in html


def test_a_rejected_query_shows_the_explanation_not_the_error():
    """The error carries an exception message, which can contain model
    text. The explanation is written in Python."""
    html = _run_panel({
        "status": "rejected", "explanation": "The query validated but could "
        "not be run.", "error": "KeyError: 'delta_iptm_invented_by_model'",
    })
    assert "could not be run" in html
    assert "KeyError" not in html
    assert "invented_by_model" not in html


def test_the_row_list_is_capped():
    """A question matching every pair would otherwise print 158 list items
    into a sidebar panel."""
    rows = [{"pair_id": f"p{index}"} for index in range(40)]
    html = _run_panel({"status": "answered", "row_count": 40, "rows": rows,
                       "explanation": "40 pair(s) matched."})
    assert html.count("<li>") <= 10
    assert "<strong>40</strong>" in html, (
        "the cap changed the count, which must stay the executor's"
    )


def test_the_panel_uses_depot_tokens_only():
    """The design system, not the house palette. A literal colour here is
    how a panel comes to look like a different product (F68)."""
    css = (ROOT / "nobble" / "app" / "static" / "css" / "nobble.css").read_text()
    block = css[css.index("#ask-form"):]
    literals = re.findall(r"#[0-9A-Fa-f]{3,8}\b", block)
    assert not literals, f"literal colour(s) in the ask panel styles: {literals}"
    assert "var(--" in block
