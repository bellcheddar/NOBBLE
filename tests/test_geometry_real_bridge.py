"""The bridge filter's success path, against a real predicted ternary.

A mutation sweep found that `result.found = True` in
geometry.score_structure could become `False` and the whole suite still
passed. Everything that consumes a bridge was tested with the geometry
stubbed, so the one path that decides whether a bridge exists at all had
no test exercising it.

This runs the real filter on a real predicted structure. It needs gemmi,
FreeSASA, BINMAN's pipeline package and a scored campaign, and skips when
any is absent, which is the same arrangement as the other
data-dependent tests here.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _a_bridged_job():
    """A ternary job from a pair whose seeds were scored as bridging."""
    for scores_path in sorted(glob.glob(str(ROOT / "campaigns" / "*" / "scores.jsonl"))):
        campaign = Path(scores_path).parent
        results = campaign / "results.jsonl"
        if not results.exists():
            continue
        bridged_pairs = {
            row["pair_id"] for row in
            (json.loads(line) for line in open(scores_path) if line.strip())
            if (row.get("bridging_seeds_with_bridge") or 0) > 0
        }
        if not bridged_pairs:
            continue
        for line in open(results):
            if not line.strip():
                continue
            job = json.loads(line)
            if (job.get("pair_id") in bridged_pairs
                    and job.get("complex_type") == "ternary"
                    and job.get("structure")
                    and Path(job["structure"]).exists()):
                return job
    return None


@pytest.fixture(scope="module")
def bridged_job():
    job = _a_bridged_job()
    if job is None:
        pytest.skip("no scored campaign with a bridged ternary on this checkout")
    return job


def _score(job):
    from nobble.score import geometry

    try:
        return geometry.score_structure(job)
    except ImportError as problem:          # gemmi, freesasa or BINMAN absent
        pytest.skip(f"geometry stack not importable here: {problem}")


def test_a_real_ternary_is_found_to_bridge(bridged_job):
    """The assertion the mutation sweep showed nothing was making."""
    result = _score(bridged_job)
    assert result.found is True, (
        f"{bridged_job['job_id']} was scored as bridging when the campaign "
        f"ran, and the filter now rejects it: {result.reject_reason}"
    )
    assert result.reject_reason is None


def test_a_found_bridge_carries_the_numbers_that_depend_on_it(bridged_job):
    """found=True with null measurements would be worse than a rejection,
    because every consumer treats found as permission to read these."""
    result = _score(bridged_job)
    assert result.dsasa_total is not None and result.dsasa_total > 0
    assert result.dsasa_receptor is not None and result.dsasa_receptor > 0
    assert result.dsasa_peptide is not None and result.dsasa_peptide > 0
    assert result.contacts_receptor and result.contacts_peptide
    assert result.heavy_atoms and result.heavy_atoms > 0


def test_the_percentile_is_a_percentile(bridged_job):
    """Against the atlas distribution, so it has to be in range and carry
    the basis it was measured against."""
    result = _score(bridged_job)
    if result.bridge_percentile is None:
        pytest.skip("BINMAN atlas not readable here, so no reference distribution")
    assert 0.0 <= result.bridge_percentile <= 100.0
    assert result.percentile_basis and "observed bridges" in result.percentile_basis


def test_the_binary_arm_is_refused_rather_than_measured(bridged_job):
    """A binary complex has no ligand, so there is no bridge to measure.
    Refusing with a reason is the right answer and is not the same as
    finding no bridge."""
    binary = dict(bridged_job, complex_type="binary")
    result = _score(binary)
    assert result.found is False
    assert result.reject_reason == "binary_complex_has_no_bridge"
    assert result.notes, "the refusal carries no explanation"


def test_a_missing_structure_is_refused_with_its_own_reason(bridged_job):
    """Distinct from no_bridge_found, which is what F33 turns on."""
    from nobble.score import geometry

    result = geometry.score_structure(
        dict(bridged_job, structure="/nonexistent/x.cif")
    )
    assert result.found is False
    assert result.reject_reason == "structure_missing"
    assert result.reject_reason in geometry.MEASUREMENT_FAILURES
