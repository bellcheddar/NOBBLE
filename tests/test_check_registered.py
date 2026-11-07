"""The registered predictions can return wrong, which is the whole point.

F18: "a scorer that cannot return wrong is not scoring anything". F251, F252
and F253 were registered before their data existed, so each is scored here
against a fixture that should refute it as well as one that should support it.
If only the supporting case were tested, the scorer would be decoration.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "check_registered", ROOT / "tools" / "check_registered.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sievers(tmp_path, tier2_shift):
    """Four degraded and six not, with tier-2 deltas shifted by arm."""
    from nobble.validate import layers

    campaign = tmp_path / "campaign_f251"
    campaign.mkdir()
    tier1, tier2 = [], []
    for index in range(4):
        pair = f"sv_pos_{index}"
        tier1.append({"pair_id": pair, "tier": layers.ROC_ARM,
                      "peptide_label": "degraded",
                      "bridge_formation_rate": 0.5})
        tier2.append({"pair_id": pair,
                      "bridge_formation_rate": 0.5 + tier2_shift})
    for index in range(6):
        pair = f"sv_neg_{index}"
        tier1.append({"pair_id": pair, "tier": layers.ROC_ARM,
                      "peptide_label": "not_degraded",
                      "bridge_formation_rate": 0.5})
        tier2.append({"pair_id": pair, "bridge_formation_rate": 0.5 + tier2_shift})
    (campaign / "scores.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in tier1))
    (campaign / "scores_tier2.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in tier2))
    return campaign


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def _tier_b_arm(tmp_path, positives: int, scored: list[dict]) -> Path:
    """A Tier B arm with `positives` pairs queued and only `scored` scored.

    Named apart from `_tier_b` below, which predates it and writes no queue
    on purpose: two helpers of the same name in one module is the later one
    silently winning, which is how the first version of these four tests ran
    against the wrong fixture.
    """
    campaign = tmp_path / "tier_b_coverage"
    campaign.mkdir()
    _write(campaign / "queue.jsonl",
           [{"job_id": f"j{i}", "pair_id": f"tb_pos_X{i}"}
            for i in range(positives)]
           + [{"job_id": f"k{i}", "pair_id": f"tb_neg_X{i}"}
              for i in range(positives)])
    _write(campaign / "scores.jsonl", scored)
    return campaign


def test_f251_is_withdrawn_rather_than_pending(tmp_path):
    """Pending would have waited forever for a measurement that cannot exist.

    Tier 2 is ternary-only, so Delta-ipTM has no binary term there. Left as
    "not yet testable" the scorer would have waited for scores_tier2.jsonl and
    then skipped every row for a null delta, reporting a missing measurement
    as an unfinished stage (F251, F254).
    """
    campaign = tmp_path / "campaign_bare"
    campaign.mkdir()
    (campaign / "scores.jsonl").write_text("")
    verdict = _module().f251_refinement_discrimination(campaign)
    assert verdict["status"] == "withdrawn", verdict
    assert "ternary-only" in verdict["detail"], verdict
    assert "F254" in verdict["detail"], verdict


def test_f254_is_not_yet_testable_without_tier_two_scores(tmp_path):
    campaign = tmp_path / "campaign_bare2"
    campaign.mkdir()
    (campaign / "scores.jsonl").write_text("")
    verdict = _module().f254_refinement_bridging(campaign)
    assert verdict["status"] == "not yet testable", verdict
    assert "scores_tier2" in verdict["detail"], verdict


def test_f254_returns_wrong_when_refinement_finds_bridges(tmp_path):
    """A rise beyond the line is the falsifier, not the claim."""
    verdict = _module().f254_refinement_bridging(
        _sievers(tmp_path, tier2_shift=0.40))
    assert verdict["status"] == "WRONG", verdict
    assert verdict["move"] > 0.10, verdict


def test_f254_returns_wrong_when_refinement_loses_bridges(tmp_path):
    """A fall is refuting too: it would mean tier 1 overstates the rate."""
    verdict = _module().f254_refinement_bridging(
        _sievers(tmp_path, tier2_shift=-0.40))
    assert verdict["status"] == "WRONG", verdict
    assert verdict["move"] < -0.10, verdict


def test_f254_is_supported_when_nothing_moves(tmp_path):
    verdict = _module().f254_refinement_bridging(
        _sievers(tmp_path, tier2_shift=0.0))
    assert verdict["status"] == "supported", verdict
    assert verdict["move"] == 0.0, verdict


PARENT_SEQUENCE = "PFQCNQCGASFTQKG"


def _profile(tmp_path, position):
    """A real scan_profile, not a hand-written dict.

    Writing the shape by hand assumes it, which is the error that made two of
    the three registered predictions unfalsifiable: a falsifier written
    against an imagined measurement. Built through lift.scan_profile so the
    keys the scorer reads are the keys the pipeline writes.
    """
    from nobble.design import lift as lift_module

    campaign = tmp_path / f"design_f252_{position}"
    campaign.mkdir()
    lifts = [
        lift_module.Lift(
            variant_id=f"v{position}", parent_peptide_id="p",
            substitution=f"{PARENT_SEQUENCE[position - 1]}{position}A",
            position=position, variant_delta_iptm=-0.4,
            parent_delta_iptm=0.1, lift=-0.5, status="computed"),
        lift_module.Lift(
            variant_id="v_other", parent_peptide_id="p",
            substitution="Q3A", position=3, variant_delta_iptm=0.0,
            parent_delta_iptm=0.1, lift=-0.1, status="computed"),
    ]
    profile = lift_module.scan_profile(lifts, PARENT_SEQUENCE)
    assert (profile["most_sensitive"] or {}).get("position") == position, profile
    (campaign / "scan_profile.json").write_text(json.dumps(profile))
    return campaign


def test_f252_is_supported_on_a_contacting_position(tmp_path):
    verdict = _module().f252_design_scan_position(_profile(tmp_path, 7))
    assert verdict["status"] == "supported", verdict


def test_f252_returns_wrong_on_a_position_touching_nothing(tmp_path):
    verdict = _module().f252_design_scan_position(_profile(tmp_path, 14))
    assert verdict["status"] == "WRONG", verdict


def test_f252_is_unclear_in_between(tmp_path):
    verdict = _module().f252_design_scan_position(_profile(tmp_path, 10))
    assert verdict["status"] == "unclear", verdict


def _tier_b(tmp_path, positive_rate, scramble_rate):
    campaign = tmp_path / "tier_b_f253"
    campaign.mkdir()
    rows = [
        {"pair_id": "tb_pos_ASB8_BRD4_759",
         "bridge_formation_rate": positive_rate},
        {"pair_id": "tb_neg_ASB8_BRD4_759",
         "bridge_formation_rate": scramble_rate},
    ]
    (campaign / "scores.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows))
    # A queue holding exactly this pair, so these tests read as a complete
    # arm. Without one they passed through the branch that has no
    # denominator, which is the right answer to a different question.
    (campaign / "queue.jsonl").write_text("".join(
        json.dumps({"job_id": f"j_{row['pair_id']}",
                    "pair_id": row["pair_id"]}) + "\n" for row in rows))
    return campaign


def test_f253_is_supported_when_nothing_clears_the_line(tmp_path):
    verdict = _module().f253_tier_b_bridging(_tier_b(tmp_path, 0.6, 0.4))
    assert verdict["status"] == "supported", verdict
    assert verdict["hits"] == [], verdict


def test_f253_returns_wrong_on_a_hit(tmp_path):
    """The positive bridges and its own scramble does not.

    Stated as a rate because Tier B runs five ternary seeds per arm: the
    first version of this line asked for eight of ten and could never fire.
    """
    # 0.8 against 0.2 is 4 of 5 against 1 of 5, which is what Tier B runs.
    verdict = _module().f253_tier_b_bridging(_tier_b(tmp_path, 0.8, 0.2))
    assert verdict["status"] == "WRONG", verdict
    assert verdict["hits"][0]["pair_id"] == "tb_pos_ASB8_BRD4_759", verdict


def test_f253_needs_the_scramble_before_it_judges(tmp_path):
    """A positive with no matched scramble is counted, never scored."""
    campaign = tmp_path / "tier_b_unpaired"
    campaign.mkdir()
    (campaign / "scores.jsonl").write_text(json.dumps(
        {"pair_id": "tb_pos_ASB8_BRD4_759",
         "bridge_formation_rate": 1.0}) + "\n")
    verdict = _module().f253_tier_b_bridging(campaign)
    assert verdict["status"] == "supported", verdict
    assert verdict["unpaired"] == 1, verdict


def test_the_live_state_is_every_prediction_pending():
    """Today: nothing has run, so nothing is scored and nothing is wrong."""
    assert _module().main([]) == 0


def test_the_brief_mode_is_one_line_per_prediction():
    """A status command is scanned, so the claims stay in the full output."""
    import io
    import contextlib

    module = _module()
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        module.main(["--brief"])
    lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    # One summary line plus one per prediction. Counted from the summary
    # line's own figure rather than from a literal, which went stale the
    # moment a fifth prediction was registered: the property is one line per
    # prediction, not five lines.
    import re

    recorded = re.search(r"(\d+) recorded", lines[0])
    assert recorded, lines[0]
    assert len(lines) == int(recorded.group(1)) + 1, lines
    assert all("falsifier" not in line for line in lines), lines
    for finding in ("F251", "F252", "F253", "F254", "F268"):
        assert any(finding in line for line in lines), (finding, lines)


def test_the_status_command_surfaces_the_verdicts():
    """Wired where it is read, since the chain cannot be edited mid-run."""
    text = (ROOT / "tools" / "status.sh").read_text()
    assert "check_registered.py --brief" in text, (
        "status.sh does not surface the registered predictions, so a verdict "
        "would only appear if someone ran the tool by hand")


def test_the_chain_wiring_is_recorded_as_outstanding():
    """run_chain.sh was executing when this was written.

    Editing a running bash script corrupts it, because the shell reads it
    incrementally. The chain already calls status.sh as its last line, so the
    verdicts do appear at the end of a run; what is outstanding is calling the
    scorer at each stage, and the reason it was not done is in status.sh.
    """
    # Normalised, because the comment wraps and the phrase crosses a line
    # with a "# " between: searching the raw text for it cannot match, which
    # is how this assertion failed when it was written.
    raw = (ROOT / "tools" / "status.sh").read_text()
    text = " ".join(raw.replace("#", " ").split())
    assert "executing while this is written" in text, (
        "the reason the chain itself is not wired has been lost")
    assert "bash tools/status.sh" in (ROOT / "tools" / "run_chain.sh").read_text()


def test_a_partial_tier_b_arm_does_not_confirm_f253(tmp_path):
    """"No pair clears the line" is vacuously true of an empty set.

    The arm is run with `|| true` and the runner stops on Gate G5, so a
    partial scores.jsonl is a normal outcome. One scored row was enough for
    this to report `supported`, which is F251's error in a new place: a
    prediction confirmed by the absence of the data that could refute it.
    """
    campaign = _tier_b_arm(tmp_path, 10, [
        {"pair_id": "tb_pos_X0", "bridge_formation_rate": 0.2},
        {"pair_id": "tb_neg_X0", "bridge_formation_rate": 0.0},
    ])
    verdict = _module().f253_tier_b_bridging(campaign)
    assert verdict["status"] == "not yet testable", verdict
    assert verdict["positives_compared"] == 1, verdict
    assert verdict["positives_expected"] == 10, verdict


def test_a_complete_arm_with_no_hit_confirms_f253(tmp_path):
    campaign = _tier_b_arm(tmp_path, 1, [
        {"pair_id": "tb_pos_X0", "bridge_formation_rate": 0.4},
        {"pair_id": "tb_neg_X0", "bridge_formation_rate": 0.0},
    ])
    verdict = _module().f253_tier_b_bridging(campaign)
    assert verdict["status"] == "supported", verdict


def test_one_hit_refutes_f253_even_on_a_partial_arm(tmp_path):
    """Refutation takes one case, confirmation takes the set.

    The claim is that no pair clears the line, so a pair that clears it
    refutes the claim whatever is still to be scored. Requiring full coverage
    before reporting WRONG would let a known counterexample sit unreported
    behind an unfinished queue.
    """
    campaign = _tier_b_arm(tmp_path, 10, [
        {"pair_id": "tb_pos_X0", "bridge_formation_rate": 0.9},
        {"pair_id": "tb_neg_X0", "bridge_formation_rate": 0.1},
    ])
    verdict = _module().f253_tier_b_bridging(campaign)
    assert verdict["status"] == "WRONG", verdict
    assert verdict["hits"][0]["pair_id"] == "tb_pos_X0", verdict
    assert verdict["positives_compared"] == 1, verdict


def test_the_f253_denominator_comes_from_the_queue(tmp_path):
    """Same rule as the atlas's jobs_total, for the same reason.

    A count of what is on disk has no denominator: it reads as complete
    whenever it is read, and the fraction it reports gets better the less has
    run. Checked by removing the queue and confirming the verdict changes,
    rather than by searching the source for a filename.
    """
    campaign = _tier_b_arm(tmp_path, 10, [
        {"pair_id": "tb_pos_X0", "bridge_formation_rate": 0.2},
        {"pair_id": "tb_neg_X0", "bridge_formation_rate": 0.0},
    ])
    assert _module().f253_tier_b_bridging(campaign)["status"] == (
        "not yet testable")
    (campaign / "queue.jsonl").unlink()
    # With no queue there is no denominator, so the old behaviour returns and
    # the verdict is what it can be rather than a fabricated fraction.
    verdict = _module().f253_tier_b_bridging(campaign)
    assert verdict["positives_expected"] == 0, verdict
    assert verdict["status"] == "supported", verdict


def _bench06(tmp_path, unconstrained_states: dict[str, list[str]]) -> Path:
    """A campaign whose bench06 refinements are in a given state.

    Five unconstrained jobs are queued either way, because the denominator
    comes from the queue (F258) and "none succeeded" over nothing attempted
    is not a result.
    """
    campaign = tmp_path / "campaign_f268"
    campaign.mkdir()
    pair = "bench06_RBM39_DCAF15"
    queue, state = [], []
    for conditioning in ("conditioned", "unconstrained"):
        for seed in range(1, 6):
            job = f"{pair}__ternary__{conditioning}__seed{seed}__tier2"
            queue.append({"job_id": job, "pair_id": pair, "tokens": 1223})
    for seed in range(1, 6):
        job = f"{pair}__ternary__conditioned__seed{seed}__tier2"
        state.append({"job_id": job,
                      "status": "failed: exit 0 but no confidence JSON "
                                "written", "seconds": 9492.0})
    for job, states in unconstrained_states.items():
        for status in states:
            state.append({"job_id": job, "status": status, "seconds": 9400.0})
    _write(campaign / "queue_tier2.jsonl", queue)
    _write(campaign / "state_tier2.jsonl", state)
    return campaign


def test_f268_is_not_testable_until_the_unconstrained_jobs_run(tmp_path):
    verdict = _module().f268_refinement_size_limit(_bench06(tmp_path, {}))
    assert verdict["status"] == "not yet testable", verdict
    assert verdict["unconstrained_queued"] == 5, verdict
    assert verdict["conditioned_attempted"] == 5, verdict


def test_f268_is_supported_when_every_conditioning_fails(tmp_path):
    """The size reading: conditioning does not change the 1,223 tokens."""
    states = {f"bench06_RBM39_DCAF15__ternary__unconstrained__seed{s}__tier2":
              ["failed: exit 0 but no confidence JSON written"]
              for s in range(1, 6)}
    verdict = _module().f268_refinement_size_limit(_bench06(tmp_path, states))
    assert verdict["status"] == "supported", verdict
    assert "454 tokens" in verdict["detail"], verdict


def test_f268_is_wrong_when_one_unconstrained_job_completes(tmp_path):
    """One success refutes it, as with F253: the claim is that none does.

    And it says what the success would mean, which is the point of the
    prediction: the limit would follow the pocket constraint rather than the
    size, and the pair would be refinable without conditioning.
    """
    states = {f"bench06_RBM39_DCAF15__ternary__unconstrained__seed{s}__tier2":
              ["failed: exit 0 but no confidence JSON written"]
              for s in range(2, 6)}
    states["bench06_RBM39_DCAF15__ternary__unconstrained__seed1__tier2"] = [
        "failed: exit 0 but no confidence JSON written", "done"]
    verdict = _module().f268_refinement_size_limit(_bench06(tmp_path, states))
    assert verdict["status"] == "WRONG", verdict
    assert verdict["unconstrained_done"] == [
        "bench06_RBM39_DCAF15__ternary__unconstrained__seed1__tier2"], verdict
    assert "pocket constraint" in verdict["detail"], verdict


def test_f268_ignores_a_running_job(tmp_path):
    """A job in flight has not failed and has not succeeded.

    Counting a `running` record as an attempt would report the prediction
    testable while the deciding job was still going.
    """
    states = {f"bench06_RBM39_DCAF15__ternary__unconstrained__seed{s}__tier2":
              ["failed: exit 0 but no confidence JSON written"]
              for s in range(1, 5)}
    states["bench06_RBM39_DCAF15__ternary__unconstrained__seed5__tier2"] = [
        "running"]
    verdict = _module().f268_refinement_size_limit(_bench06(tmp_path, states))
    assert verdict["status"] == "not yet testable", verdict
    assert verdict["unconstrained_attempted"] == 4, verdict


# --------------------------------------------------------------------------- #
# F306: does bench06 refine at a reduced sample count? (F298's claim)
# --------------------------------------------------------------------------- #

def _bench06_reduced(tmp_path, results):
    """A bench06 tier-2 campaign whose results carry a sample count.

    `results` maps job id to (status, diffusion_samples). The count lives on
    the result row and the status on the state row, so the check joins them,
    and a job with no recorded count ran before F298 and is not an attempt at
    a reduced count.
    """
    campaign = _bench06(tmp_path, {
        job: [status] for job, (status, _count) in results.items()})
    _write(campaign / "results_tier2.jsonl",
           [{"job_id": job, "diffusion_samples": count}
            for job, (_status, count) in results.items()])
    return campaign


def test_f306_is_not_testable_before_a_reduced_attempt_runs(tmp_path):
    verdict = _module().f306_reduced_sampling_succeeds(_bench06(tmp_path, {}))
    assert verdict["status"] == "not yet testable", verdict
    assert "fewer than 25 samples" in verdict["detail"], verdict


def test_f306_ignores_an_attempt_at_the_full_count(tmp_path):
    """A job that failed again at twenty-five samples says nothing about
    this claim, and counting it would let the old failures decide a
    prediction about the new settings."""
    campaign = _bench06_reduced(tmp_path, {
        "bench06_RBM39_DCAF15__ternary__unconstrained__seed1__tier2":
            ("failed: exit 0 but no confidence JSON written", 25),
    })
    verdict = _module().f306_reduced_sampling_succeeds(campaign)
    assert verdict["status"] == "not yet testable", verdict


def test_f306_ignores_a_job_with_no_recorded_count(tmp_path):
    """Every bench06 attempt before F298 has none, and reading a missing
    count as a reduced one would score the prediction on the evidence that
    motivated it."""
    campaign = _bench06_reduced(tmp_path, {
        "bench06_RBM39_DCAF15__ternary__unconstrained__seed1__tier2":
            ("failed: exit 0 but no confidence JSON written", None),
    })
    verdict = _module().f306_reduced_sampling_succeeds(campaign)
    assert verdict["status"] == "not yet testable", verdict


def test_f306_is_supported_when_a_reduced_attempt_completes(tmp_path):
    campaign = _bench06_reduced(tmp_path, {
        "bench06_RBM39_DCAF15__ternary__unconstrained__seed1__tier2":
            ("done", 9),
        "bench06_RBM39_DCAF15__ternary__unconstrained__seed2__tier2":
            ("failed: exit 0 but no confidence JSON written", 9),
    })
    verdict = _module().f306_reduced_sampling_succeeds(campaign)
    assert verdict["status"] == "supported", verdict
    assert verdict["reduced_attempts"] == 2, verdict
    assert "F268 is wrong" in verdict["detail"], verdict


def test_f306_is_wrong_when_every_reduced_attempt_still_fails(tmp_path):
    """The outcome that would retire F298's size story rather than defend
    it, which is why the prediction is registered at all."""
    campaign = _bench06_reduced(tmp_path, {
        f"bench06_RBM39_DCAF15__ternary__unconstrained__seed{seed}__tier2":
            ("failed: exit 0 but no confidence JSON written", 9)
        for seed in range(1, 6)
    })
    verdict = _module().f306_reduced_sampling_succeeds(campaign)
    assert verdict["status"] == "WRONG", verdict
    assert verdict["reduced_attempts"] == 5, verdict
    assert "needs replacing" in verdict["detail"], verdict


def test_f306_and_f268_disagree_by_construction():
    """One predicts the other is wrong. Registered that way deliberately, so
    whichever way the refinement goes, one of them is scored against me."""
    module = _module()
    f268 = module.f268_refinement_size_limit.__doc__ or ""
    f306 = module.f306_reduced_sampling_succeeds.__doc__ or ""
    assert "F268" in f306, "F306 does not say which claim it contradicts"
    assert "size" in f268 or "constraint" in f268


def test_f306_appears_in_the_report():
    """Computed and not reported would make it unfalsifiable in practice."""
    import ast

    source = (ROOT / "tools" / "check_registered.py").read_text()
    tree = ast.parse(source)
    main = next(node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == "main")
    called = {node.func.id for node in ast.walk(main)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "f306_reduced_sampling_succeeds" in called
