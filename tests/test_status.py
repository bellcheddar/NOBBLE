"""The header status must not claim more than it knows.

"complete" describes the campaign that was published, not the project. The
droplet cannot see the Studio's queues, so build_atlas records what was
outstanding when the slice was built. Without that the panel reads COMPLETE
while three campaigns are still to run, and a visitor reasonably concludes
the science is finished.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.app import data


def _atlas(tmp_path: Path, outstanding: list | None) -> Path:
    scores = [{"pair_id": "p1", "tier": "benchmark", "delta_iptm": 0.3,
               "bridging_seeds_with_bridge": 2}]
    (tmp_path / "scores.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in scores))
    (tmp_path / "results.jsonl").write_text(
        json.dumps({"job_id": "j1", "pair_id": "p1", "structure": "x.cif"}) + "\n")
    (tmp_path / "queue.jsonl").write_text(
        json.dumps({"job_id": "j1", "pair_id": "p1"}) + "\n")
    (tmp_path / "state.jsonl").write_text(
        json.dumps({"job_id": "j1", "status": "done"}) + "\n")
    (tmp_path / "validation.json").write_text(json.dumps({"layers": {}}))
    atlas = {"campaign": tmp_path.name, "files": {}}
    if outstanding is not None:
        atlas["outstanding"] = outstanding
    (tmp_path / "ATLAS.json").write_text(json.dumps(atlas))
    return tmp_path


def test_complete_says_so_when_other_campaigns_are_outstanding(tmp_path):
    data.configure(str(_atlas(tmp_path, [
        {"campaign": "campaign_x", "jobs_done": 0, "jobs_total": 2360},
        {"campaign": "design_y", "jobs_done": 0, "jobs_total": 240},
    ])))
    try:
        status = data.site_status()
        assert status["health"] == "complete"
        assert "2 more" in status["note"], status["note"]
        assert len(status["outstanding"]) == 2
    finally:
        data.configure()


def test_a_genuinely_finished_project_does_not_grow_a_caveat(tmp_path):
    """The note should only widen when there is something to report."""
    data.configure(str(_atlas(tmp_path, [])))
    try:
        status = data.site_status()
        assert status["health"] == "complete"
        assert "more" not in status["note"]
        assert status["outstanding"] == []
    finally:
        data.configure()


def test_an_older_atlas_without_the_field_still_works(tmp_path):
    """Slices built before this existed carry no `outstanding` key."""
    data.configure(str(_atlas(tmp_path, None)))
    try:
        status = data.site_status()
        assert status["health"] == "complete"
        assert status["outstanding"] == []
    finally:
        data.configure()
