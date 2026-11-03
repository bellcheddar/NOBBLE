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


def _read_outputs(output_dir: Path, stem: str) -> tuple[dict | None, dict | None, str | None]:
    """Locate Boltz's confidence JSON, affinity JSON and predicted structure."""
    confidence = affinity = None
    structure = None
    for path in output_dir.rglob("confidence_*.json"):
        try:
            confidence = json.loads(path.read_text())
        except Exception:                           # noqa: BLE001
            confidence = None
        break
    for path in output_dir.rglob("affinity_*.json"):
        try:
            affinity = json.loads(path.read_text())
        except Exception:                           # noqa: BLE001
            affinity = None
        break
    for pattern in ("*_model_0.cif", "*.cif", "*_model_0.pdb", "*.pdb"):
        found = sorted(output_dir.rglob(pattern))
        if found:
            structure = str(found[0])
            break
    return confidence, affinity, structure


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

    attempts = 0
    detail = ""
    started = time.monotonic()
    while attempts <= RETRIES:
        attempts += 1
        try:
            result = subprocess.run(
                command, capture_output=True, text=True,
                env=boltz_environment(), timeout=settings["job_timeout_seconds"],
            )
        except subprocess.TimeoutExpired:
            detail = f"timeout after {settings['job_timeout_seconds']}s"
            continue
        if result.returncode == 0:
            seconds = time.monotonic() - started
            confidence, affinity, structure = _read_outputs(output_dir, job_id)
            if confidence is None:
                detail = "exit 0 but no confidence JSON written"
                continue
            return JobOutcome(
                job_id=job_id, status="done", seconds=seconds, tokens=job["tokens"],
                output_dir=str(output_dir), confidence=confidence, affinity=affinity,
                structure=structure, attempts=attempts,
            )
        tail = (result.stderr or result.stdout or "").strip().splitlines()
        detail = " | ".join(tail[-3:])[:400] if tail else f"exit {result.returncode}"

    return JobOutcome(
        job_id=job_id, status=f"failed: {detail[:200]}",
        seconds=time.monotonic() - started, tokens=job["tokens"],
        output_dir=str(output_dir), confidence=None, affinity=None, structure=None,
        attempts=attempts, detail=detail,
    )


def settings_from_config(tier: int = 1, job_timeout_seconds: int = 5400) -> dict:
    campaign_settings = paths.tuning()["campaign"]
    compute = paths.tuning()["compute"]
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
        "job_timeout_seconds": job_timeout_seconds * 4,
    }


def run_campaign(campaign: Path, limit: int | None = None, tier: int = 1) -> dict:
    queue_path = campaign / "queue.jsonl"
    state_path = campaign / "state.jsonl"
    results_path = campaign / "results.jsonl"
    settings = settings_from_config(tier)

    jobs = [json.loads(line) for line in queue_path.read_text().splitlines() if line.strip()]
    done = completed(state_path)
    pending = [job for job in jobs if job["job_id"] not in done]
    if limit:
        pending = pending[:limit]

    print(f"queue: {len(jobs)} jobs, {len(done)} already done, running {len(pending)}",
          flush=True)

    outcomes = []
    for index, job in enumerate(pending, start=1):
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
                results.write(json.dumps({**job, **record}) + "\n")
        outcomes.append(outcome)
        print(f"    {outcome.status} in {outcome.seconds:.1f}s "
              f"({record['seconds_per_token']} s/token)", flush=True)

    succeeded = [item for item in outcomes if item.status == "done"]
    return {
        "campaign": str(campaign),
        "attempted": len(outcomes),
        "succeeded": len(succeeded),
        "failed": len(outcomes) - len(succeeded),
        "total_seconds": sum(item.seconds for item in outcomes),
    }


def write_throughput(campaign: Path) -> dict:
    """Measure seconds per token and size the campaign from it (spec 1.2)."""
    results_path = campaign / "results.jsonl"
    if not results_path.exists():
        return {"status": "no results yet"}

    records = [json.loads(line) for line in results_path.read_text().splitlines() if line.strip()]
    timed = [item for item in records if item.get("seconds") and item.get("tokens")]
    if not timed:
        return {"status": "no timed results"}

    rates = sorted(item["seconds"] / item["tokens"] for item in timed)
    median_rate = rates[len(rates) // 2]
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

    payload = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "campaign": campaign.name,
        "jobs_timed": len(timed),
        "median_seconds_per_token": round(median_rate, 4),
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
        "note": (
            "Measured on the benchmark panel. affordable_pairs is what the "
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
