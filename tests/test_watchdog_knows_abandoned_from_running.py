"""A `running` record with no runner is a stopped campaign, not a working one (F216).

The watchdog exists to tell those apart, and for a job killed with its runner
it answered "ok" until this. That is the worst of the three possible wrong
answers, because a watchdog answering ok is the only evidence anything checked.
"""
from __future__ import annotations

import json
import time

import pytest

from nobble.execute import watchdog


def _campaign(tmp_path, *, tier=2, started_ago=120.0):
    campaign = tmp_path / "campaign_killed"
    campaign.mkdir()
    (campaign / "queue.jsonl").write_text(json.dumps(
        {"job_id": "a__ternary__seed1", "tokens": 500}) + "\n")
    suffix = "" if tier == 1 else f"_tier{tier}"
    (campaign / f"queue{suffix}.jsonl").write_text(json.dumps(
        {"job_id": "a__ternary__seed1", "tokens": 500}) + "\n")
    (campaign / f"state{suffix}.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"job_id": "done__seed1", "status": "done", "seconds": 300, "tokens": 500},
        {"job_id": "a__ternary__seed1", "status": "running",
         "started_at": time.time() - started_ago},
    ]) + "\n")
    return campaign


def test_a_killed_job_reads_as_abandoned_not_running(tmp_path):
    report = watchdog.stall_report(_campaign(tmp_path), tier=2, alive=False)
    assert [job["job_id"] for job in report["abandoned"]] == ["a__ternary__seed1"]
    assert report["stalled"] == []
    assert report["overdue"] == []


def test_the_same_record_with_a_live_runner_is_just_running(tmp_path):
    """The control: the record is identical, only the machine differs."""
    report = watchdog.stall_report(_campaign(tmp_path), tier=2, alive=True)
    assert report["abandoned"] == []
    assert [job["job_id"] for job in report["running"]] == ["a__ternary__seed1"]


def test_abandoned_is_asked_before_the_timings(tmp_path):
    """A job 'running' for a week with no runner is abandoned, never stalled.

    How long an abandoned job has been running is the age of a record nobody
    closed, not a fact about the job. Calling it stalled sends whoever reads
    it looking for a process to kill.
    """
    campaign = _campaign(tmp_path, started_ago=7 * 24 * 3600)
    report = watchdog.stall_report(campaign, tier=2, alive=False)
    assert report["abandoned"], report
    assert report["stalled"] == [], "an abandoned job was reported as stalled"


def test_unknowable_liveness_does_not_raise_an_alarm(tmp_path):
    """None is read as True. 'I cannot tell' must not become 'nothing runs'."""
    report = watchdog.stall_report(_campaign(tmp_path), tier=2, alive=None)
    assert report["abandoned"] == []


def test_the_default_is_not_a_probe(tmp_path):
    """Existing callers describe the state they mean, not the live machine."""
    report = watchdog.stall_report(_campaign(tmp_path), tier=2)
    assert report["runner_alive"] is True
    assert report["abandoned"] == []


def test_abandoned_exits_three(tmp_path, monkeypatch, capsys):
    """Its own code, because the remedy differs: start a runner, not kill one."""
    monkeypatch.chdir(tmp_path.parent)
    monkeypatch.setattr(watchdog, "runner_alive", lambda tier=1: False)
    code = watchdog.main(["--campaign", str(_campaign(tmp_path)), "--tier", "2"])
    assert code == 3
    out = capsys.readouterr().out
    assert "ABANDONED" in out
    assert "Start the runner" in out


def test_a_live_runner_for_another_tier_does_not_count(tmp_path, monkeypatch):
    """tools/tier2.sh produces exactly this state on every chain run.

    A tier-2 refinement in flight while tier 1 sits abandoned is real, so
    liveness has to be read per tier or the busier tier masks the other.
    """
    listing = "4242 caffeinate -dimsu python -m nobble.execute.runner --tier 2\n"

    class Found:
        returncode = 0
        stdout = listing

    monkeypatch.setattr(watchdog.subprocess, "run", lambda *a, **k: Found())
    assert watchdog.runner_alive(tier=2) is True
    assert watchdog.runner_alive(tier=1) is False


def test_a_runner_without_the_flag_is_tier_one(tmp_path, monkeypatch):
    class Found:
        returncode = 0
        stdout = "99 caffeinate -dimsu python -m nobble.execute.runner\n"

    monkeypatch.setattr(watchdog.subprocess, "run", lambda *a, **k: Found())
    assert watchdog.runner_alive(tier=1) is True
    assert watchdog.runner_alive(tier=2) is False


def test_no_match_is_an_answer_and_a_broken_probe_is_not(monkeypatch):
    """pgrep exits 1 for no match, which is False; worse is unknowable."""
    class NoMatch:
        returncode = 1
        stdout = ""

    class Broken:
        returncode = 2
        stdout = ""

    monkeypatch.setattr(watchdog.subprocess, "run", lambda *a, **k: NoMatch())
    assert watchdog.runner_alive() is False

    monkeypatch.setattr(watchdog.subprocess, "run", lambda *a, **k: Broken())
    assert watchdog.runner_alive() is None


def test_a_missing_pgrep_is_unknowable_rather_than_empty(monkeypatch):
    def explode(*args, **kwargs):
        raise FileNotFoundError("pgrep")

    monkeypatch.setattr(watchdog.subprocess, "run", explode)
    assert watchdog.runner_alive() is None


def test_the_watchdog_does_not_match_itself(monkeypatch):
    """This module's own command line must not read as a runner."""
    class Found:
        returncode = 0
        stdout = "7 python -m nobble.execute.watchdog --tier 2\n"

    monkeypatch.setattr(watchdog.subprocess, "run", lambda *a, **k: Found())
    assert watchdog.runner_alive(tier=2) is False


def test_tier2_arms_its_own_watchdog():
    """The chain's watchdog polls tier 1, so by the time it reaches tier 2 it
    is watching a finished queue and answering ok indefinitely (F112)."""
    from pathlib import Path
    script = (Path(__file__).resolve().parents[1] / "tools" / "tier2.sh").read_text()
    assert "nobble.execute.watchdog" in script, "tier2.sh arms no watchdog"
    assert "--tier 2" in script
    assert script.index("nobble.execute.watchdog") < script.index("nobble.execute.runner"), (
        "the watchdog is armed after the refinement it is supposed to watch"
    )


def test_tier2_keeps_one_exit_trap():
    """A second `trap ... EXIT` replaces the first rather than adding to it,
    which would have dropped the mktemp cleanup the moment the watchdog's
    trap was registered."""
    from pathlib import Path
    script = (Path(__file__).resolve().parents[1] / "tools" / "tier2.sh").read_text()
    registrations = [line for line in script.splitlines()
                     if line.strip().startswith("trap ")]
    assert len(registrations) == 1, (
        f"tier2.sh registers more than one trap: {registrations}")
    assert 'rm -f "$SELECT_LOG"' in script
    assert 'kill "$WATCHDOG_PID"' in script
