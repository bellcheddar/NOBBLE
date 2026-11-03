"""The BINMAN-LM query head over NOBBLE (spec Phase 4).

The contract these protect is the important one: the model proposes a query and
never a number. So the executor must be exercised without any model present,
and must refuse anything it does not recognise rather than improvising.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.app import lm


ROWS = [
    {"pair_id": "a", "e3_gene": "CRBN", "peptide_gene": "IKZF1", "ligand_key": "Y70",
     "modality": "glue", "tier": "benchmark", "peptide_label": "degraded",
     "bridge_percentile": 46.4, "delta_iptm": 0.32, "convergence_score": 0.73,
     "seeds_docked": 15, "seeds_total": 15, "nobble_score": None},
    {"pair_id": "b", "e3_gene": "VHL", "peptide_gene": "BRD4", "ligand_key": "759",
     "modality": "protac", "tier": "benchmark", "peptide_label": "degraded",
     "bridge_percentile": 85.4, "delta_iptm": -0.10, "convergence_score": 0.0,
     "seeds_docked": 15, "seeds_total": 15, "nobble_score": None},
]


def test_executor_needs_no_model():
    """The whole point: numbers come from Python, not from the model."""
    query = {"filter": [["e3_gene", "eq", "CRBN"]], "select": ["pair_id", "bridge_percentile"]}
    assert lm.validate(query)[0]
    rows = lm.execute(query, ROWS)
    assert rows == [{"pair_id": "a", "bridge_percentile": 46.4}]


def test_sort_and_limit():
    query = {"sort": ["bridge_percentile", "desc"], "limit": 1, "select": ["pair_id"]}
    assert lm.execute(query, ROWS) == [{"pair_id": "b"}]


def test_rejects_a_field_the_campaign_does_not_have():
    ok, reason = lm.validate({"filter": [["binding_affinity_nM", "lt", 100]]})
    assert not ok
    assert "binding_affinity_nM" in reason


def test_rejects_an_unsupported_operator():
    ok, reason = lm.validate({"filter": [["e3_gene", "contains", "CRBN"]]})
    assert not ok
    assert "operator" in reason


def test_rejects_an_unreasonable_limit():
    assert not lm.validate({"limit": 5000})[0]
    assert not lm.validate({"limit": 0})[0]


def test_sort_puts_missing_values_last():
    rows = ROWS + [{"pair_id": "c", "bridge_percentile": None}]
    out = lm.execute({"sort": ["bridge_percentile", "desc"], "select": ["pair_id"]}, rows)
    assert out[-1] == {"pair_id": "c"}


def test_abstains_when_nothing_is_scored():
    answer = lm.ask("anything", [])
    assert answer.status == "abstained"
    assert "nothing to answer from" in answer.explanation


def test_unavailable_rather_than_guessing_when_no_model_is_configured(monkeypatch):
    monkeypatch.setattr(lm, "available", lambda: False)
    answer = lm.ask("which CRBN pairs bridge best?", ROWS)
    assert answer.status == "unavailable"
    assert answer.rows == []


def test_abstains_with_a_reason_when_the_query_matches_nothing(monkeypatch):
    """Head C: say what is missing rather than answering from what is present."""
    monkeypatch.setattr(lm, "available", lambda: True)

    class Result:
        ok = True
        payload = {"filter": [["e3_gene", "eq", "KEAP1"]]}
        error = ""

    import types
    fake = types.SimpleNamespace(propose_query=lambda q, s, **k: Result(), enabled=lambda: True)
    monkeypatch.setitem(sys.modules, "app.lm", fake)
    answer = lm.ask("how does KEAP1 do?", ROWS)
    assert answer.status == "abstained"
    assert "has not run" in answer.explanation


def test_schema_only_advertises_fields_the_executor_accepts():
    for name in lm.QUERY_SCHEMA["fields"]:
        assert lm.validate({"filter": [[name, "eq", 1]]})[0], name
