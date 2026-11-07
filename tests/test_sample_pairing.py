"""The confidence read must belong to the structure scored.

Boltz writes one structure and one confidence JSON per diffusion sample,
ranked so that `_model_0` is the best of the batch. Tier 1 runs a single
sample, so the directory holds one of each and any pick is correct. Tier 2
runs twenty-five.

`_read_outputs` used to ask for the structure by rank (`*_model_0.cif`,
sorted) and for the confidence by whatever `rglob("confidence_*.json")`
yielded first, which is directory order. On the ten tier-2 jobs that would
have recorded one pose's ipTM beside another pose's bridge, PLIP and RMSD,
and Delta-ipTM differences two ipTMs. The confidence is now derived from the
structure's own filename, so the pair cannot come apart (F99).

Tier 2 has never run, so this is the layout the pipeline has not yet seen,
built here rather than waited for.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.execute.runner import _read_outputs  # noqa: E402

STEM = "bench02_BRD4_VHL__ternary__conditioned__seed1"
SAMPLES = 25


def _write_batch(root: Path, samples: int, stem: str = STEM) -> Path:
    """Boltz's own output tree: results/predictions/<stem>/ with one
    structure and one confidence JSON per rank."""
    out = root / f"boltz_results_{stem}" / "predictions" / stem
    out.mkdir(parents=True)
    for rank in range(samples):
        (out / f"{stem}_model_{rank}.cif").write_text(f"data_rank{rank}\n")
        (out / f"confidence_{stem}_model_{rank}.json").write_text(
            json.dumps({"confidence_score": 1.0 - rank / 100,
                        "iptm": 0.9 - rank / 100,
                        "rank_written_here": rank})
        )
    (out / f"affinity_{stem}.json").write_text(json.dumps({"affinity_pred_value": -1.0}))
    return out


def test_twenty_five_samples_pair_the_best_model_with_its_own_confidence(tmp_path):
    _write_batch(tmp_path, SAMPLES)
    confidence, affinity, structure, reason = _read_outputs(tmp_path, STEM)

    assert reason is None, reason
    assert structure is not None and structure.endswith("_model_0.cif"), structure
    assert confidence["rank_written_here"] == 0, (
        "the confidence came from a different diffusion sample than the "
        "structure, which is what F99 fixed"
    )
    assert affinity["affinity_pred_value"] == -1.0


def test_the_pairing_holds_whichever_order_the_directory_yields(tmp_path):
    """The old defect was invisible on a tidy directory and depended on APFS
    ordering, so this asserts the property rather than the ordering: for
    every rank, the confidence returned is the one named after the structure
    returned. Checked by removing rank 0 and walking down, which is also the
    real case of a batch whose best model failed to write."""
    out = _write_batch(tmp_path, SAMPLES)
    for dropped in range(5):
        (out / f"{STEM}_model_{dropped}.cif").unlink()
        confidence, _affinity, structure, _reason = _read_outputs(tmp_path, STEM)
        if structure is None:
            pytest.fail("no structure found with twenty samples still present")
        rank = int(Path(structure).stem.rsplit("_model_", 1)[1])
        assert confidence["rank_written_here"] == rank, (
            f"structure is rank {rank} and confidence is rank "
            f"{confidence['rank_written_here']}"
        )
        # And it is the best rank still present, not the first name in
        # lexical order: with ranks 0 to 2 gone, "_model_10" sorts ahead
        # of "_model_3".
        assert rank == dropped + 1, (
            f"scored rank {rank} with rank {dropped + 1} available"
        )


def test_a_structure_without_its_confidence_is_a_named_failure(tmp_path):
    """Not a silent fall back to another sample's numbers. The reason is what
    the retry records in the manifest, so it has to say which of the two
    failures happened."""
    out = _write_batch(tmp_path, SAMPLES)
    (out / f"confidence_{STEM}_model_0.json").unlink()

    confidence, _affinity, structure, reason = _read_outputs(tmp_path, STEM)
    assert confidence is None
    assert structure is not None
    assert "is missing" in reason and "confidence_" in reason, reason

    # And the caller turns that into the failure detail rather than a
    # generic one. Asserted on behaviour, not on the source line: this used
    # to pin `detail = f"exit 0 but {reason}"` exactly, and broke when the
    # branch began keeping Boltz's own output too, which is the thing that
    # made the reason diagnosable (F238).
    from nobble.execute import runner as runner_module

    calls = {"n": 0}

    def _exit_zero(command, env, timeout):
        calls["n"] += 1
        return "ok", 0, "", "something Boltz printed"

    original_run, original_read = runner_module._run_boltz, runner_module._read_outputs
    try:
        runner_module._run_boltz = _exit_zero
        runner_module._read_outputs = lambda output_dir, job_id: (
            None, None, "s.cif", reason)
        campaign = tmp_path / "campaign_named"
        (campaign / "outputs").mkdir(parents=True)
        (tmp_path / "n.yaml").write_text("version: 1\n")
        outcome = runner_module.run_job(
            {"job_id": "pairN__ternary__unconstrained__seed1", "tokens": 10,
             "yaml": str(tmp_path / "n.yaml"), "timeout_seconds": 600,
             "seed": 1, "pair_id": "pairN", "complex_type": "ternary"},
            campaign, runner_module.settings_from_config(tier=1))
    finally:
        runner_module._run_boltz, runner_module._read_outputs = (
            original_run, original_read)

    assert "exit 0 but" in outcome.detail, outcome.detail
    assert reason in outcome.detail, (reason, outcome.detail)
    assert "something Boltz printed" in outcome.detail, outcome.detail


def test_an_empty_output_directory_still_says_nothing_was_written(tmp_path):
    confidence, affinity, structure, reason = _read_outputs(tmp_path, STEM)
    assert (confidence, affinity, structure) == (None, None, None)
    assert reason == "no confidence JSON written"


def test_several_confidences_with_no_structure_refuse_to_guess(tmp_path):
    out = _write_batch(tmp_path, SAMPLES)
    for rank in range(SAMPLES):
        (out / f"{STEM}_model_{rank}.cif").unlink()

    confidence, _affinity, structure, reason = _read_outputs(tmp_path, STEM)
    assert confidence is None and structure is None
    assert "none can be matched to a pose" in reason, reason


def test_one_sample_behaves_exactly_as_before(tmp_path):
    """Tier 1 is 2,360 jobs of the main campaign and must not move."""
    _write_batch(tmp_path, 1)
    confidence, affinity, structure, reason = _read_outputs(tmp_path, STEM)
    assert reason is None
    assert confidence["rank_written_here"] == 0
    assert structure.endswith("_model_0.cif")
    assert affinity is not None


def test_against_a_real_tier_one_output_directory():
    """The regression guard that matters: a directory Boltz actually wrote
    during this campaign, read with the new code."""
    from nobble.execute.campaign import latest

    campaign = latest("campaign")
    if campaign is None:
        pytest.skip("no campaign assembled")
    dirs = [p for p in sorted((campaign / "outputs").glob("*"))
            if list(p.rglob("confidence_*.json"))]
    if not dirs:
        pytest.skip("no completed predictions yet")

    job_dir = dirs[0]
    confidence, _affinity, structure, reason = _read_outputs(job_dir, job_dir.name)
    assert reason is None, reason
    assert confidence is not None and "iptm" in confidence
    assert structure is not None and structure.endswith(".cif")
    assert Path(structure).name == f"{job_dir.name}_model_0.cif"
    assert (Path(structure).parent
            / f"confidence_{Path(structure).stem}.json").exists()
