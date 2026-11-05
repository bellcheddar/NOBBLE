"""A route that 404s on purpose must not crash the page (F202).

`/api/pair/<pair_id>/structures` returns 404 for a pair the campaign has no
record of, and that is deliberate: F122 changed it from 200-with-an-empty-list
precisely because "a pair that produced nothing" and "a pair that does not
exist" are different states, and the viewer would otherwise render an empty
overlay for a pair that was never run.

`pose.html` fetched it and called `r.json()` regardless, so a 404 handed
`JSON.parse` the error page's HTML and the promise rejected unhandled.
Browser QC counts that as a console error and the seed overlay then fails
without saying anything.

Found by pointing the browser QC harness at a campaign-scale atlas for the
first time. It had only ever run against seven pairs, where every scored pair
has results rows and the 404 never fires.

Run under node rather than matched as source, which is F50's lesson: the
check should exercise the function, not its text.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "nobble" / "app" / "templates" / "pose.html"


def _fetch_catalogue(status: int, body: str) -> dict:
    """Run the template's own fetchCatalogue against a stubbed fetch."""
    if not shutil.which("node"):
        pytest.skip("node is not available")
    source = TEMPLATE.read_text()
    match = re.search(r"  function fetchCatalogue\(\) \{.*?\n  \}\n", source, re.S)
    assert match, "fetchCatalogue is no longer a named function in pose.html"

    script = (
        "let catalogue = null;\n"
        "const pairId = 'some_pair';\n"
        f"const stubStatus = {status};\n"
        f"const stubBody = {json.dumps(body)};\n"
        "globalThis.fetch = () => Promise.resolve({\n"
        "  ok: stubStatus >= 200 && stubStatus < 300,\n"
        "  status: stubStatus,\n"
        "  json: () => Promise.resolve(JSON.parse(stubBody)),\n"
        "});\n"
        + match.group(0)
        + "fetchCatalogue()\n"
        "  .then(d => { console.log(JSON.stringify(d)); })\n"
        "  .catch(e => { console.log(JSON.stringify({threw: String(e)})); });\n"
    )
    done = subprocess.run(["node", "-e", script], capture_output=True,
                          text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_a_404_yields_an_empty_catalogue_rather_than_a_rejection():
    """The defect: JSON.parse on the 404 page's HTML."""
    result = _fetch_catalogue(404, "<!doctype html><title>404</title>")
    assert "threw" not in result, (
        "a deliberate 404 still rejects, so the page logs an uncaught "
        f"SyntaxError: {result}"
    )
    assert result["structures"] == []
    assert result["crystal"] is None
    assert result["unavailable"] == 404, (
        "the empty catalogue does not record why it is empty, so a pair that "
        "produced nothing cannot be told from one the campaign never ran"
    )


def test_a_200_still_returns_the_payload():
    """The guard must not swallow the normal path."""
    payload = {"pair_id": "p", "crystal": "6H0F",
               "structures": [{"job_id": "j", "structure": "structures/j.cif"}]}
    result = _fetch_catalogue(200, json.dumps(payload))
    assert result == payload, result


def test_a_500_is_handled_too_rather_than_only_404():
    """The guard is on `r.ok`, not on the number 404, so any error works."""
    result = _fetch_catalogue(500, "<!doctype html><title>500</title>")
    assert "threw" not in result, result
    assert result["unavailable"] == 500


def test_the_guard_is_on_response_ok_and_not_on_a_status_literal():
    source = TEMPLATE.read_text()
    body = "\n".join(line for line in source.splitlines()
                     if not line.strip().startswith(("*", "/*")))
    assert "if (!r.ok)" in body, (
        "the guard tests a specific status rather than whether the response "
        "succeeded, so one error code would still crash the page"
    )
