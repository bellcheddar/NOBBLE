"""Resumable Boltz queue runner (spec Phase 2).

Three properties the spec treats as load-bearing, and the reasons:

- **Resumable and idempotent.** Multi-day MPS runs hit OOM and NaN diffusion
  steps. A queue that cannot resume mid-run is unusable, so every job appends a
  checkpoint to state.jsonl before and after it runs, and a restart skips
  anything already recorded as done. The file is append-only: a crash during a
  write loses at most the record being written, never the history.
- **One job never blocks the campaign.** A failure retries once, then is
  recorded with `status = failed:<reason>` and the queue moves on. That is the
  fallback ladder, and it matters most for the jobs most likely to fail: the
  1,229-token DCAF15 member is both the largest and the one an OOM would hit.
- **Throughput is measured, not assumed.** Each job records wall-clock seconds
  and its token count, and the benchmark writes seconds-per-token to
  data/throughput.json. Everything downstream sizes itself from that file
  rather than from the spec's estimate (spec 1.2).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from nobble import paths

TERMINAL_STATUSES = ("done",)
RETRIES = 1


@dataclass
class JobOutcome:
    job_id: str
    status: str
    seconds: float
    tokens: int
    output_dir: str | None
    confidence: dict | None
    affinity: dict | None
    structure: str | None
    attempts: int
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "seconds": round(self.seconds, 2),
            "tokens": self.tokens,
            "seconds_per_token": round(self.seconds / self.tokens, 4) if self.tokens else None,
            "output_dir": self.output_dir,
            "confidence": self.confidence,
            "affinity": self.affinity,
            "structure": self.structure,
            "attempts": self.attempts,
            "detail": self.detail,
        }


def boltz_environment() -> dict:
    settings = paths.tuning().get("env", {})
    environment = dict(os.environ, **{key: str(value) for key, value in settings.items()})
    # Boltz writes its weights and CCD cache here; keep it on the default so the
    # already-downloaded 7.6 GB is reused rather than fetched again.
    environment.setdefault("BOLTZ_CACHE", str(Path.home() / ".boltz"))
    return environment


def completed(state_path: Path) -> dict[str, dict]:
    """Job identifiers already finished, from the append-only checkpoint log."""
    done: dict[str, dict] = {}
    if not state_path.exists():
        return done
    for line in state_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            # A torn final line from a kill mid-write: ignore it and re-run that job.
            continue
        if record.get("status") in TERMINAL_STATUSES:
            done[record["job_id"]] = record
    return done


def _model_rank(path: Path) -> int | None:
    """Boltz's rank from a filename, or None if it carries no rank.

    The ranks are not zero-padded, so sorting the names lexically puts
    `_model_10` ahead of `_model_3`. With one diffusion sample there is only
    `_model_0` and no ordering to get wrong; with twenty-five, a batch whose
    first ranks failed to write would have been scored on rank 10 while
    ranks 3 to 9 sat beside it (F99).
    """
    marker = "_model_"
    if marker not in path.stem:
        return None
    tail = path.stem.rsplit(marker, 1)[1]
    return int(tail) if tail.isdigit() else None


def _best_structure(output_dir: Path, stem: str) -> Path | None:
    """The highest-ranked predicted structure Boltz wrote for this job.

    Preference order: this job's own files over any others in the tree, mmCIF
    over PDB, a ranked model over an unranked one, and then the best rank
    numerically. Ties break on the name so the choice is reproducible rather
    than dependent on directory order.
    """
    candidates = [path for suffix in (".cif", ".pdb")
                  for path in output_dir.rglob(f"*{suffix}")]
    if not candidates:
        return None

    def key(path: Path) -> tuple:
        rank = _model_rank(path)
        return (
            0 if path.stem.startswith(stem) else 1,
            0 if path.suffix == ".cif" else 1,
            0 if rank is not None else 1,
            rank if rank is not None else 0,
            str(path),
        )

    return min(candidates, key=key)


def _read_outputs(
    output_dir: Path, stem: str
) -> tuple[dict | None, dict | None, str | None, str | None]:
    """Locate Boltz's confidence JSON, affinity JSON and predicted structure.

    Boltz writes one structure and one confidence JSON per diffusion sample,
    named by rank rather than by sample index: `argsort(confidence_score,
    descending)` puts the best model at `_model_0`, so `<stem>_model_0.cif`
    is the pick of the batch and `confidence_<stem>_model_0.json` holds that
    model's metrics.

    Tier 1 runs one diffusion sample, so each pattern matches exactly one
    file and any pick is the right one. Tier 2 runs twenty-five, and then the
    confidence has to come from the model whose structure is being scored.
    This used to take the first `confidence_*.json` that `rglob` yielded, in
    directory order, while the structure loop asked for `_model_0`
    explicitly: on the ten tier-2 jobs the recorded ipTM would have belonged
    to an arbitrary one of twenty-five poses and the bridge, PLIP and RMSD
    measurements to another, with the arbitrary choice depending on APFS
    directory order rather than on anything reproducible. Delta-ipTM is the
    tier-2 headline, so the two numbers it differences have to describe the
    same structure (F99).

    The confidence is therefore derived from the structure's own filename
    rather than searched for, which makes a mismatch unrepresentable instead
    of merely unlikely. A fourth return value carries the reason when
    something is missing, because "no confidence JSON written" and "a
    structure whose confidence JSON is missing" are different failures and
    the retry records whichever is true.
    """
    structure = _best_structure(output_dir, stem)

    confidence = None
    reason = None
    if structure is not None:
        beside = structure.parent / f"confidence_{structure.stem}.json"
        if beside.exists():
            try:
                confidence = json.loads(beside.read_text())
            except Exception as problem:            # noqa: BLE001
                reason = f"{beside.name} did not parse: {type(problem).__name__}"
        else:
            reason = f"{structure.name} written but {beside.name} is missing"
    else:
        # No structure to match against. One confidence JSON is the tier-1
        # shape and unambiguous; several with no structure is not something
        # to guess at, on F81's precedent.
        candidates = sorted(output_dir.rglob("confidence_*.json"))
        if len(candidates) == 1:
            try:
                confidence = json.loads(candidates[0].read_text())
            except Exception as problem:            # noqa: BLE001
                reason = f"{candidates[0].name} did not parse: {type(problem).__name__}"
            reason = reason or "no structure written, confidence read alone"
        elif candidates:
            reason = (f"no structure written and {len(candidates)} confidence "
                      "JSONs, so none can be matched to a pose")
        else:
            reason = "no confidence JSON written"

    affinity = None
    # Affinity is written once per job rather than once per sample.
    for path in sorted(output_dir.rglob("affinity_*.json")):
        try:
            affinity = json.loads(path.read_text())
        except Exception:                           # noqa: BLE001
            affinity = None
        break

    return confidence, affinity, (str(structure) if structure else None), reason


# How long to keep trying to reap a child that has already been SIGKILLed,
# and how many separate kills to send inside that window.
KILL_GRACE_SECONDS = 120
KILL_ATTEMPTS = 4


def _run_boltz(command: list[str], env: dict, timeout: float):
    """Run one Boltz job and always return within timeout + KILL_GRACE_SECONDS.

    subprocess.run(timeout=...) is not safe for this. When it times out it
    sends SIGKILL and then calls wait() with no bound of its own. A Boltz job
    wedged in an uninterruptible Metal wait (ps STAT "U") cannot be reaped, so
    that wait() never returns and the whole campaign stalls with no log line
    and no failed job: the queue simply stops. Observed on
    corr06_RBM39_DCAF15__ternary__unconstrained__seed1, which held the
    corrected campaign for 3h45m *after* its own 5400s timeout had already
    fired. A second SIGKILL from outside the process cleared it (F20).

    Returns (status, returncode, stdout, stderr) with status one of:
      "ok"          the process exited on its own, returncode is meaningful
      "timeout"     it overran and was killed and reaped; worth retrying
      "unkillable"  it overran and survived SIGKILL for the whole grace
                    window, so it is abandoned rather than waited on. It may
                    still hold GPU memory, which is why this one is not
                    retried.
    """
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return "ok", process.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        pass

    # Kill repeatedly rather than once: the signal that finally landed on the
    # observed hang was a later one, not the first.
    for _ in range(KILL_ATTEMPTS):
        process.kill()
        try:
            stdout, stderr = process.communicate(
                timeout=KILL_GRACE_SECONDS / KILL_ATTEMPTS
            )
            return "timeout", process.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            continue
    return "unkillable", None, "", ""


def run_job(job: dict, campaign: Path, settings: dict) -> JobOutcome:
    """Run one Boltz inference, with one retry on failure."""
    job_id = job["job_id"]
    output_dir = campaign / "outputs" / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    command = [
        str(paths.BOLTZ_CLI), "predict", job["yaml"],
        "--out_dir", str(output_dir),
        "--recycling_steps", str(settings["recycles"]),
        "--diffusion_samples", str(settings["diffusion_samples"]),
        "--seed", str(job["seed"]),
        "--output_format", "mmcif",
        "--accelerator", "gpu" if settings["device"] == "mps" else "cpu",
        "--num_workers", "0",
        "--override",
        # Optional kernels are a CUDA path: disabling them explicitly keeps the
        # run deterministic rather than depending on an import succeeding.
        "--no_kernels",
    ]
    if settings["potentials"]:
        command.append("--use_potentials")

    # The queue may carry a budget computed from this pair's measured tier-1
    # cost; otherwise the tier's configured cap applies. See tier2.job_budget.
    budget = float(job.get("timeout_seconds") or settings["job_timeout_seconds"])

    attempts = 0
    detail = ""
    started = time.monotonic()
    while attempts <= RETRIES:
        # The budget is per job, not per attempt. It used to be per attempt,
        # so a job that timed out spent the cap twice: RETRIES=1 meant two
        # full attempts, and re-running an identical command against an
        # identical input after a timeout is the one retry guaranteed to end
        # the same way, because nothing about it changed. The project's own
        # fallback ladder says retry once *with a fix*. Sizing the retry from
        # what is left makes that automatic: a job that crashes after two
        # minutes retries with the rest of its budget, and a job that
        # exhausts the budget has nothing to retry with (F100).
        remaining = budget - (time.monotonic() - started)
        if remaining <= 0:
            detail = detail or f"budget of {budget:.0f}s spent"
            break
        attempts += 1
        status, returncode, stdout, stderr = _run_boltz(
            command, boltz_environment(), remaining,
        )
        if status == "timeout":
            detail = (f"timeout after {remaining:.0f}s, with a total budget of "
                      f"{budget:.0f}s")
            # Not retried. A timeout consumed the whole of what it was given,
            # so the remaining-budget rule below would stop the retry anyway,
            # but saying it here states the reason rather than leaving it to
            # be inferred from the clock: an identical command on an identical
            # input, having been killed for taking too long, will be killed
            # again. The "unkillable" branch already breaks for this reason.
            # A crash is different and still retries, with what is left.
            break
        if status == "unkillable":
            detail = (
                f"timeout after {remaining:.0f}s of a {budget:.0f}s budget, then "
                f"survived SIGKILL for {KILL_GRACE_SECONDS}s: abandoned so the "
                "queue can continue. The orphan may still hold GPU memory"
            )
            break
        if returncode == 0:
            seconds = time.monotonic() - started
            confidence, affinity, structure, reason = _read_outputs(
                output_dir, job_id)
            if confidence is None:
                detail = f"exit 0 but {reason}"
                continue
            return JobOutcome(
                job_id=job_id, status="done", seconds=seconds, tokens=job["tokens"],
                output_dir=str(output_dir), confidence=confidence, affinity=affinity,
                structure=structure, attempts=attempts,
            )
        tail = (stderr or stdout or "").strip().splitlines()
        detail = " | ".join(tail[-3:])[:400] if tail else f"exit {returncode}"

    return JobOutcome(
        job_id=job_id, status=f"failed: {detail[:200]}",
        seconds=time.monotonic() - started, tokens=job["tokens"],
        output_dir=str(output_dir), confidence=None, affinity=None, structure=None,
        attempts=attempts, detail=detail,
    )


def settings_from_config(tier: int = 1, job_timeout_seconds: int | None = None) -> dict:
    campaign_settings = paths.tuning()["campaign"]
    compute = paths.tuning()["compute"]
    # The timeout was a default argument, which put the number that decides
    # when a job is abandoned in a signature rather than in config. Still
    # overridable, because a test needs to.
    if job_timeout_seconds is None:
        job_timeout_seconds = int(campaign_settings["job_timeout_seconds"])
    if tier == 1:
        return {
            "recycles": int(campaign_settings["tier1_recycles"]),
            "diffusion_samples": int(campaign_settings["tier1_diffusion_samples"]),
            "potentials": bool(campaign_settings["tier1_potentials"]),
            "device": compute["model_device"],
            "job_timeout_seconds": job_timeout_seconds,
        }
    return {
        "recycles": int(campaign_settings["tier2_recycles"]),
        "diffusion_samples": int(campaign_settings["tier2_diffusion_samples"]),
        "potentials": bool(campaign_settings["tier2_potentials"]),
        "device": compute["model_device"],
        # From config, not a literal here. See tier2_timeout_multiple's
        # comment in tuning.toml: the factor is a guess until tier 2 runs.
        "job_timeout_seconds": job_timeout_seconds * int(
            campaign_settings["tier2_timeout_multiple"]),
    }


def free_disk_gb(path: Path | None = None) -> float:
    """Free space on the project volume, in GB."""
    import shutil

    return shutil.disk_usage(path or paths.ROOT).free / 1e9


def disk_gate(path: Path | None = None) -> dict:
    """Gate G5. Open when free space falls below the configured floor.

    The threshold has been in `thresholds.toml` as `min_free_disk_gb` since
    the first phase and nothing read it, so the gate existed on paper only.
    A campaign that fills the volume does not fail cleanly: Boltz writes a
    truncated output, the job is recorded done, and the damage is found at
    scoring time with the compute already spent.
    """
    floor = float(paths.thresholds().get("gates", {}).get("min_free_disk_gb", 0)
                  or paths.tuning().get("gates", {}).get("min_free_disk_gb", 0))
    free = free_disk_gb(path)
    return {
        "free_gb": round(free, 1),
        "floor_gb": floor,
        "open": bool(floor) and free < floor,
    }


def tier_files(campaign: Path, tier: int = 1) -> dict:
    """Queue, state and results paths for a sampling tier.

    Tier 2 gets its own three files rather than appending to tier 1's. Two
    reasons, and the second is the load-bearing one. Keeping tier 1's results
    immutable means a tier-2 run can never corrupt the measurement that
    selected it. And `iptm_min` is a minimum over seeds, which is not robust
    to sample count: adding diffusion samples can only push a minimum down,
    never up. Pooling 25-sample ternary records into the same minimum as
    1-sample binary records would bias `delta_iptm` downwards for exactly the
    pairs that were refined, and it would look like the glue weakening the
    interface rather than the arithmetic of an order statistic.
    """
    suffix = "" if tier == 1 else f"_tier{tier}"
    return {
        "queue": campaign / f"queue{suffix}.jsonl",
        "state": campaign / f"state{suffix}.jsonl",
        "results": campaign / f"results{suffix}.jsonl",
    }


def run_campaign(campaign: Path, limit: int | None = None, tier: int = 1) -> dict:
    # Resolved here so every path written into state.jsonl and results.jsonl is
    # absolute, whatever form the caller used. It used to follow the caller:
    # the benchmark campaign was started with an absolute path and the
    # corrected one with "campaigns/corrected_...", so the two campaigns'
    # records disagreed about what a structure path is. Any consumer running
    # from somewhere other than the project root then reads one and fails on
    # the other, which is exactly what happened to cif2plip (F32). Fixing the
    # consumer closed that instance; this closes the class.
    campaign = Path(campaign).resolve()
    files = tier_files(campaign, tier)
    queue_path = files["queue"]
    state_path = files["state"]
    results_path = files["results"]
    if not queue_path.exists():
        return {"campaign": str(campaign), "tier": tier, "attempted": 0,
                "succeeded": 0, "failed": 0, "total_seconds": 0.0,
                "status": f"no queue at {queue_path.name}"}
    settings = settings_from_config(tier)

    # Strict: the queue is written once, before anything runs, and nothing
    # appends to it. A line that will not parse is a damaged input, not a
    # torn tail, and skipping it would run 2,359 of 2,360 jobs in silence
    # (F111).
    jobs = paths.read_jsonl(queue_path)
    done = completed(state_path)
    pending = [job for job in jobs if job["job_id"] not in done]
    if limit:
        pending = pending[:limit]

    print(f"queue: {len(jobs)} jobs, {len(done)} already done, running {len(pending)}",
          flush=True)

    outcomes = []
    for index, job in enumerate(pending, start=1):
        # Gate G5, checked per job rather than once at the start: a 52-hour
        # run fills a volume gradually, and the point of a gate is to stop
        # before the damage, not to report it afterwards.
        gate = disk_gate(campaign)
        if gate["open"]:
            print(f"GATE G5: {gate['free_gb']} GB free, below the "
                  f"{gate['floor_gb']} GB floor. Stopping with "
                  f"{len(pending) - index + 1} job(s) unrun; rerun to resume.",
                  file=sys.stderr, flush=True)
            break

        print(f"[{index}/{len(pending)}] {job['job_id']} ({job['tokens']} tokens)",
              flush=True)
        with state_path.open("a") as state:
            state.write(json.dumps({"job_id": job["job_id"], "status": "running",
                                    "started_at": time.time()}) + "\n")
        outcome = run_job(job, campaign, settings)
        record = outcome.to_dict()
        with state_path.open("a") as state:
            state.write(json.dumps(record) + "\n")
        if outcome.status == "done":
            with results_path.open("a") as results:
                results.write(json.dumps(
                    {**job, **record, "tier_setting": tier}) + "\n")
        outcomes.append(outcome)
        print(f"    {outcome.status} in {outcome.seconds:.1f}s "
              f"({record['seconds_per_token']} s/token)", flush=True)

    succeeded = [item for item in outcomes if item.status == "done"]
    return {
        "campaign": str(campaign),
        "tier": tier,
        "attempted": len(outcomes),
        "succeeded": len(succeeded),
        "failed": len(outcomes) - len(succeeded),
        "total_seconds": sum(item.seconds for item in outcomes),
    }


def token_band(tokens: int, edges: list[int]) -> tuple[int, int]:
    """The (low, high) band a job of this size falls in, high exclusive.

    A high of 0 means the open-ended top band. One band for all job sizes
    is what a single median seconds-per-token rate amounts to, and that
    rate is not constant: measured on the main campaign it runs from 0.21
    to 0.66 s/token across these bands, because attention cost does not
    grow linearly with sequence length (F61).
    """
    low = 0
    for edge in edges:
        if tokens < edge:
            return (low, edge)
        low = edge
    return (low, 0)


def throughput_bands(timed: list[dict]) -> list[dict]:
    """Median seconds per token within each band, and how many jobs set it.

    The job count travels with the rate because a band measured once is not
    the same evidence as a band measured fifty times, and a projection that
    cannot tell the difference states a number it has no basis for.
    """
    edges = [int(edge) for edge in
             paths.thresholds()["throughput"]["token_bands"]]
    grouped: dict[tuple[int, int], list[float]] = {}
    for item in timed:
        band = token_band(int(item["tokens"]), edges)
        grouped.setdefault(band, []).append(item["seconds"] / item["tokens"])
    out = []
    for (low, high), observed in sorted(grouped.items()):
        observed.sort()
        out.append({
            "min_tokens": low,
            "max_tokens": high or None,
            "jobs": len(observed),
            "median_seconds_per_token": round(observed[len(observed) // 2], 4),
        })
    return out


def write_throughput(campaign: Path) -> dict:
    """Measure seconds per token and size the campaign from it (spec 1.2)."""
    results_path = campaign / "results.jsonl"
    if not results_path.exists():
        return {"status": "no results yet"}

    records = paths.read_jsonl(results_path, tolerate_torn=True)
    timed = [item for item in records if item.get("seconds") and item.get("tokens")]
    if not timed:
        return {"status": "no timed results"}

    rates = sorted(item["seconds"] / item["tokens"] for item in timed)
    median_rate = rates[len(rates) // 2]
    by_band = throughput_bands(timed)
    budget_hours = float(paths.tuning()["campaign"]["wall_clock_budget_hours"])

    # Size the campaign from the measured rate at a representative token count,
    # using the median rather than the mean so one pathological job does not set
    # the budget.
    representative_tokens = sorted(item["tokens"] for item in timed)[len(timed) // 2]
    seconds_per_job = median_rate * representative_tokens
    from nobble.curate.manifest import jobs_per_pair

    per_pair = jobs_per_pair()
    affordable_jobs = int((budget_hours * 3600) / seconds_per_job) if seconds_per_job else 0
    affordable_pairs = affordable_jobs // per_pair

    # Which arms the timed jobs came from. A job carrying no tier is counted
    # as unlabelled rather than silently folded into one of the arms.
    measured_on: dict[str, int] = {}
    for item in timed:
        measured_on[str(item.get("tier") or "unlabelled")] = (
            measured_on.get(str(item.get("tier") or "unlabelled"), 0) + 1
        )
    measured_on = dict(sorted(measured_on.items(), key=lambda kv: (-kv[1], kv[0])))
    described = ", ".join(f"{count} {arm} job(s)"
                          for arm, count in measured_on.items())

    payload = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "campaign": campaign.name,
        "jobs_timed": len(timed),
        "median_seconds_per_token": round(median_rate, 4),
        "seconds_per_token_by_band": by_band,
        "mean_seconds_per_token": round(sum(rates) / len(rates), 4),
        "fastest_seconds_per_token": round(rates[0], 4),
        "slowest_seconds_per_token": round(rates[-1], 4),
        "representative_tokens": representative_tokens,
        "seconds_per_representative_job": round(seconds_per_job, 1),
        "jobs_per_pair": per_pair,
        "wall_clock_budget_hours": budget_hours,
        "affordable_jobs": affordable_jobs,
        "affordable_pairs": affordable_pairs,
        "device": paths.tuning()["compute"]["model_device"],
        # What was actually measured, counted rather than asserted. This read
        # "Measured on the benchmark panel" unconditionally, which was true
        # for the first hundred jobs of this campaign and false from job 100,
        # where the Sievers arm begins: at 120 timed jobs the measurement
        # spanned two arms whose per-job cost differs by a factor of twenty
        # six, and the note still named one of them. It is published in the
        # atlas, and a label that describes the wrong data is the failure
        # F102 and F101 were both instances of (F104).
        "measured_on": measured_on,
        "note": (
            f"Measured on {described}. affordable_pairs is what the "
            "manifest generator sizes itself from (spec 1.2), replacing the "
            "spec's 200-250 estimate."
        ),
    }
    paths.THROUGHPUT.write_text(json.dumps(payload, indent=2))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a NOBBLE campaign queue")
    parser.add_argument("--campaign", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--tier", type=int, default=1)
    parser.add_argument("--throughput", action="store_true",
                        help="write data/throughput.json from the results so far")
    args = parser.parse_args()

    campaign = args.campaign
    if campaign is None:
        from nobble.execute.campaign import latest
        campaign = latest("benchmark")
    if campaign is None:
        print("no campaign found: assemble one first", file=sys.stderr)
        return 2

    if args.throughput:
        print(json.dumps(write_throughput(Path(campaign)), indent=2))
        return 0

    summary = run_campaign(Path(campaign), limit=args.limit, tier=args.tier)
    print(json.dumps(summary, indent=2))
    print(json.dumps(write_throughput(Path(campaign)), indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
