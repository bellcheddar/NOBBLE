"""Tier 2 reduces its sampling for a job too large to refine (F298).

Of 155 resolved tier-2 jobs, every success is at most 454 tokens and every
failure is 1,223, with no overlap, and the same 1,223-token jobs all
complete at tier-1 settings. Six consecutive clean exits wrote no
predictions directory at all, about 2.6 hours each, so the product of tokens
and samples is what fails.

The reduction is the fallback ladder's "retry with a fix" applied before the
first attempt rather than after it, since the first attempt's outcome is
known. These assert that it fires on size, that it never fires on tier 1,
that the budget is config rather than a literal, that the reduced count
reaches Boltz, and that the job records what it actually sampled.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths                                    # noqa: E402
from nobble.execute import runner                           # noqa: E402

# The measured split, from `state_tier2.jsonl` at the time of writing. Named
# rather than inlined because these two numbers are the evidence, and a test
# that used round ones would be asserting a design instead of a measurement.
LARGEST_SUCCESS_TOKENS = 454
SMALLEST_FAILURE_TOKENS = 1223


def test_the_largest_observed_success_is_not_reduced():
    settings = runner.settings_from_config(2)
    samples, note = runner.sampling_for(
        {"tokens": LARGEST_SUCCESS_TOKENS}, settings)
    assert samples == settings["diffusion_samples"]
    assert note == ""


def test_the_size_that_failed_is_reduced():
    settings = runner.settings_from_config(2)
    samples, note = runner.sampling_for(
        {"tokens": SMALLEST_FAILURE_TOKENS}, settings)
    assert samples < settings["diffusion_samples"]
    assert samples >= 1, "a refinement that samples nothing is not a refinement"
    assert str(SMALLEST_FAILURE_TOKENS) in note and str(samples) in note


def test_the_reduction_never_goes_below_one_sample():
    """A product big enough to floor the division still runs. Ten recycling
    steps with potentials is a refinement over tier 1's three without, so
    the job is worth attempting at one sample."""
    settings = runner.settings_from_config(2)
    samples, note = runner.sampling_for(
        {"tokens": settings["token_sample_budget"] * 10}, settings)
    assert samples == 1
    assert note


def test_tier_one_is_never_reduced():
    """It samples once, so there is no product to exceed, and a budget key
    on tier 1 would be an invitation to reduce a job to zero samples."""
    settings = runner.settings_from_config(1)
    assert "token_sample_budget" not in settings
    samples, note = runner.sampling_for(
        {"tokens": SMALLEST_FAILURE_TOKENS * 10}, settings)
    assert samples == settings["diffusion_samples"]
    assert note == ""


def test_the_budget_comes_from_config():
    """CLAUDE.md: thresholds come from config, never a literal in Python."""
    configured = paths.tuning()["campaign"]["tier2_token_sample_budget"]
    assert runner.settings_from_config(2)["token_sample_budget"] == configured
    source = (ROOT / "nobble" / "execute" / "runner.py").read_text()
    assert str(configured) not in source, (
        "the budget is spelled as a literal in runner.py as well as in "
        "config, so the two can drift"
    )


def test_the_budget_is_the_largest_product_actually_seen():
    """Not a round number someone liked. If this fails, either the evidence
    moved or the budget was invented."""
    configured = paths.tuning()["campaign"]["tier2_token_sample_budget"]
    asked = paths.tuning()["campaign"]["tier2_diffusion_samples"]
    assert configured == LARGEST_SUCCESS_TOKENS * asked


def _run_one(tmp_path, monkeypatch, tokens):
    commands = []

    def fake_run_boltz(command, env, timeout):
        commands.append(command)
        return ("ok", 0, "", "")

    monkeypatch.setattr(runner, "_run_boltz", fake_run_boltz)
    monkeypatch.setattr(
        runner, "_read_outputs",
        lambda output_dir, job_id: ({"iptm": 0.5}, None, "s.cif", ""))
    settings = dict(runner.settings_from_config(2), job_timeout_seconds=600)
    outcome = runner.run_job(
        {"job_id": "j1", "seed": 1, "yaml": str(tmp_path / "j1.yaml"),
         "tokens": tokens, "timeout_seconds": 600},
        tmp_path, settings,
    )
    return outcome, commands


def test_the_reduced_count_is_what_boltz_is_told(tmp_path, monkeypatch):
    """The reduction is worthless if it only changes a printed note."""
    outcome, commands = _run_one(tmp_path, monkeypatch, SMALLEST_FAILURE_TOKENS)
    assert len(commands) == 1
    command = commands[0]
    position = command.index("--diffusion_samples")
    asked = runner.settings_from_config(2)["diffusion_samples"]
    assert int(command[position + 1]) < asked
    assert int(command[position + 1]) == outcome.diffusion_samples


def test_the_job_records_what_it_sampled(tmp_path, monkeypatch):
    """So nothing compares a reduced refinement with a full one without
    knowing. The results row carries it, not just the dataclass."""
    big, _ = _run_one(tmp_path, monkeypatch, SMALLEST_FAILURE_TOKENS)
    small, _ = _run_one(tmp_path, monkeypatch, LARGEST_SUCCESS_TOKENS)
    assert big.to_dict()["diffusion_samples"] < small.to_dict()["diffusion_samples"]
    assert small.to_dict()["diffusion_samples"] == (
        runner.settings_from_config(2)["diffusion_samples"])


def test_a_failed_reduced_job_still_records_its_sample_count(tmp_path, monkeypatch):
    """The next rung of the ladder needs to know what the attempt that just
    failed was given, or lowering the budget is another guess."""
    def fake_run_boltz(command, env, timeout):
        return ("ok", 0, "", "")

    monkeypatch.setattr(runner, "_run_boltz", fake_run_boltz)
    monkeypatch.setattr(
        runner, "_read_outputs",
        lambda output_dir, job_id: (None, None, None,
                                    "no confidence JSON written"))
    settings = dict(runner.settings_from_config(2), job_timeout_seconds=600)
    outcome = runner.run_job(
        {"job_id": "j1", "seed": 1, "yaml": str(tmp_path / "j1.yaml"),
         "tokens": SMALLEST_FAILURE_TOKENS, "timeout_seconds": 600},
        tmp_path, settings,
    )
    assert outcome.status.startswith("failed")
    assert outcome.diffusion_samples is not None
    assert outcome.diffusion_samples < settings["diffusion_samples"]
