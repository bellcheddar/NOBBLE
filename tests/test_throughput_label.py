"""The throughput note has to describe the jobs it was measured on.

It read "Measured on the benchmark panel" unconditionally. That was true for
the first hundred jobs of the main campaign and false from job 100, where
the Sievers arm begins. The two arms differ in per-job cost by a factor of
twenty six, a Sievers binary being 136 tokens in 35 seconds against a DCAF15
ternary at 1,223 tokens in 915, so which arm a rate was measured on is the
difference between a projection that holds and one that does not. F45 was
that mistake made across campaigns; this is the same mistake made across
arms within one.

The note is published in the atlas, where `throughput` is excluded from the
drift check, so nothing would have caught the label going stale. Counted now
rather than asserted (F104).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.execute.runner import write_throughput  # noqa: E402


def _campaign(tmp_path: Path, rows: list[dict]) -> Path:
    campaign = tmp_path / "campaign_label"
    campaign.mkdir()
    (campaign / "results.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n")
    return campaign


def test_the_note_counts_the_arms_it_measured(tmp_path, monkeypatch):
    from nobble import paths

    monkeypatch.setattr(paths, "THROUGHPUT", tmp_path / "throughput.json")
    campaign = _campaign(tmp_path, [
        {"job_id": f"b{i}", "tier": "benchmark", "seconds": 100.0, "tokens": 200}
        for i in range(3)
    ] + [
        {"job_id": f"s{i}", "tier": "sievers_zf", "seconds": 35.0, "tokens": 136}
        for i in range(7)
    ])

    payload = write_throughput(campaign)
    assert payload["measured_on"] == {"sievers_zf": 7, "benchmark": 3}
    assert "7 sievers_zf job(s)" in payload["note"]
    assert "3 benchmark job(s)" in payload["note"]
    assert "Measured on the benchmark panel" not in payload["note"], (
        "the note asserts an arm again instead of counting them"
    )


def test_a_job_with_no_arm_is_counted_as_unlabelled(tmp_path, monkeypatch):
    """Not folded into one of the arms, which would be the same mistake in
    miniature."""
    from nobble import paths

    monkeypatch.setattr(paths, "THROUGHPUT", tmp_path / "throughput.json")
    campaign = _campaign(tmp_path, [
        {"job_id": "a", "seconds": 50.0, "tokens": 100},
        {"job_id": "b", "tier": "benchmark", "seconds": 50.0, "tokens": 100},
    ])
    payload = write_throughput(campaign)
    assert payload["measured_on"] == {"benchmark": 1, "unlabelled": 1}


def test_the_arms_are_ordered_by_how_much_they_contributed(tmp_path, monkeypatch):
    """So the note leads with the arm the rate mostly came from."""
    from nobble import paths

    monkeypatch.setattr(paths, "THROUGHPUT", tmp_path / "throughput.json")
    campaign = _campaign(tmp_path, [
        {"job_id": f"s{i}", "tier": "sievers_zf", "seconds": 35.0, "tokens": 136}
        for i in range(9)
    ] + [{"job_id": "b", "tier": "benchmark", "seconds": 900.0, "tokens": 1223}])
    payload = write_throughput(campaign)
    assert list(payload["measured_on"]) == ["sievers_zf", "benchmark"]
    assert payload["note"].index("sievers_zf") < payload["note"].index("benchmark")


def test_the_counts_add_up_to_the_timed_jobs(tmp_path, monkeypatch):
    from nobble import paths

    monkeypatch.setattr(paths, "THROUGHPUT", tmp_path / "throughput.json")
    campaign = _campaign(tmp_path, [
        {"job_id": "a", "tier": "benchmark", "seconds": 50.0, "tokens": 100},
        {"job_id": "b", "tier": "scramble", "seconds": 50.0, "tokens": 100},
        # Neither timed: no seconds, and no tokens.
        {"job_id": "c", "tier": "benchmark", "tokens": 100},
        {"job_id": "d", "tier": "benchmark", "seconds": 50.0},
    ])
    payload = write_throughput(campaign)
    assert sum(payload["measured_on"].values()) == payload["jobs_timed"] == 2


def test_the_live_campaign_note_names_the_arms_that_have_run():
    """On the real campaign, which is the case that went stale."""
    from nobble.execute.campaign import latest

    campaign = latest("campaign")
    if campaign is None or not (campaign / "results.jsonl").exists():
        pytest.skip("no campaign results")
    payload = write_throughput(campaign)
    if payload.get("status"):
        pytest.skip(payload["status"])
    assert payload["measured_on"], payload
    for arm, count in payload["measured_on"].items():
        assert f"{count} {arm} job(s)" in payload["note"], (arm, payload["note"])
