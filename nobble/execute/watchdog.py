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

`abandoned` is the third state, and it is not a degree of the other two. A
`running` record whose runner is no longer on the machine describes a job that
is not running at all, and until the next runner starts and closes it out
(F214) that record is the newest thing the state file says about it. Reported
separately because the remedy is different: a stalled job needs the runner
killed, an abandoned one needs the runner started. Both were "ok" here until
F216, which is worse than either, since a watchdog answering ok is the only
evidence anything checked.

Exit codes, which the callers key on rather than grepping the printed verdict
(F54): 0 ok, 1 overdue, 2 stalled, 3 abandoned.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from nobble import paths
from nobble.numeric import finite
from nobble.execute import runner

TERMINAL = ("done",)

# The runner's own module path, which appears in its command line however it
# is wrapped: `caffeinate -dimsu <python> -m nobble.execute.runner --tier 2`
# matches, and this module (nobble.execute.watchdog) does not.
RUNNER_PATTERN = r"nobble\.execute\.runner"


def runner_alive(tier: int = 1) -> bool | None:
    """Is a runner for this tier on the machine? None if that is unknowable.

    None rather than False when pgrep is missing or errors, because "I cannot
    tell" and "nothing is running" must not collapse into the same answer: the
    second one raises an alarm and the first one must not.

    The tier is read off the command line. A tier-1 runner is one that carries
    no `--tier` above 1, since the runner defaults to tier 1 when the flag is
    absent, and a tier-2 refinement running while tier 1 sits abandoned is a
    real state that `tools/tier2.sh` produces on every chain run.
    """
    try:
        found = subprocess.run(["pgrep", "-fl", RUNNER_PATTERN],
                               capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    # pgrep exits 1 for "no match", which is an answer, and anything above
    # that is a failure to ask, which is not.
    if found.returncode > 1:
        return None
    for line in found.stdout.splitlines():
        if not re.search(RUNNER_PATTERN, line):
            continue
        flag = re.search(r"--tier\s+(\d+)", line)
        found_tier = int(flag.group(1)) if flag else 1
        if found_tier == tier:
            return True
    return False


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
        if "job_id" in row and finite(row.get("tokens")) and row["tokens"] > 0:
            tokens[row["job_id"]] = int(row["tokens"])
    return tokens


def hard_bound_seconds(tier: int = 1,
                       job_timeout_seconds: float | None = None) -> float:
    """The longest one job can legitimately occupy the runner.

    Derived from the runner rather than configured, so it cannot drift away
    from the behaviour it describes: the job's whole budget, plus the window
    a kill is given, plus a configured margin.

    **Once per job, not once per attempt.** It used to multiply by
    `RETRIES + 1`, which was right until F100 made the runner's budget cover
    the job rather than each attempt: `remaining = budget - elapsed`, so two
    attempts share one allowance and the runner cannot hold a job past
    `budget` plus the kill grace. Multiplying made the bound twice what the
    runner can allow, 11,520 seconds against 6,120 at tier 1 and 43,920
    against 22,320 at tier 2, so a genuinely hung runner went uncalled for an
    extra hour and a half, or six. The docstring said "once per attempt"
    throughout, and `test_the_bound_comes_from_the_runner_not_from_a_constant`
    asserted that arithmetic, so the stale model was pinned in two places and
    described in a third.

    `job_timeout_seconds` is the queue row's own override where it has one.
    The runner reads `job.get("timeout_seconds") or settings[...]`, so a bound
    taken from the tier default alone does not follow the runner either: the
    main campaign's tier-2 rows carry 39,000 against a tier default of 21,600.
    No queue today can be called stalled while legitimately running, because
    the doubling happened to cover the gap, but the two errors were
    cancelling rather than absent.
    """
    settings = runner.settings_from_config(tier=tier)
    budget = float(job_timeout_seconds or settings["job_timeout_seconds"])
    margin = float(paths.thresholds()["watchdog"]["stall_margin_minutes"]) * 60.0
    return budget + runner.KILL_GRACE_SECONDS + margin


def _timeouts_by_job(queue: Path) -> dict[str, float]:
    """Each job's own timeout override, where the queue row carries one."""
    out: dict[str, float] = {}
    if not queue.exists():
        return out
    for row in paths.read_jsonl(queue, tolerate_torn=True):
        value = row.get("timeout_seconds")
        if row.get("job_id") and value:
            out[row["job_id"]] = float(value)
    return out


def stall_report(campaign: Path, tier: int = 1, now: float | None = None,
                 alive: bool | None = True) -> dict:
    """What is running in this campaign, and whether any of it has stopped.

    `alive` says whether a runner for this tier is on the machine. It defaults
    to True rather than to a probe so that every existing caller and test
    keeps describing the state it means to describe; `main` probes and passes
    the answer in. None means it could not be determined, and is read the same
    way as True: an unanswerable question must not raise an alarm.
    """
    now = time.time() if now is None else now
    files = runner.tier_files(campaign, tier=tier)
    state = Path(files["state"])
    queue = Path(files["queue"])

    report = {
        "campaign": campaign.name,
        "running": [],
        "overdue": [],
        "stalled": [],
        "abandoned": [],
        "runner_alive": alive,
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
        if row.get("status") in TERMINAL
        and finite(row.get("seconds")) and finite(row.get("tokens"))
        and row["seconds"] > 0 and row["tokens"] > 0
    )
    # Taken by index from a sorted list, so one non-finite rate above would
    # leave the list unsorted and make this an arbitrary element rather than
    # the middle one. `finite` rather than truthiness, because a NaN is truthy
    # (F130).
    typical_rate = rates[len(rates) // 2] if rates else None

    # And the same rate banded by job size, because one rate is not a
    # property of the model.
    #
    # The comment above says the per-token yardstick means "a large job is
    # not called overdue for being large". A flat per-token rate does not
    # deliver that: seconds per token rises with size, so dividing by tokens
    # removes the linear part and leaves the rest. Measured on this
    # campaign's tier 2, the jobs at 400 tokens or more run at 2.953 s/token
    # against 2.237 for the rest, so a 1,223-token job is "expected" at
    # 2,736s and called overdue at 8,208s while a legitimate attempt takes
    # over 5,000s and its retry pushes the total past the line (F233).
    #
    # This is F45 and F225 a third time, and `thresholds.toml` already says
    # it in words beside `token_bands`, which `projected_hours` already uses.
    # Same bands, same config, so there is one definition of a job size in
    # the project rather than two.
    bands = [float(edge) for edge
             in paths.thresholds()["throughput"]["token_bands"]]

    def _band_of(token_count: float) -> int:
        for index, edge in enumerate(bands):
            if token_count < edge:
                return index
        return len(bands)

    banded: dict[int, list[float]] = {}
    for row in records.values():
        if row.get("status") not in TERMINAL:
            continue
        if not (finite(row.get("seconds")) and finite(row.get("tokens"))
                and row["seconds"] > 0 and row["tokens"] > 0):
            continue
        banded.setdefault(_band_of(float(row["tokens"])), []).append(
            float(row["seconds"]) / float(row["tokens"]))
    band_rate = {index: sorted(values)[len(values) // 2]
                 for index, values in banded.items()}

    # For tier 2 there is a better yardstick than any rate: the same job's
    # own tier-1 time, times the refinement factor this campaign measured.
    #
    # A tier-2 job is the same input at different settings, so its tier-1
    # time is a measurement of that exact molecule rather than of jobs its
    # size. On the job this was found with, bench06 at 1,223 tokens: tier 1
    # took 902s, the measured factor is 4.614, so the expectation is 4,162s
    # against an attempt that actually ran about 5,040s. The flat median said
    # 2,736s, which at the configured multiple put the overdue line at 8,208s
    # and would have flagged the job while its retry was still inside its
    # budget. The scaled line is 12,486s and does not (F233, F235).
    tier1_seconds: dict[str, float] = {}
    refinement_factor = None
    tier2_suffix = ""
    if tier == 2:
        from nobble.execute import budget as budget_module

        tier1_results = campaign / "results.jsonl"
        if tier1_results.exists():
            for row in paths.read_jsonl(tier1_results, tolerate_torn=True):
                if (row.get("status") in TERMINAL
                        and finite(row.get("seconds")) and row["seconds"] > 0):
                    tier1_seconds[row["job_id"]] = float(row["seconds"])
        refinement_factor = budget_module.measured_scaling(campaign)["factor"]
        # From budget, where the suffix is defined, rather than guessed here.
        # The first version of this looked for it on `runner` behind a
        # hasattr guard, which is always false, so the lookup below would
        # have used the tier-2 job id against tier-1 records, found nothing,
        # and silently fallen back to the rate it was replacing: the
        # correction would have reported itself as working and changed
        # nothing, which is F218's shape and F232's fourth instance.
        tier2_suffix = budget_module.TIER2_SUFFIX
    multiple = float(paths.thresholds()["watchdog"]["overdue_multiple"])
    timeouts = _timeouts_by_job(queue)
    default_bound = hard_bound_seconds(tier)

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

        # Asked before the timings, because how long an abandoned job has
        # been "running" is not a fact about the job: it is the age of a
        # record nobody closed. Calling such a job stalled would send whoever
        # read it looking for a runner to kill.
        if alive is False:
            report["abandoned"].append(entry)
        elif elapsed > (job_bound := hard_bound_seconds(
                tier, timeouts.get(job_id))):
            entry = dict(entry, bound_seconds=round(job_bound, 1))
            report["stalled"].append(entry)
        elif tokens.get(job_id):
            # The job's own band where this campaign has finished something
            # that size, and the campaign-wide median where it has not. Which
            # one was used is recorded, because a rate borrowed from a
            # different size is the thing being corrected here and a reader
            # comparing an overdue verdict against the clock needs to know
            # the yardstick was not measured at that size (F74).
            band = _band_of(float(tokens[job_id]))
            own_tier1 = (tier1_seconds.get(job_id.removesuffix(tier2_suffix))
                         if tier2_suffix else None)
            if refinement_factor and own_tier1:
                expected = own_tier1 * refinement_factor
                basis = (f"this job's own tier-1 time {own_tier1:.0f}s times "
                         f"the measured refinement factor {refinement_factor}")
            else:
                rate = band_rate.get(band)
                basis = f"median of this campaign's finished band-{band} jobs"
                if rate is None:
                    rate, basis = typical_rate, (
                        f"campaign-wide median: no finished job in band "
                        f"{band}, so no rate measured at this size")
                if rate is None:
                    continue
                expected = rate * tokens[job_id]
            if elapsed > multiple * expected:
                report["overdue"].append(
                    dict(entry, expected_seconds=round(expected, 1),
                         rate_basis=basis)
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
    # Asked once, outside the loop: it is a fact about the machine, not about
    # a campaign, and probing per campaign would answer the same question
    # once per directory in campaigns/.
    alive = runner_alive(args.tier)
    examined = 0
    with_running = 0
    for campaign in targets:
        if not (campaign / "queue.jsonl").exists():
            continue
        examined += 1
        report = stall_report(campaign, tier=args.tier, alive=alive)
        if not report["running"]:
            continue
        with_running += 1
        for job in report["abandoned"]:
            print(f"   ABANDONED {campaign.name} {job['job_id']}: the state "
                  f"file says running and no tier-{args.tier} runner is on "
                  f"this machine. Start the runner; it closes the record out "
                  f"and re-runs the job.")
            worst = max(worst, 3)
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
        if not report["stalled"] and not report["overdue"] \
                and not report["abandoned"]:
            print(f"   ok       {campaign.name}: "
                  f"{len(report['running'])} running, none overdue")

    # Said, rather than left as an empty section.
    #
    # With nothing running this printed nothing at all, so `tools/status.sh`
    # showed an empty "running jobs" heading whether no job was running or
    # the wrong tier had been asked. Those are not the same, and the second
    # was live: status.sh called this with no --tier while a tier-2 job had
    # been running for five hours, which is F216's own lesson, that liveness
    # is per tier, unapplied in the operator's one command. Silence meaning
    # two things is F232's shape.
    if not with_running:
        print(f"   ok       no job running at tier {args.tier} "
              f"across {examined} campaign(s) with a queue")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
