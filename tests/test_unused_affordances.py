"""Parameters that exist for a stated reason nobody exercised.

F79 found that `cost_of`'s `tokens_per_pair`, added to fix F45, was never
passed by either call site, so the one caller kept taking the fallback the
finding was about. Sweeping for the general shape, every optional parameter
in `nobble/` against every call anywhere, positional or by name, gives
twenty-two that are never supplied.

Most are ordinary configurable defaults and are left alone: the bootstrap's
round count and seed, a batch size, a row limit. Three were not.

`settings_from_config`'s timeout carries the comment "Still overridable,
because a test needs to", and no test overrode it. The claim was the
justification for the parameter existing, which makes it worth either
removing or making true.

`cost_of`'s `tokens_per_pair` became dead when F79 wired `job_tokens`
through instead. It is the simpler form of the same idea, kept because a
caller with one job size is the common case, so the branch that expands it
is tested rather than left to be discovered wrong later.

`matched_control_roc`'s `statistic` is the curve's whole subject and has
only ever been computed on one field (F80).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402
from nobble.execute import runner  # noqa: E402
from nobble.validate import layers  # noqa: E402


def test_the_job_timeout_comes_from_config_by_default():
    campaign = paths.tuning()["campaign"]
    configured = int(campaign["job_timeout_seconds"])
    multiple = int(campaign["tier2_timeout_multiple"])
    assert runner.settings_from_config(1)["job_timeout_seconds"] == configured
    assert runner.settings_from_config(2)["job_timeout_seconds"] == (
        configured * multiple)


def test_the_job_timeout_can_be_overridden():
    """The comment beside this parameter says a test needs the override.
    This is that test; before it, the claim was the only evidence."""
    multiple = int(paths.tuning()["campaign"]["tier2_timeout_multiple"])
    assert runner.settings_from_config(1, job_timeout_seconds=7)[
        "job_timeout_seconds"] == 7
    assert runner.settings_from_config(2, job_timeout_seconds=7)[
        "job_timeout_seconds"] == 7 * multiple


def test_the_tier_two_multiple_is_configured_not_written_in_code():
    """The factor decides when a refinement is abandoned, and tier 2 has
    never run, so it is a guess. A guess in config can be changed by
    whoever measures it; a guess in an expression has to be found first."""
    import re

    source = (ROOT / "nobble" / "execute" / "runner.py").read_text()
    assert "tier2_timeout_multiple" in source
    assert not re.search(r"job_timeout_seconds \* \d", source), (
        "the tier-2 timeout factor is a literal in runner.py again"
    )


def test_the_watchdog_bound_follows_the_configured_multiple():
    """`hard_bound_seconds` derives from the runner so the two cannot
    drift. A tier-2 bound that did not follow the multiple would call a
    healthy refinement stalled, which is F20's mistake with a longer
    fuse."""
    from nobble.execute import watchdog

    multiple = int(paths.tuning()["campaign"]["tier2_timeout_multiple"])
    one = watchdog.hard_bound_seconds(tier=1)
    two = watchdog.hard_bound_seconds(tier=2)
    assert two > one
    assert two >= one * multiple * 0.9, (
        f"the tier-2 bound {two} does not scale with the multiple {multiple}"
    )


def test_an_overridden_timeout_does_not_disturb_the_other_settings():
    configured = paths.tuning()["campaign"]
    plain = runner.settings_from_config(1)
    overridden = runner.settings_from_config(1, job_timeout_seconds=7)
    assert plain["recycles"] == overridden["recycles"] == int(
        configured["tier1_recycles"])
    assert plain["diffusion_samples"] == overridden["diffusion_samples"]


def test_the_simpler_cost_form_expands_to_the_same_jobs():
    """`tokens_per_pair` is the one-size-fits-all form of `job_tokens`, and
    F79 left its expansion branch unexercised. For a uniform scan the two
    must agree, or the simpler form is a trap."""
    from nobble.curate.manifest import jobs_per_pair
    from nobble.design.report import cost_of

    if not paths.THROUGHPUT.exists():
        pytest.skip("no measured throughput yet")

    count = 16
    uniform = cost_of(count, tokens_per_pair=144)
    explicit = cost_of(count, job_tokens=[144] * (count * jobs_per_pair()))
    assert uniform["projected_hours"] == explicit["projected_hours"]
    assert "each priced in its own token band" in uniform["basis"]


def test_the_explicit_job_list_wins_over_the_uniform_one():
    """Both supplied is a caller mistake, and the more specific one is the
    answer rather than a silent average of the two."""
    from nobble.design.report import cost_of

    if not paths.THROUGHPUT.exists():
        pytest.skip("no measured throughput yet")
    both = cost_of(16, tokens_per_pair=1200, job_tokens=[144] * 240)
    only = cost_of(16, job_tokens=[144] * 240)
    assert both["projected_hours"] == only["projected_hours"]


def test_the_roc_statistic_is_the_field_the_spec_names(tmp_path):
    """The parameter names the curve's subject. Spec 5.3 puts Delta-ipTM on
    the Sievers split, and that is the default; a caller asking for another
    field must get a curve over that field rather than the default one."""
    rows = []
    for index in range(4):
        rows.append({"pair_id": f"sv{index}", "tier": layers.ROC_ARM,
                     "peptide_label": "degraded", "delta_iptm": 0.1,
                     "bridge_percentile": 90.0 - index,
                     "seeds_ternary": 10, "seeds_binary": 5})
        rows.append({"pair_id": f"nd{index}", "tier": layers.ROC_ARM,
                     "peptide_label": "not_degraded", "delta_iptm": 0.9,
                     "bridge_percentile": 10.0 + index,
                     "seeds_ternary": 10, "seeds_binary": 5})
    campaign = tmp_path / "campaign_20261104T000000Z"
    campaign.mkdir()
    (campaign / "scores.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")

    # delta_iptm is deliberately the wrong way round here, so the two
    # statistics cannot agree by accident.
    on_delta = layers.matched_control_roc(campaign)
    on_bridge = layers.matched_control_roc(campaign, statistic="bridge_percentile")
    assert on_delta.summary["statistic"] == "delta_iptm"
    assert on_bridge.summary["statistic"] == "bridge_percentile"
    assert on_delta.summary["auc"] == 0.0
    assert on_bridge.summary["auc"] == 1.0


def test_a_timed_out_job_names_the_number_that_killed_it():
    """What makes an unvalidated multiple tolerable. Tier 2 has never run,
    so the factor is a guess, and the guess is tolerable only because a job
    it kills says so and says the value: the first tier-2 campaign reports
    `timeout after 21600s` rather than quietly losing refinements."""
    source = (ROOT / "nobble" / "execute" / "runner.py").read_text()
    assert 'f"timeout after {settings[\'job_timeout_seconds\']}s"' in source, (
        "a timed-out job no longer reports the timeout it exceeded, so an "
        "unvalidated tier-2 multiple would fail silently"
    )
