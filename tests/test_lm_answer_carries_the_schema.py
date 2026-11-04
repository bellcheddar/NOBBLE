"""An answer carries what can be asked about, not every field in the row (F176).

`lm.execute` applies a `select` clause when the model supplies one. When it
does not, it used to return the whole score row, and the answer panel on the
campaign page renders exactly one field from it, `pair_id`, for at most ten
rows.

On the benchmark atlas that cost nothing. At campaign scale a default
25-row answer was 514 KB of JSON and a 100-row one, the schema's maximum,
was 2,056 KB. Nine tenths of it was `seed_records`, `plip`, `contact_map`
and `convergence`, which the panel cannot show and which the model cannot
ask about either, since they are not in the published schema. The default is
now the schema, which takes those to 12 KB and 49 KB.

The schema is the right default rather than a convenient one: it is the only
vocabulary a question can be asked in, so an answer carrying its fields is
complete with respect to anything askable, and the whole row is still served
by `/api/pair/<pair_id>`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.app import lm  # noqa: E402

HEAVY = ("seed_records", "plip", "contact_map", "convergence")


@pytest.fixture(scope="module")
def atlas_rows() -> list[dict]:
    published = ROOT / "deploy" / "atlas" / "scores.jsonl"
    if not published.exists():
        return []
    return [json.loads(line) for line in published.read_text().splitlines()
            if line.strip()]


def test_an_answer_with_no_select_carries_only_schema_fields(atlas_rows):
    if not atlas_rows:
        pytest.skip("no published atlas")
    out = lm.execute({"limit": 5}, atlas_rows)
    assert out
    allowed = set(lm.QUERY_SCHEMA["fields"])
    for row in out:
        extra = sorted(set(row) - allowed)
        assert extra == [], f"the answer carries {extra}, which is not in the schema"


def test_the_heavy_keys_are_gone(atlas_rows):
    if not atlas_rows:
        pytest.skip("no published atlas")
    carried = [key for key in HEAVY if key in atlas_rows[0]]
    if not carried:
        pytest.skip("this atlas carries none of the heavy keys")
    out = lm.execute({"limit": 5}, atlas_rows)
    for row in out:
        assert not [key for key in HEAVY if key in row]


def test_everything_askable_is_still_answered(atlas_rows):
    """The direction that matters: a smaller answer must not be a poorer one."""
    if not atlas_rows:
        pytest.skip("no published atlas")
    out = lm.execute({"limit": 1}, atlas_rows)
    source, answer = atlas_rows[0], out[0]
    for name in lm.QUERY_SCHEMA["fields"]:
        if name in source:
            assert name in answer, f"{name} is askable and was dropped"
            assert answer[name] == source[name], name


def test_a_field_the_row_does_not_carry_is_not_invented():
    """`absent` and `null` are different answers, and the schema is not data."""
    sparse = [{"pair_id": "a", "e3_gene": "CRBN"}]
    out = lm.execute({}, sparse)
    assert out == [{"pair_id": "a", "e3_gene": "CRBN"}], (
        "projecting onto the schema invented keys the row never had, which "
        "reports `not computed` as a measured null"
    )


def test_an_explicit_select_still_wins():
    rows = [{"pair_id": "a", "e3_gene": "CRBN", "bridge_percentile": 46.4}]
    assert lm.execute({"select": ["pair_id"]}, rows) == [{"pair_id": "a"}]


def test_the_field_the_panel_renders_is_always_there(atlas_rows):
    """The panel prints `row.pair_id`; an answer without it renders blank."""
    if not atlas_rows:
        pytest.skip("no published atlas")
    assert "pair_id" in lm.QUERY_SCHEMA["fields"]
    for row in lm.execute({"limit": 3}, atlas_rows):
        assert row.get("pair_id")


def test_the_default_answer_is_small_enough_to_serve(atlas_rows):
    """A bound, not a measurement: the schema's 100-row maximum must be sane.

    Checked against the campaign's shape rather than the benchmark's, by
    repeating the published rows up to 158 pairs, because the whole point is
    that the benchmark atlas was too small for this to show.
    """
    if not atlas_rows:
        pytest.skip("no published atlas")
    grown = []
    while len(grown) < 158:
        for row in atlas_rows:
            grown.append(dict(row, pair_id=f"{row['pair_id']}__{len(grown)}"))
            if len(grown) >= 158:
                break
    biggest = lm.execute({"limit": 100}, grown)
    kilobytes = len(json.dumps(biggest)) / 1024
    assert kilobytes < 200, (
        f"a 100-row answer is {kilobytes:.0f} KB; the panel renders ten "
        "pair ids from it"
    )
