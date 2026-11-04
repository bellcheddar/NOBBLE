"""The question endpoint must not crash on what the model hands it.

CLAUDE.md: BINMAN-LM never computes, estimates or reports a number. The
design honours that exactly. The model's only output is a query object, the
executor runs it in Python, and every `explanation` on the Answer is a
Python f-string rather than model prose.

What was missing was the other half: the query is untrusted input.
`validate` checked field names, operators, sort direction and the limit, and
never looked at a filter's value. A model asked "which pairs have a high
delta-ipTM" can reasonably answer ["delta_iptm", "gt", "high"], and Python
raises comparing a float to a string, so /api/ask returned 500 instead of
saying what was wrong with the query.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.app import lm  # noqa: E402

ROWS = [
    {"pair_id": "bench01_GSPT1_CRBN", "e3_gene": "CRBN", "delta_iptm": 0.3},
    {"pair_id": "bench02_BRD4_VHL", "e3_gene": "VHL", "delta_iptm": 0.1},
]


@pytest.mark.parametrize("value", ["high", None, [0.2], True, {"a": 1}])
def test_an_ordered_filter_on_a_number_rejects_a_non_number(value):
    """Each of these raised a TypeError out of execute() before."""
    ok, reason = lm.validate({"filter": [["delta_iptm", "gt", value]]})
    assert not ok, f"{value!r} was accepted"
    assert "needs a number" in reason, reason


def test_an_ordered_filter_on_a_string_rejects_a_number():
    ok, reason = lm.validate({"filter": [["e3_gene", "lt", 3]]})
    assert not ok
    assert "needs a string" in reason


def test_in_requires_a_list():
    ok, reason = lm.validate({"filter": [["e3_gene", "in", "CRBN"]]})
    assert not ok
    assert "list of values" in reason


def test_equality_across_types_is_still_allowed():
    """eq and ne cannot raise: a float is simply not equal to a string, and
    rejecting those would turn a harmless query into an error."""
    ok, _ = lm.validate({"filter": [["delta_iptm", "eq", "x"]]})
    assert ok
    assert lm.execute({"filter": [["delta_iptm", "eq", "x"]]}, ROWS) == []


def test_a_well_formed_query_still_runs():
    ok, _ = lm.validate({"filter": [["delta_iptm", "gt", 0.2]], "limit": 5})
    assert ok
    out = lm.execute({"filter": [["delta_iptm", "gt", 0.2]]}, ROWS)
    assert [row["pair_id"] for row in out] == ["bench01_GSPT1_CRBN"]


def test_every_field_has_a_declared_type():
    """The assertion in the module makes this a failure at import, so this
    test is about the pairing staying visible rather than catching drift
    late: a field added without a type would otherwise surface as a 500 on
    the first question that filtered on it."""
    assert set(lm.FIELD_TYPES) == set(lm.QUERY_SCHEMA["fields"])
    assert set(lm.FIELD_TYPES.values()) <= {"number", "string"}
    # Published, so the model is told the types rather than inferring them
    # from the prose descriptions.
    assert lm.QUERY_SCHEMA["types"] == lm.FIELD_TYPES


def test_ask_reports_a_failing_query_rather_than_raising(monkeypatch):
    """The floor under validate(). A shape nobody anticipated must come back
    as an answer, not a stack trace."""
    class Result:
        ok = True
        payload = {"filter": [["delta_iptm", "gt", 0.2]]}
        error = None

    import types
    fake = types.ModuleType("app.lm")
    fake.propose_query = lambda question, schema: Result()
    monkeypatch.setitem(sys.modules, "app.lm", fake)
    monkeypatch.setattr(lm, "available", lambda: True)

    def boom(query, rows):
        raise RuntimeError("something nobody thought of")

    monkeypatch.setattr(lm, "execute", boom)

    answer = lm.ask("anything", ROWS)
    assert answer.status == "rejected"
    assert "RuntimeError" in (answer.error or "")
    assert "could not be run" in answer.explanation


def test_no_explanation_is_model_authored():
    """The no-arithmetic contract in one assertion: every sentence the user
    reads is built here, so the model cannot state a figure even when it is
    the one being asked."""
    import ast

    source = (ROOT / "nobble" / "app" / "lm.py").read_text()
    tree = ast.parse(source)
    assigned = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Attribute)
                        and target.attr == "explanation"):
                    assigned.append(node.value)
    assert assigned, "no explanation is assigned anywhere: has ask() moved?"
    for value in assigned:
        # A literal, or an f-string, or a parenthesised concatenation of
        # them. Never a name carrying something the model returned.
        assert isinstance(value, (ast.Constant, ast.JoinedStr, ast.BinOp)), (
            f"explanation assigned from {type(value).__name__}, which could "
            "carry model text"
        )


def test_an_unconfigured_check_does_not_import_binman(monkeypatch):
    """Checking availability must not change what a later test can fake.

    `from app import lm` binds a real `lm` attribute on the `app` package,
    and that attribute then wins over anything in `sys.modules`. So a
    single unconfigured availability check anywhere in a session
    permanently defeated `monkeypatch.setitem(sys.modules, "app.lm", ...)`,
    and two tests that passed alone failed in the suite once the campaign
    page started asking whether a model was configured (F70).
    """
    monkeypatch.delenv(lm.LM_URL_VARIABLE, raising=False)
    monkeypatch.delitem(sys.modules, "app", raising=False)
    monkeypatch.delitem(sys.modules, "app.lm", raising=False)

    assert lm.available() is False
    assert "app.lm" not in sys.modules, (
        "an unconfigured availability check imported BINMAN's model module, "
        "which binds app.lm for the rest of the session"
    )


def test_a_configured_check_still_consults_binman(monkeypatch):
    """The guard must not become the whole answer: with the variable set,
    the real check still runs and its verdict is what counts."""
    import types

    monkeypatch.setenv(lm.LM_URL_VARIABLE, "http://127.0.0.1:9/v1")
    fake = types.SimpleNamespace(enabled=lambda: False)
    monkeypatch.setitem(sys.modules, "app", types.SimpleNamespace(lm=fake))
    monkeypatch.setitem(sys.modules, "app.lm", fake)
    assert lm.available() is False

    fake.enabled = lambda: True
    assert lm.available() is True


def test_the_variable_name_matches_binmans():
    """Two copies of a name is how they come to differ. BINMAN gates its
    model on this variable and NOBBLE skips the import when it is unset,
    so a rename there would silently disable the feature here."""
    from nobble import paths

    source = (paths.BINMAN / "app" / "lm.py")
    if not source.exists():
        pytest.skip("BINMAN is not checked out beside this project")
    assert lm.LM_URL_VARIABLE in source.read_text(), (
        f"BINMAN no longer mentions {lm.LM_URL_VARIABLE}"
    )
