"""The gate that refuses to spend a stage should say what the stage costs.

`tools/preflight.py` opens with "before spending days of GPU on it", and
every caller's refusal is phrased in exactly those terms: `run_design.sh`
prints "refusing to spend 240 jobs on it", `run_chain.sh` "refusing to start
a 52-hour run on it". The report named the jobs and never the hours, so the
one quantity the refusal is about had to be looked up somewhere else, with
whatever rate the reader had to hand.

That is not hypothetical. Tier B went on record at 38.9 hours, priced before
the throughput bands were remeasured on the main campaign; preflight prices
the same queue at 32.8. And F225 is me pricing a tier-2 remainder at a flat
median and understating it by three hours, which is F45, which is written
down in `thresholds.toml` beside `token_bands`.

Reporting only: the projection must never decide `ok`. Gate G1 is decided by
`budget.gate_g1` against `max_compute_hours`, and a preflight that refused on
cost would be a second, quieter gate with no decision recorded against it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import preflight as preflight_module  # noqa: E402

RECEPTOR = "ACDEFGHIKLMNPQRSTVWY" * 3
PEPTIDE = "PVDVEALGLHDYCDI"


def _campaign(root: Path, *, jobs: int = 4, tokens: int | None = 150) -> Path:
    """A campaign preflight accepts, with a real a3m for its receptor."""
    campaign = root / "queued_stage"
    (campaign / "yaml").mkdir(parents=True)
    a3m = root / "receptor.a3m"
    a3m.write_text(f">query\n{RECEPTOR}\n>hit1\n{RECEPTOR}\n")

    rows = []
    for index in range(jobs):
        name = f"pairX__ternary__unconstrained__seed{index + 1}"
        path = campaign / "yaml" / f"{name}.yaml"
        path.write_text(
            "version: 1\n"
            "sequences:\n"
            "- protein:\n"
            "    id: A\n"
            f"    sequence: {RECEPTOR}\n"
            f"    msa: {a3m}\n"
            "- protein:\n"
            "    id: P\n"
            f"    sequence: {PEPTIDE}\n"
            "    msa: empty\n"
        )
        row = {"job_id": name, "pair_id": "pairX", "complex_type": "ternary",
               "yaml": str(path)}
        if tokens is not None:
            row["tokens"] = tokens
        rows.append(row)
    (campaign / "queue.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n")
    return campaign


def test_the_report_prices_the_queue(tmp_path):
    report = preflight_module.preflight(_campaign(tmp_path))
    assert report["ok"], report["errors"]
    cost = report["cost"]
    assert cost is not None, report
    assert cost["projected_hours"] > 0, cost
    assert cost["priced_jobs"] == 4
    assert cost["unpriced_jobs"] == 0
    assert "token band" in cost["basis"], cost["basis"]


def test_a_bigger_queue_is_priced_higher(tmp_path):
    small = preflight_module.preflight(_campaign(tmp_path / "a", jobs=4))
    large = preflight_module.preflight(_campaign(tmp_path / "b", jobs=40))
    assert large["cost"]["projected_hours"] > small["cost"]["projected_hours"]


def test_the_projection_never_decides_ok(tmp_path):
    """A cost is reported; a refusal is still only ever about errors."""
    campaign = _campaign(tmp_path, jobs=4000)
    report = preflight_module.preflight(campaign)
    assert report["cost"]["projected_hours"] > 24, report["cost"]
    assert report["ok"], (
        "preflight refused on cost, which makes it a second compute gate "
        "with no decision recorded against it")
    assert report["errors"] == []


def test_a_queue_with_no_token_counts_is_unpriced_not_free(tmp_path):
    """Charging nothing is the one answer that is certainly wrong."""
    report = preflight_module.preflight(_campaign(tmp_path, tokens=None))
    assert report["ok"], report["errors"]
    assert report["cost"] is None, (
        "a queue with no token counts was given a cost, so the projection "
        "invented a number from nothing")


def test_an_unpriced_job_is_counted_rather_than_dropped(tmp_path):
    campaign = _campaign(tmp_path, jobs=4)
    rows = [json.loads(line) for line
            in (campaign / "queue.jsonl").read_text().splitlines() if line.strip()]
    rows[0].pop("tokens")
    (campaign / "queue.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n")

    cost = preflight_module.preflight(campaign)["cost"]
    assert cost["priced_jobs"] == 3
    assert cost["unpriced_jobs"] == 1, cost
