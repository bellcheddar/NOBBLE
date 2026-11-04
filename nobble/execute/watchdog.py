"""Tell a running campaign apart from a stalled one.

A campaign that has stopped looks exactly like a campaign that is working.
Both show a `running` record and a live process; progress tooling that counts
completed jobs reports "81/100 running" for either. F20 cost most of a night
to that ambiguity: the queue sat still for 3h45m while every check that asked
"is the process alive" answered yes.

Two signals, deliberately separated:

`overdue` compares a job against the slowest comparable job the same campaign
has already finished, scaled by token count because a 397-token job and a
1287-token job are not comparable. It is informational. Boltz timings vary and
a slow job is not a stalled one.

`stalled` is the one that matters, and it needs no tuning. The runner cannot
legitimately spend more than its timeout, times its retries, plus the grace it
allows a kill. A job still running past that bound is not slow: the runner has
lost control of it, which is precisely the state F20 left behind.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from nobble import paths
from nobble.execute import runner

TERMINAL = ("done",)


def _last_record_per_job(state_path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    if not state_path.exists():
        return records
    for line in state_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "job_id" in row:
            records[row["job_id"]] = row
    return records


def _tokens_by_job(queue_path: Path) -> dict[str, int]:
    tokens: dict[str, int] = {}
    if not queue_path.exists():
        return tokens
    for line in queue_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "job_id" in row and row.get("tokens"):
            tokens[row["job_id"]] = int(row["tokens"])
    return tokens


def hard_bound_seconds(tier: int = 1) -> float:
    """The longest one job can legitimately occupy the runner.

    Derived from the runner rather than configured, so it cannot drift away
    from the behaviour it describes: the timeout, once per attempt, plus the
    window a kill is given, plus a configured margin.
    """
    settings = runner.settings_from_config(tier=tier)
    attempts = runner.RETRIES + 1
    margin = float(paths.thresholds()["watchdog"]["stall_margin_minutes"]) * 60.0
    return settings["job_timeout_seconds"] * attempts + runner.KILL_GRACE_SECONDS + margin


def stall_report(campaign: Path, tier: int = 1, now: float | None = None) -> dict:
    """What is running in this campaign, and whether any of it has stopped."""
    now = time.time() if now is None else now
    files = runner.tier_files(campaign, tier=tier)
    state = Path(files["state"])
    queue = Path(files["queue"])

    report = {
        "campaign": campaign.name,
        "running": [],
        "overdue": [],
        "stalled": [],
        "hard_bound_seconds": round(hard_bound_seconds(tier), 1),
    }
    records = _last_record_per_job(state)
    if not records:
        return report

    tokens = _tokens_by_job(queue)

    # The yardstick is the campaign's own completed work, per token, so a
    # large job is not called overdue for being large.
    #
    # Median, not max, for the same reason runner.throughput() sizes the
    # budget on a median: one pathological job must not set the scale. The
    # first version of this used max and was immediately blunted by a single
    # job whose recorded time included an attempt killed by hand, which
    # nearly doubled the threshold for every job after it.
    rates = sorted(
        float(row["seconds"]) / float(row["tokens"])
        for row in records.values()
        if row.get("status") in TERMINAL and row.get("seconds") and row.get("tokens")
    )
    typical_rate = rates[len(rates) // 2] if rates else None
    multiple = float(paths.thresholds()["watchdog"]["overdue_multiple"])
    bound = hard_bound_seconds(tier)

    for job_id, row in sorted(records.items()):
        if row.get("status") in TERMINAL or str(row.get("status", "")).startswith("failed"):
            continue
        started = row.get("started_at")
        if started is None:
            continue
        elapsed = now - float(started)
        entry = {
            "job_id": job_id,
            "elapsed_seconds": round(elapsed, 1),
            "tokens": tokens.get(job_id),
        }
        report["running"].append(entry)

        if elapsed > bound:
            entry = dict(entry, bound_seconds=round(bound, 1))
            report["stalled"].append(entry)
        elif typical_rate is not None and tokens.get(job_id):
            expected = typical_rate * tokens[job_id]
            if elapsed > multiple * expected:
                report["overdue"].append(
                    dict(entry, expected_seconds=round(expected, 1))
                )
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    import glob

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", default=None)
    parser.add_argument("--tier", type=int, default=1)
    args = parser.parse_args(argv)

    targets = (
        [Path(args.campaign)] if args.campaign
        else [Path(p) for p in sorted(glob.glob("campaigns/*"))]
    )
    worst = 0
    for campaign in targets:
        if not (campaign / "queue.jsonl").exists():
            continue
        report = stall_report(campaign, tier=args.tier)
        if not report["running"]:
            continue
        for job in report["stalled"]:
            print(f"   STALLED  {campaign.name} {job['job_id']} "
                  f"{job['elapsed_seconds'] / 3600:.2f} h, past the "
                  f"{job['bound_seconds'] / 3600:.2f} h the runner allows")
            worst = 2
        for job in report["overdue"]:
            print(f"   overdue  {campaign.name} {job['job_id']} "
                  f"{job['elapsed_seconds'] / 60:.1f} min against "
                  f"{job['expected_seconds'] / 60:.1f} min expected")
            worst = max(worst, 1)
        if not report["stalled"] and not report["overdue"]:
            print(f"   ok       {campaign.name}: "
                  f"{len(report['running'])} running, none overdue")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
