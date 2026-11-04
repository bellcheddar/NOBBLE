"""Refined poses must reach the viewer.

Tier 2's only product is a better set of coordinates, and the structure
catalogue is the one place they can be read. It drew from results.jsonl
alone, so a refinement run would have produced hours of compute that
nothing could open.

Run in a subprocess. The app keeps its campaign and its file cache in
module globals, and the suite has several tests that reconfigure both;
in-process this test passed alone, passed against every other file
pairwise, and failed only in the full run. The product code was correct
throughout, which is the point: a test that depends on accumulated global
state is measuring the suite, not the code. A fresh interpreter removes
the variable rather than hiding it.
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _catalogue(tmp_path: Path, with_tier2: bool) -> dict:
    base = {"job_id": "p1__ternary__unconstrained__seed1", "pair_id": "p1",
            "complex_type": "ternary", "conditioning": "unconstrained",
            "seed": 1, "structure": "x.cif"}
    (tmp_path / "results.jsonl").write_text(json.dumps(base) + "\n")
    (tmp_path / "scores.jsonl").write_text("")
    if with_tier2:
        refined = dict(base, job_id=base["job_id"] + "__tier2", tier_setting=2)
        (tmp_path / "results_tier2.jsonl").write_text(json.dumps(refined) + "\n")

    script = textwrap.dedent(f"""
        import json, sys
        sys.path.insert(0, {str(ROOT)!r})
        from nobble.app import create_app
        app = create_app({str(tmp_path)!r})
        payload = app.test_client().get("/api/pair/p1/structures").get_json()
        print(json.dumps(payload))
    """)
    result = subprocess.run([sys.executable, "-c", script],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_refined_poses_reach_the_structure_catalogue(tmp_path):
    """Marked rather than merged: tier 1 and tier 2 were sampled
    differently and are not interchangeable (D-NOB-032)."""
    payload = _catalogue(tmp_path, with_tier2=True)

    tiers = sorted(s["sampling_tier"] for s in payload["structures"])
    assert tiers == [1, 2], payload["structures"]
    labels = {s["sampling_tier"]: s["label"] for s in payload["structures"]}
    assert labels[2] == "refined"
    assert labels[1] == "tier 1"


def test_a_campaign_without_tier_two_is_unaffected(tmp_path):
    """The normal state. An absent results_tier2.jsonl must not error or
    add anything."""
    payload = _catalogue(tmp_path, with_tier2=False)

    assert len(payload["structures"]) == 1
    assert payload["structures"][0]["sampling_tier"] == 1
