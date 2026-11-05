#!/usr/bin/env python3
"""Phase 0 hardware probe. Writes config/hardware.toml and config/tuning.toml.

Nothing in NOBBLE hard-codes a core count, a memory figure or a device: every
setting below is derived from what this probe measures on the host it runs on.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"


def sysctl(key: str) -> str | None:
    try:
        out = subprocess.run(["sysctl", "-n", key], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except Exception:
        return None


def gpu_cores() -> int | None:
    try:
        out = subprocess.run(
            ["system_profiler", "-json", "SPDisplaysDataType"],
            capture_output=True, text=True, timeout=60,
        )
        data = json.loads(out.stdout)
        for card in data.get("SPDisplaysDataType", []):
            for key in ("sppci_cores", "spdisplays_ncores"):
                if key in card:
                    return int(str(card[key]).split()[0])
    except Exception:
        pass
    return None


def free_disk_gb(path: Path) -> float:
    """Free space in GB, decimal, which is what the G5 gate compares against.

    This divided by 1024**3 and returned the answer under a `_gb` name, so
    it was gibibytes labelled gigabytes: 7.4 per cent low, and 37 GB out at
    the volume this runs on. `nobble.execute.runner.free_disk_gb` already
    divided by 1e9, and the gate's floor in `thresholds.toml` is 50 GB as
    CLAUDE.md states it, so the gate was right and this was the one out of
    step. Two functions of the same name in one project disagreeing about
    their unit (F179).

    Nothing decides on this one: it is recorded in `config/hardware.toml`
    and printed by the probe. The divergence still mattered, because the
    probe's line is where a reader goes to find out how much room there is,
    and a figure that disagrees with the gate by 37 GB is worse than no
    figure.
    """
    usage = shutil.disk_usage(path)
    return round(usage.free / 1e9, 1)


def mps_state() -> dict:
    """Probe MPS through the BoltzMaker env, which owns the torch build boltz uses."""
    candidates = [
        ROOT.parent / "BoltzMaker" / ".pixi" / "envs" / "default" / "bin" / "python",
        ROOT.parent / "BINMAN" / ".pixi" / "envs" / "default" / "bin" / "python",
        Path(sys.executable),
    ]
    probe = (
        "import torch,json;"
        "print('NOBBLE_MPS='+json.dumps({"
        "'torch': torch.__version__,"
        "'mps_available': bool(torch.backends.mps.is_available()),"
        "'mps_built': bool(torch.backends.mps.is_built())}))"
    )
    env = dict(os.environ, KMP_DUPLICATE_LIB_OK="TRUE", PYTORCH_ENABLE_MPS_FALLBACK="1")
    for python in candidates:
        if not python.exists():
            continue
        try:
            out = subprocess.run(
                [str(python), "-c", probe], capture_output=True, text=True, timeout=180, env=env
            )
            for line in out.stdout.splitlines():
                if line.startswith("NOBBLE_MPS="):
                    state = json.loads(line.split("=", 1)[1])
                    state["python"] = str(python)
                    return state
        except Exception:
            continue
    return {"torch": None, "mps_available": False, "mps_built": False, "python": None}


def toml_dump(data: dict) -> str:
    """Minimal TOML writer: two levels, scalars and flat lists only."""
    def fmt(value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if value is None:
            return '""'
        if isinstance(value, list):
            return "[" + ", ".join(fmt(v) for v in value) + "]"
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'

    lines: list[str] = []
    for key, value in data.items():
        if not isinstance(value, dict):
            lines.append(f"{key} = {fmt(value)}")
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"\n[{key}]")
            for sub_key, sub_value in value.items():
                lines.append(f"{sub_key} = {fmt(sub_value)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    CONFIG.mkdir(parents=True, exist_ok=True)

    perf = int(sysctl("hw.perflevel0.physicalcpu") or 0)
    eff = int(sysctl("hw.perflevel1.physicalcpu") or 0)
    logical = int(sysctl("hw.logicalcpu") or 0)
    memsize = int(sysctl("hw.memsize") or 0)
    memory_gb = round(memsize / 1024 ** 3, 1)
    mps = mps_state()

    hardware = {
        "probed_at": subprocess.run(
            ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True
        ).stdout.strip(),
        "chip": sysctl("machdep.cpu.brand_string"),
        "cpu": {
            "performance_cores": perf,
            "efficiency_cores": eff,
            "logical_cores": logical,
        },
        "memory": {"total_gb": memory_gb, "total_bytes": memsize},
        "gpu": {"cores": gpu_cores() or 0},
        "disk": {"free_gb_project_volume": free_disk_gb(ROOT)},
        "accelerator": mps,
    }

    # Derived settings, per the Mac Studio performance rules.
    cpu_workers = max(2, perf - 2)
    device = "mps" if mps.get("mps_available") else "cpu"
    headroom = 24

    tuning = {
        "derived_from": "config/hardware.toml",
        "note": "Generated by tools/hwprobe.py. Do not hand-edit: re-run the probe.",
        "compute": {
            "cpu_workers": cpu_workers,
            "io_workers": 16,
            "model_device": device,
            "model_instances": 1,
            "memory_headroom_gb": headroom,
            "usable_memory_gb": round(max(0.0, memory_gb - headroom), 1),
        },
        "env": {
            "PYTORCH_ENABLE_MPS_FALLBACK": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "OMP_NUM_THREADS": str(cpu_workers),
            "KMP_DUPLICATE_LIB_OK": "TRUE",
        },
        "campaign": {
            # Spec 1.1/1.2. Budgets, not measurements: Phase 2 overwrites the
            # throughput figure in data/throughput.json from a real timing run.
            "token_cap_tier1": 400,
            "token_cap_exceptions": ["VHL_VCB", "DCAF15_DDB1_DDA1"],
            # Lifted from 96 on 2026-11-05. Marc's instruction: the Studio
            # is his own machine, the compute is free, and 96 was an
            # arbitrary figure from the spec rather than a measurement of
            # anything. 240 covers everything planned (48 spent, ~10 h of
            # tier 1 left, 38.9 h of Tier B at full depth with scrambles)
            # with headroom, and still trips on genuine runaway: tier 2's
            # full decile is priced at 120 to 904 h, and the upper end is a
            # month of wall-clock, which is a decision rather than a budget
            # line (D-NOB-073).
            "max_compute_hours": 240,
            "wall_clock_budget_hours": 48,
            "seeds": 5,
            # Tier B's depth, its own key: see config/tuning.toml.
            "tier_b_seeds": 5,
            # Longest one tier-1 job may run before it is killed. Tier 2
            # is given four times this (runner.settings_from_config).
            "job_timeout_seconds": 5400,
            "tier1_recycles": 3,
            "tier1_diffusion_samples": 1,
            "tier1_potentials": False,
            "tier2_recycles": 10,
            "tier2_diffusion_samples": 25,
            "tier2_potentials": True,
        },
        "gates": {"min_free_disk_gb": 50},
    }

    (CONFIG / "hardware.toml").write_text(toml_dump(hardware))
    (CONFIG / "tuning.toml").write_text(toml_dump(tuning))

    print(f"chip            : {hardware['chip']}")
    print(f"cores           : {perf} performance, {eff} efficiency, {logical} logical")
    print(f"memory          : {memory_gb} GB")
    print(f"gpu cores       : {hardware['gpu']['cores']}")
    print(f"free disk       : {hardware['disk']['free_gb_project_volume']} GB")
    print(f"accelerator     : {device} (torch {mps.get('torch')})")
    print(f"cpu_workers     : {cpu_workers}")
    print("wrote config/hardware.toml and config/tuning.toml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
