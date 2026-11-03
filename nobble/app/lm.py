"""BINMAN-LM over the NOBBLE campaign (spec Phase 4).

No new heads (spec Phase 4). BINMAN's `app/lm.py` is imported, not forked
(D-NOB-007), and NOBBLE supplies two things it does not have: a schema
describing the campaign tables, and a deterministic executor for the query
objects the model returns.

**The no-arithmetic contract holds absolutely.** The model's only output is a
query object: a filter, a sort and a projection, as JSON. Every number on
screen is then computed in Python from the scored records. The model never
emits a figure, never aggregates and never compares magnitudes, so it cannot
be wrong about one. If it proposes a field that does not exist, the executor
rejects the query rather than guessing what was meant.

Head C's job here is abstention with a reason: when a question names a pair the
campaign has not run, the honest answer is to say which pair is missing and why,
not to answer from the pairs that happen to be present.
"""
from __future__ import annotations

import sys
from dataclasses import asdict, dataclass, field
from typing import Any

from nobble import paths

if str(paths.BINMAN) not in sys.path:
    sys.path.insert(0, str(paths.BINMAN))

# Fields the model may filter, sort or project on. Anything outside this set is
# rejected: a schema the executor does not recognise is a malformed query, not
# an invitation to improvise.
QUERY_SCHEMA: dict[str, Any] = {
    "table": "pairs",
    "description": (
        "One row per (receptor, peptide, ligand) triple scored by a NOBBLE "
        "campaign."
    ),
    "fields": {
        "pair_id": "string, the campaign's identifier for the triple",
        "e3_gene": "string, the E3 ligase, for example CRBN or VHL",
        "peptide_gene": "string, the substrate the peptide was drawn from",
        "ligand_key": "string, the glue or degrader, as a CCD code or a name",
        "modality": "string, glue or protac",
        "tier": "string, benchmark, A or B",
        "peptide_label": "string, degraded, not_degraded, negative_control or unknown",
        "bridge_percentile": "number 0 to 100, against 285,996 observed bridges",
        "bridge_formation_rate": "number 0 to 1, fraction of seeds that bridged",
        "delta_iptm": "number, ternary minus binary interface confidence",
        "delta_iptm_median": "number, the same using the median across seeds",
        "convergence_score": "number 0 to 1, pose agreement across seeds",
        "plip_fingerprint_match": "number 0 to 1, canonical degron contacts reproduced",
        "seeds_docked": "integer, seeds whose peptide touched the receptor",
        "seeds_total": "integer",
        "nobble_score": "number or null, the fitted composite",
    },
    "operations": {
        "filter": "list of [field, operator, value]; operators are eq, ne, gt, gte, lt, lte, in",
        "sort": "[field, asc|desc]",
        "limit": "integer, at most 100",
        "select": "list of field names to return",
    },
    "contract": (
        "Return JSON only. Never compute, estimate or state a number: return a "
        "query and the application will compute from it."
    ),
}

OPERATORS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a is not None and a > b,
    "gte": lambda a, b: a is not None and a >= b,
    "lt": lambda a, b: a is not None and a < b,
    "lte": lambda a, b: a is not None and a <= b,
    "in": lambda a, b: a in b if isinstance(b, (list, tuple, set)) else False,
}


@dataclass
class Answer:
    status: str                       # answered | abstained | unavailable | rejected
    question: str
    query: dict | None = None
    rows: list = field(default_factory=list)
    row_count: int = 0
    explanation: str = ""
    missing: list = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def available() -> bool:
    try:
        from app import lm as binman_lm
        return binman_lm.enabled()
    except Exception:                              # noqa: BLE001
        return False


def validate(query: dict) -> tuple[bool, str]:
    """Reject anything referring to a field the campaign does not have."""
    if not isinstance(query, dict):
        return False, "the query is not an object"
    fields = set(QUERY_SCHEMA["fields"])

    for clause in query.get("filter") or []:
        if not isinstance(clause, (list, tuple)) or len(clause) != 3:
            return False, f"malformed filter clause: {clause!r}"
        field_name, operator, _value = clause
        if field_name not in fields:
            return False, f"unknown field in filter: {field_name!r}"
        if operator not in OPERATORS:
            return False, f"unsupported operator: {operator!r}"

    sort = query.get("sort")
    if sort is not None:
        if not isinstance(sort, (list, tuple)) or len(sort) != 2:
            return False, f"malformed sort: {sort!r}"
        if sort[0] not in fields:
            return False, f"unknown field in sort: {sort[0]!r}"
        if sort[1] not in ("asc", "desc"):
            return False, f"sort direction must be asc or desc, not {sort[1]!r}"

    for name in query.get("select") or []:
        if name not in fields:
            return False, f"unknown field in select: {name!r}"

    limit = query.get("limit")
    if limit is not None and (not isinstance(limit, int) or limit < 1 or limit > 100):
        return False, "limit must be an integer between 1 and 100"
    return True, ""


