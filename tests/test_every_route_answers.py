"""Every route the app declares, answered locally, before any deploy.

Individual routes are covered in several files and `tests/test_deployed_app.py`
checks the live site, which needs the droplet. Nothing walked
`app.url_map`, so a route added later was untested until it was deployed, and
the thing that would have caught it is a request.

Two properties, and the second is why this is written as a walk rather than a
list. No route may answer 5xx. And every declared route must have a sample
value here, so adding a parameterised route fails this test until someone
supplies one deliberately, rather than quietly leaving it unexercised.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "deploy" / "atlas"


def _app():
    from nobble.app import create_app

    app = create_app(str(ATLAS))
    app.config["TESTING"] = True
    return app


def _samples():
    """Real values from the published bundle, for the parameterised routes."""
    from nobble.app import create_app

    app = create_app(str(ATLAS))
    app.config["TESTING"] = True
    client = app.test_client()
    payload = client.get("/api/pairs").get_json()
    rows = payload if isinstance(payload, list) else (
        (payload or {}).get("pairs") or (payload or {}).get("rows") or [])
    pair = rows[0].get("pair_id") if rows else None
    structures = sorted(p.name[:-4] for p in (ATLAS / "structures").glob("*.cif"))
    deposited = None
    benchmark = ATLAS / "benchmark.json"
    if benchmark.exists():
        text = benchmark.read_text()
        for candidate in json.loads(text).get("pairs", []) if isinstance(
                json.loads(text), dict) else []:
            deposited = (candidate or {}).get("pdb_id")
            if deposited:
                break
    return {
        "pair_id": pair,
        "job_id": structures[0] if structures else None,
        "pdb_id": deposited or "5HXB",
    }


def test_no_route_answers_with_a_server_error():
    if not (ATLAS / "comparison.json").exists():
        pytest.skip("no published bundle to serve")
    app = _app()
    samples = _samples()
    client = app.test_client()

    missing, failures = [], []
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        if "static" in rule.rule:
            continue
        methods = rule.methods - {"HEAD", "OPTIONS"}
        path, unresolved = rule.rule, []
        for name in rule.arguments:
            value = samples.get(name)
            if value is None:
                unresolved.append(name)
                continue
            path = path.replace(f"<{name}>", str(value))
            path = path.replace(f"<path:{name}>", str(value))
        if unresolved:
            missing.append(f"{rule.rule} needs a sample for {unresolved}")
            continue
        if "<" in path:
            missing.append(f"{rule.rule} left a converter unfilled: {path}")
            continue
        response = (client.post(path, json={"question": "how many pairs?"})
                    if "POST" in methods and "GET" not in methods
                    else client.get(path))
        if response.status_code >= 500:
            failures.append(f"{path} -> {response.status_code}")

    assert not missing, (
        "a declared route has no sample value here, so it is not exercised: "
        f"{missing}")
    assert not failures, f"routes answering 5xx: {failures}"


def test_an_absent_pair_is_a_client_error_not_a_server_one():
    if not (ATLAS / "comparison.json").exists():
        pytest.skip("no published bundle to serve")
    response = _app().test_client().get("/api/pair/does_not_exist")
    assert response.status_code == 404, response.status_code
