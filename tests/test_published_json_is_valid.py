"""Everything a browser parses must be JSON a browser accepts.

Python's `json.dumps` writes `NaN`, `Infinity` and `-Infinity` by default.
None of the three is valid JSON, and `JSON.parse` rejects all three with a
syntax error. So a single non-finite number anywhere in the atlas or in an
API response does not produce a wrong figure on the page: it produces no
page, because the whole document fails to parse.

Nothing checked, and the exposure is real rather than theoretical.
`deploy/build_atlas.py` runs `scipy.stats.pearsonr` and `spearmanr` on the
recovery-against-bridge points and publishes `round(float(r), 3)`. It
imports no finiteness guard of its own, and `tests/test_numeric_rule.py`,
which enforces F76 and F77's rule about what counts as a number, scans only
`ROOT / "nobble"`, so `deploy/` was outside it (F127).

A NaN cannot reach that correlation today: `median_rmsd` comes through
`finite_values` and `bridge_rate` divides by a total checked non-zero. Both
guards are upstream and neither is stated where the correlation is taken.
This states it at the boundary that matters, which is the file a browser
loads.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PUBLISHED = ROOT / "deploy" / "atlas"
ENDPOINTS = (
    "/api/pairs", "/api/state", "/api/status", "/api/schema",
    "/api/components",
)


def _strict(text: str):
    """Parse the way a browser does, rejecting the three Python extensions."""
    def refuse(value):
        raise ValueError(f"{value} is not valid JSON")

    return json.loads(text, parse_constant=refuse)


def test_the_strict_parser_really_rejects_what_python_writes():
    """The control. Without it the tests below could pass against a parser
    that accepts everything."""
    import math

    loose = json.dumps({"r": math.nan})
    assert "NaN" in loose, loose
    with pytest.raises(ValueError):
        _strict(loose)
    # And it still accepts ordinary JSON.
    assert _strict('{"r": 0.5, "ok": true, "n": null}') == {
        "r": 0.5, "ok": True, "n": None}


def test_every_published_file_is_json_a_browser_accepts():
    from conftest import published_files

    files = [path for path in published_files() if path.suffix == ".json"]
    if not files:
        pytest.skip("no published atlas")
    for path in files:
        try:
            _strict(path.read_text())
        except ValueError as problem:
            raise AssertionError(f"{path.name}: {problem}") from None
    assert len(files) >= 5, [p.name for p in files]


def test_no_published_file_carries_a_non_finite_token():
    """Belt and braces, and a clearer message than a parse error at an
    offset: a reader needs to know which field, not which byte.

    Across every published text file, not one extension of it: the JSONL
    records hold a hundred rows each and are where a non-finite component
    would surface (F129).
    """
    from conftest import published_files

    files = published_files()
    if not files:
        pytest.skip("no published atlas")
    for path in files:
        text = path.read_text()
        for token in ("NaN", "Infinity"):
            assert token not in text, (path.name, token)


def test_every_published_jsonl_line_is_json_a_browser_accepts():
    """A `.jsonl` file is one document per line, so widening the scan to it
    is a parsing change rather than a glob change. The licensing tests
    failed with a decode error the moment their glob was corrected, which is
    how this was noticed."""
    from conftest import published_documents

    checked = 0
    for path, line, _document in published_documents((".jsonl",)):
        checked += 1
    if not checked:
        pytest.skip("no published JSONL records")
    assert checked > 50, checked

    # And strictly, line by line, with the line named on failure.
    for path in sorted(PUBLISHED.glob("*.jsonl")):
        for number, text in enumerate(path.read_text().splitlines(), start=1):
            if not text.strip():
                continue
            try:
                _strict(text)
            except ValueError as problem:
                raise AssertionError(f"{path.name}:{number}: {problem}") from None


def test_every_api_response_is_json_a_browser_accepts():
    from nobble.app import create_app

    client = create_app().test_client()
    for path in ENDPOINTS:
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code)
        try:
            _strict(response.get_data(as_text=True))
        except ValueError as problem:
            raise AssertionError(f"{path}: {problem}") from None


def test_a_pair_response_is_too():
    """The widest payload: a pair record carries every scored component, so
    it is where a non-finite one would surface first."""
    from nobble.app import create_app

    client = create_app().test_client()
    rows = client.get("/api/pairs").get_json() or []
    if not rows:
        pytest.skip("no scored pair on this checkout")
    pair = rows[0]["pair_id"]
    for path in (f"/api/pair/{pair}", f"/api/pair/{pair}/structures"):
        _strict(client.get(path).get_data(as_text=True))


def test_the_correlation_publishes_finite_numbers_or_nothing():
    """The specific case that prompted this. If the correlation cannot be
    computed the fields should be absent, not present and non-finite."""
    import math

    path = PUBLISHED / "recovery_vs_bridge.json"
    if not path.exists():
        pytest.skip("no correlation in the bundle")
    payload = _strict(path.read_text())
    for field in ("pearson_r", "pearson_p", "spearman_rho", "spearman_p"):
        if field not in payload:
            continue
        value = payload[field]
        assert isinstance(value, (int, float)) and math.isfinite(value), (
            field, value)
    for point in payload.get("points", []):
        for field in ("bridge_rate", "median_rmsd", "best_rmsd"):
            value = point.get(field)
            if value is None:
                continue
            assert math.isfinite(value), (point.get("pair_id"), field, value)