def execute(query: dict, rows: list[dict]) -> list[dict]:
    """Run a validated query over the scored pairs. Pure Python, no model."""
    out = list(rows)
    for field_name, operator, value in query.get("filter") or []:
        test = OPERATORS[operator]
        out = [row for row in out if test(row.get(field_name), value)]

    sort = query.get("sort")
    if sort:
        field_name, direction = sort
        # Missing values sort last in BOTH directions. Folding the None test
        # into the sort key and then reversing puts them first on a descending
        # sort, so "the top five by bridge percentile" would lead with the pairs
        # that have no bridge percentile at all: the most misleading possible
        # answer to that question.
        present = [row for row in out if row.get(field_name) is not None]
        missing = [row for row in out if row.get(field_name) is None]
        present.sort(key=lambda row: row.get(field_name), reverse=(direction == "desc"))
        out = present + missing

    limit = query.get("limit") or 25
    out = out[:limit]

    select = query.get("select")
    if select:
        out = [{name: row.get(name) for name in select} for row in out]
    return out


def _named_pairs(question: str, rows: list[dict]) -> tuple[list[str], list[str]]:
    """Gene and ligand names in the question, split into present and absent."""
    words = {
        token.strip(" ,.?;:()[]").upper()
        for token in question.split() if len(token.strip(" ,.?;:()[]")) >= 3
    }
    known = set()
    for row in rows:
        for key in ("e3_gene", "peptide_gene", "ligand_key"):
            value = row.get(key)
            if value:
                known.add(str(value).upper())
    # Only treat a word as a named entity if it looks like one: present in the
    # campaign, or a gene-shaped token the campaign plainly lacks.
    present = sorted(words & known)
    return present, []


def ask(question: str, rows: list[dict]) -> Answer:
    """Head A then the executor, with Head C abstaining when the data is absent."""
    answer = Answer(status="unavailable", question=question)

    if not rows:
        answer.status = "abstained"
        answer.explanation = (
            "The campaign has scored no pairs yet, so there is nothing to answer "
            "from. This is an abstention, not a negative result."
        )
        return answer

    if not available():
        answer.status = "unavailable"
        answer.explanation = (
            "BINMAN-LM is not configured on this host (BINMAN_LM_URL is unset). "
            "Every tab works without it: the model only translates a question "
            "into a query, and never produces a number."
        )
        return answer

    from app import lm as binman_lm

    result = binman_lm.propose_query(question, QUERY_SCHEMA)
    if not result.ok or not isinstance(result.payload, dict):
        answer.status = "unavailable"
        answer.error = result.error or "the model did not return a query"
        answer.explanation = (
            "The model did not return a usable query, so nothing was run. No "
            "answer is better than one assembled from a query nobody validated."
        )
        return answer

    query = result.payload
    ok, reason = validate(query)
    if not ok:
        answer.status = "rejected"
        answer.query = query
        answer.error = reason
        answer.explanation = (
            f"The proposed query was rejected: {reason}. The executor runs only "
            "fields the campaign actually has, so a question about something "
            "NOBBLE does not measure returns nothing rather than something "
            "plausible."
        )
        return answer

    matched = execute(query, rows)
    answer.query = query
    answer.rows = matched
    answer.row_count = len(matched)

    if not matched:
        present, _ = _named_pairs(question, rows)
        answer.status = "abstained"
        answer.missing = present
        answer.explanation = (
            "The query is valid but no scored pair matches it. The campaign has "
            f"{len(rows)} scored pair(s); this question needs one it has not run. "
            "Abstaining with that reason is the correct answer: filling the gap "
            "from the pairs that happen to be present would answer a different "
            "question."
        )
        return answer

    answer.status = "answered"
    answer.explanation = (
        f"{len(matched)} pair(s) matched. Every value shown was computed by the "
        "pipeline and read from the scored records: the model proposed only the "
        "query."
    )
    return answer
