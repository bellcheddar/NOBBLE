"""What the app does with input it did not expect.

It is a public site, so a 500 shows a reader a broken page and a traversal
that resolves shows them a file. Probed with unknown ids, encoded `../`,
an over-long parameter and a GET on a POST endpoint: nothing raises, nothing
5xxs, and both `/structure/<job>.cif` and `/crystal/<pdb>.cif` refuse a
traversal by matching the identifier against the campaign's own records
rather than by sanitising a path.

One thing disagreed with itself. `/api/pair/<id>` returned 404 for a pair the
campaign has not scored and `/api/pair/<id>/structures` returned 200 with
`{"pair_id": "nope", "crystal": null, "structures": []}`, which asserts that
the pair exists and produced nothing.

Those are two different states, and this project distinguishes them
everywhere else: a pair whose jobs all failed is a real outcome with a real
empty list, and the Pose viewer would have rendered one for a pair that does
not exist. The sub-resource now uses the same existence check as its parent
(F122).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="module")
def client():
    from nobble.app import create_app

    return create_app().test_client()


def _a_scored_pair(client) -> str | None:
    rows = client.get("/api/pairs").get_json() or []
    return rows[0]["pair_id"] if rows else None


@pytest.mark.parametrize("path", [
    "/api/pair/does_not_exist",
    "/api/pair/does_not_exist/structures",
    "/structure/nope.cif",
    "/structure/..%2F..%2F..%2Fetc%2Fpasswd.cif",
    "/crystal/ZZZZ.cif",
    "/crystal/..%2Fpasswd.cif",
])
def test_an_unknown_identifier_is_a_404(client, path):
    assert client.get(path).status_code == 404, path


@pytest.mark.parametrize("path", [
    "/", "/campaign", "/pose", "/interactions", "/delta", "/benchmark",
    "/design", "/about", "/healthz",
    "/design?parent=nonexistent",
    "/design?parent=" + "x" * 4000,
    "/campaign?weights=garbage",
    "/api/pairs", "/api/state", "/api/status", "/api/schema", "/api/components",
])
def test_nothing_returns_a_server_error(client, path):
    assert client.get(path).status_code < 500, path


def test_the_two_pair_endpoints_agree_about_what_exists(client):
    """The inconsistency F122 fixed. A sub-resource of a thing that does not
    exist cannot be 200."""
    for unknown in ("nope", "bench99_NOT_REAL", "x"):
        bare = client.get(f"/api/pair/{unknown}").status_code
        subresource = client.get(f"/api/pair/{unknown}/structures").status_code
        assert bare == subresource == 404, (unknown, bare, subresource)


def test_a_real_pair_still_answers_on_both(client):
    """The control: the fix must not 404 a pair that is there."""
    pair = _a_scored_pair(client)
    if pair is None:
        pytest.skip("no scored pair on this checkout")
    assert client.get(f"/api/pair/{pair}").status_code == 200
    payload = client.get(f"/api/pair/{pair}/structures").get_json()
    assert payload["pair_id"] == pair
    assert isinstance(payload["structures"], list)


def test_an_empty_structure_list_still_means_something(client):
    """The state the 200 used to be confused with. A scored pair may have no
    completed structure, and that must stay distinguishable from a pair that
    does not exist: 200 with an empty list against 404."""
    rows = client.get("/api/pairs").get_json() or []
    without = [row["pair_id"] for row in rows
               if not row.get("structure") and row.get("pair_id")]
    if not without:
        pytest.skip("every scored pair has a structure")
    payload = client.get(f"/api/pair/{without[0]}/structures")
    assert payload.status_code == 200
    assert payload.get_json()["pair_id"] == without[0]


def test_the_sub_resource_judges_existence_on_results_not_scores():
    """My first fix used the sibling's check, `data.scores()`, and the
    tier-2 catalogue tests caught it within a minute.

    Scoring runs after the campaign, so for the whole length of a run every
    completed pair is in `results.jsonl` and none are in `scores.jsonl`.
    Using the sibling's check here 404s every pair while the campaign is
    still going, which is exactly when the viewer is used. The two endpoints
    should agree about a pair that is in neither, and must not agree about
    one that is only in results.
    """
    import re

    source = (ROOT / "nobble" / "app" / "routes.py").read_text()
    block = source[source.index("def api_pair_structures"):]
    # The docstring contains the word "returned", so splitting the raw text
    # on "return" cuts inside it. Blanked first, which is the same trap
    # F119's test fell into.
    block = re.sub(r'"""(?:.|\n)*?"""', "", block, count=1)
    before_return = block.split("return")[0]
    assert "data.results()" in before_return, (
        "the structures endpoint no longer judges existence on results"
    )
    assert "_pair_or_404" not in before_return, (
        "it is back to using the scores-based check, which 404s every pair "
        "for the length of a campaign"
    )


def test_a_pair_with_results_and_no_scores_still_serves(tmp_path):
    """The state a running campaign is in, start to finish.

    Run in a subprocess with `create_app(<dir>)`, the way
    `test_tier2_catalogue` does it. Calling `data.configure()` in-process
    does not pin a bare directory: it falls back to the most recent real
    campaign, so the first version of this asserted 200 and got a 404 from
    a campaign where p1 does not exist.
    """
    import json
    import subprocess
    import textwrap

    row = {"job_id": "p1__ternary__conditioned__seed1", "pair_id": "p1",
           "complex_type": "ternary", "conditioning": "conditioned", "seed": 1,
           "status": "done", "structure": "x.cif"}
    (tmp_path / "results.jsonl").write_text(json.dumps(row) + "\n")
    (tmp_path / "scores.jsonl").write_text("")

    script = textwrap.dedent(f"""
        import json, sys
        sys.path.insert(0, {str(ROOT)!r})
        from nobble.app import create_app
        client = create_app({str(tmp_path)!r}).test_client()
        print(json.dumps({{
            "known": client.get("/api/pair/p1/structures").status_code,
            "absent": client.get("/api/pair/absent/structures").status_code,
        }}))
    """)
    result = subprocess.run([sys.executable, "-c", script],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr[-400:]
    codes = json.loads(result.stdout.strip().splitlines()[-1])
    assert codes == {"known": 200, "absent": 404}, codes
