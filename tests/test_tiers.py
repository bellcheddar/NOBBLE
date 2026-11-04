"""Sampling tiers must never share a minimum (spec 1.2).

Delta-ipTM is a difference of two minima over seeds, and a minimum is not
robust to sample count: drawing more diffusion samples can push a minimum
down but never up. Tier 1 draws one diffusion sample, tier 2 draws
twenty-five. So pooling tier-2 ternary records into the tier-1 ternary
minimum, while the binary arm stays at tier 1, drags the ternary minimum
down on sample count alone and reports it as the glue weakening the
interface.

That failure is silent. Nothing raises, no value goes out of range, and the
number stays plausible. These tests exist because the only way to notice it
is to construct it deliberately.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.execute.runner import tier_files
from nobble.score import metrics


def _job(job_id: str, complex_type: str, iptm: float, tier_setting=None,
         seed: int = 1) -> dict:
    record = {
        "job_id": job_id,
        "seed": seed,
        "pair_id": "pairA",
        "construct": "CRBN_CULT",
        "e3_gene": "CRBN",
        "peptide_id": "p1",
        "complex_type": complex_type,
        "conditioning": "unconstrained",
        "tier": "benchmark",
        "status": "done",
        "confidence": {
            "pair_chains_iptm": {"0": {"1": iptm}, "1": {"0": iptm}},
            "iptm": iptm,
        },
    }
    if tier_setting is not None:
        record["tier_setting"] = tier_setting
    return record


def _write(path: Path, jobs: list[dict]) -> None:
    path.write_text("".join(json.dumps(job) + "\n" for job in jobs))


def test_tier2_records_do_not_enter_the_tier1_minimum(tmp_path):
    """The contamination case, built on purpose.

    The tier-2 ternary record carries a far lower ipTM, which is exactly what
    a deeper diffusion sample is expected to produce. If it reached the tier-1
    ternary minimum it would take delta_iptm negative.
    """
    results = tmp_path / "results.jsonl"
    _write(results, [
        _job("j1", "binary", 0.60),
        _job("j2", "ternary", 0.80),
        _job("j3__tier2", "ternary", 0.10, tier_setting=2),
    ])

    pairs = metrics.aggregate(results, sampling_tier=1)
    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.iptm_min_ternary == 0.80, "a tier-2 sample reached a tier-1 minimum"
    assert pair.delta_iptm == 0.20


def test_records_without_a_sampling_tier_are_treated_as_tier1(tmp_path):
    """Every result written before tier_setting existed is a tier-1 record.

    Defaulting the other way would silently empty the campaign that has
    already run.
    """
    results = tmp_path / "results.jsonl"
    _write(results, [_job("j1", "binary", 0.60), _job("j2", "ternary", 0.80)])

    pairs = metrics.aggregate(results, sampling_tier=1)
    assert len(pairs) == 1
    assert pairs[0].delta_iptm == 0.20


def test_asking_for_a_tier_with_no_records_returns_nothing_not_a_mixture(tmp_path):
    results = tmp_path / "results.jsonl"
    _write(results, [_job("j1", "binary", 0.60), _job("j2", "ternary", 0.80)])

    assert metrics.aggregate(results, sampling_tier=2) == []


def test_tier2_writes_to_its_own_three_files(tmp_path):
    """Tier 1 stays immutable: a tier-2 run cannot corrupt the measurement
    that selected it."""
    tier1 = tier_files(tmp_path, 1)
    tier2 = tier_files(tmp_path, 2)

    assert tier1["queue"].name == "queue.jsonl"
    assert tier1["results"].name == "results.jsonl"
    assert tier2["queue"].name == "queue_tier2.jsonl"
    assert tier2["results"].name == "results_tier2.jsonl"
    assert tier2["state"].name == "state_tier2.jsonl"
    for key in ("queue", "state", "results"):
        assert tier1[key] != tier2[key]


def test_scoring_reads_the_results_file_for_the_tier_it_was_asked_for(tmp_path):
    """Tier 2 must not be scored out of tier 1's results file.

    Before this, score_campaign opened results.jsonl unconditionally, so
    asking for tier 2 silently rescored tier 1 and wrote the answer over
    scores.jsonl.
    """
    from nobble.score.run import score_campaign

    _write(tmp_path / "results.jsonl", [_job("j1", "binary", 0.60)])

    out = score_campaign(tmp_path, with_plip=False, sampling_tier=2)
    assert out["status"].startswith("no results yet")
    assert out["sampling_tier"] == 2
    assert not (tmp_path / "scores_tier2.jsonl").exists()
    assert not (tmp_path / "scores.jsonl").exists(), "a tier-2 run wrote tier 1's scores"


def test_a_tier1_results_file_holding_only_tier2_rows_scores_nothing(tmp_path):
    """The filter is on the record, not only on the filename.

    `by_pair` feeds geometry and PLIP per job, so a stray tier-2 record in
    tier 1's file would reach a tier-1 number by that route even though the
    minima are partitioned.
    """
    from nobble.score.run import score_campaign

    _write(tmp_path / "results.jsonl", [
        _job("j1__tier2", "ternary", 0.10, tier_setting=2),
    ])

    out = score_campaign(tmp_path, with_plip=False, sampling_tier=1)
    assert out["status"] == "no tier-1 results yet"
    assert not (tmp_path / "scores.jsonl").exists()
