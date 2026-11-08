"""The registered predictions can return wrong, which is the whole point.

F18: "a scorer that cannot return wrong is not scoring anything". F251, F252
and F253 were registered before their data existed, so each is scored here
against a fixture that should refute it as well as one that should support it.
If only the supporting case were tested, the scorer would be decoration.
"""
from __future__ import annotations

import importlib.util
import json
import time
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


def test_the_live_state_exits_non_zero_once_a_prediction_is_wrong():
    """This asserted every prediction was pending, which was true when it
    was written and stopped being true at 02:45 on 2026-11-08.

    F334 claimed a reduced-sample job lands within three per cent of the
    six-run mean of 9,512 seconds. It passed the top of that band still
    running, which refutes it whatever it does next, and the scorer now
    says so rather than waiting for a duration to be written.

    So the assertion worth keeping is not "nothing is wrong". It is that
    the exit code tracks the verdicts: zero while nothing is refuted, one
    once something is, because that is what a chain or a person reads.
    Pinning the count instead would make this test a transcript of a
    particular afternoon.
    """
    module = _module()
    code = module.main([])
    campaign = sorted(ROOT.glob("campaigns/campaign_*"))
    if not campaign:
        assert code == 0
        return
    wrong = [predicate(campaign[-1]) for predicate in
             (module.f268_refinement_size_limit,
              module.f306_reduced_sampling_succeeds,
              module.f334_sampling_buys_no_time)]
    refuted = [row["finding"] for row in wrong if row["status"] == "WRONG"]
    assert code == (1 if refuted else 0), (code, refuted)


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


def _bench06(tmp_path, unconstrained_states: dict[str, list[str]],
             conditioned_states: dict[str, list[str]] | None = None,
             samples: dict[str, int] | None = None) -> Path:
    """A campaign whose bench06 refinements are in a given state.

    Five unconstrained jobs are queued either way, because the denominator
    comes from the queue (F258) and "none succeeded" over nothing attempted
    is not a result.

    `conditioned_states` overrides the five conditioned failures, which are
    what the arm had done when this fixture was written and are not what it
    must always have done: F333 needed a conditioned success and the
    fixture could not express one. `samples` writes `results_tier2.jsonl`,
    which is where F306 reads the recorded sample count.
    """
    campaign = tmp_path / "campaign_f268"
    campaign.mkdir()
    pair = "bench06_RBM39_DCAF15"
    queue, state = [], []
    for conditioning in ("conditioned", "unconstrained"):
        for seed in range(1, 6):
            job = f"{pair}__ternary__{conditioning}__seed{seed}__tier2"
            queue.append({"job_id": job, "pair_id": pair, "tokens": 1223})
    if conditioned_states is None:
        conditioned_states = {
            f"{pair}__ternary__conditioned__seed{seed}__tier2":
                ["failed: exit 0 but no confidence JSON written"]
            for seed in range(1, 6)}
    # A `running` or `abandoned` row carries no `seconds` in the real
    # files: the runner writes the duration when the job settles, and an
    # abandoned job never does. The fixture gave every row one, which made
    # a running job look like a measured one and would have hidden a
    # predicate reading a duration off a job still in flight.
    for source, default in ((conditioned_states, 9492.0),
                            (unconstrained_states, 9400.0)):
        for job, states in source.items():
            for status in states:
                row = {"job_id": job, "status": status}
                if status not in ("running", "abandoned"):
                    row["seconds"] = default
                else:
                    # Now, not a fixed instant in the past. A constant here
                    # made every running row look hours old, which turned
                    # F334's empty-case test into a refutation: a fixture
                    # detail deciding a verdict. Tests that want an old job
                    # set `started_at` themselves.
                    row["started_at"] = time.time()
                state.append(row)
    _write(campaign / "queue_tier2.jsonl", queue)
    _write(campaign / "state_tier2.jsonl", state)
    if samples:
        _write(campaign / "results_tier2.jsonl",
               [{"job_id": job, "diffusion_samples": count}
                for job, count in samples.items()])
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


def test_an_abandoned_job_is_not_an_attempt(tmp_path):
    """The runner writes `abandoned` with no seconds when it closes out a
    job a previous runner left running, which is what happens to whatever
    was on the GPU when a chain is killed (F330).

    F268's claim is that every bench06 refinement fails. An abandonment is
    an outcome that did not happen, so counting it among the failures would
    let the prediction be scored "supported" on four real failures and one
    kill.
    """
    states = {
        "bench06_RBM39_DCAF15__ternary__unconstrained__seed1__tier2":
            ["failed: exit 0 but no confidence JSON written"],
        "bench06_RBM39_DCAF15__ternary__unconstrained__seed2__tier2":
            ["abandoned"],
    }
    verdict = _module().f268_refinement_size_limit(_bench06(tmp_path, states))
    assert verdict["status"] == "not yet testable", verdict
    assert verdict["unconstrained_attempted"] == 1, verdict
    assert verdict["abandoned_not_counted"] == [
        "bench06_RBM39_DCAF15__ternary__unconstrained__seed2__tier2"], verdict


def test_an_abandoned_job_cannot_make_the_prediction_supported(tmp_path):
    """Four failures and one kill must not read as five of five."""
    states = {
        f"bench06_RBM39_DCAF15__ternary__unconstrained__seed{seed}__tier2":
            ["failed: exit 0 but no confidence JSON written"]
        for seed in range(1, 5)
    }
    states["bench06_RBM39_DCAF15__ternary__unconstrained__seed5__tier2"] = \
        ["abandoned"]
    verdict = _module().f268_refinement_size_limit(_bench06(tmp_path, states))
    assert verdict["status"] == "not yet testable", verdict
    assert verdict["unconstrained_attempted"] == 4, verdict


def test_the_excluded_jobs_are_named_rather_than_silently_dropped():
    """A count that quietly shrinks is the shape this fix is about, so the
    verdict carries which jobs it set aside."""
    import ast

    source = (ROOT / "tools" / "check_registered.py").read_text()
    tree = ast.parse(source)
    function = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef)
                    and node.name == "f268_refinement_size_limit")
    body = ast.unparse(function)
    assert "abandoned_not_counted" in body
    assert "NOT_AN_OUTCOME" in body


def test_f306_does_not_count_an_abandoned_reduced_attempt(tmp_path):
    """F330's exclusion, here with the opposite consequence (F330b).

    An abandoned reduced attempt counted as a failure would score F306
    WRONG on a job that was killed rather than one that failed. The same
    hole scored *for* me in F268 and would score *against* me here, which is
    the clearest evidence that neither direction was reasoned about.
    """
    campaign = _bench06_reduced(tmp_path, {
        "bench06_RBM39_DCAF15__ternary__unconstrained__seed1__tier2":
            ("abandoned", 9),
    })
    verdict = _module().f306_reduced_sampling_succeeds(campaign)
    assert verdict["status"] == "not yet testable", verdict
    assert verdict["abandoned_not_counted"] == [
        "bench06_RBM39_DCAF15__ternary__unconstrained__seed1__tier2"], verdict


def test_f306_still_scores_a_real_reduced_failure(tmp_path):
    """The exclusion must not swallow the falsifier: a job that genuinely
    failed at a reduced count is exactly what makes F306 wrong."""
    campaign = _bench06_reduced(tmp_path, {
        f"bench06_RBM39_DCAF15__ternary__unconstrained__seed{seed}__tier2":
            ("failed: exit 0 but no confidence JSON written", 9)
        for seed in range(1, 4)
    })
    verdict = _module().f306_reduced_sampling_succeeds(campaign)
    assert verdict["status"] == "WRONG", verdict
    assert verdict["reduced_attempts"] == 3, verdict


def test_both_predictions_share_one_exclusion_list():
    """Two copies would drift, and the two holes were identical."""
    module = _module()
    assert module.NOT_AN_OUTCOME == ("running", "abandoned")
    source = (ROOT / "tools" / "check_registered.py").read_text()
    assert source.count('= ("running", "abandoned")') == 1
    assert source.count("NOT_AN_OUTCOME") >= 3


# F333. Both predicates scored the unconstrained arm only, and F268's claim
# is "whatever its conditioning". The job in flight when this was noticed
# was the conditioned one, so a success would have been reported as "not
# yet testable" by both.

CONDITIONED = "bench06_RBM39_DCAF15__ternary__conditioned__seed1__tier2"
FAILED = "failed: exit 0 but no confidence JSON written"


def test_f268_is_wrong_when_a_conditioned_job_completes(tmp_path):
    """The hole, and the conclusion it licenses.

    Not the same conclusion as an unconstrained success. That one would
    mean the pocket constraint was the cause. This job carries the
    constraint *and* the 1,223 tokens and finished anyway, so neither is,
    and what is left is the sample count.
    """
    conditioned = {CONDITIONED: ["done"]}
    for seed in range(2, 6):
        conditioned[
            f"bench06_RBM39_DCAF15__ternary__conditioned__seed{seed}__tier2"
        ] = [FAILED]
    verdict = _module().f268_refinement_size_limit(
        _bench06(tmp_path, {}, conditioned_states=conditioned))
    assert verdict["status"] == "WRONG", verdict
    assert verdict["conditioned_done"] == [CONDITIONED], verdict
    assert "sample count" in verdict["detail"], verdict
    assert "F306" in verdict["detail"], verdict


def test_f268_still_needs_the_queue_before_it_is_supported(tmp_path):
    """The widening goes one way only.

    A claim of mine must not become easier to affirm because I edited its
    scorer while its deciding job was running. The bar for `supported` is
    still the five queued unconstrained jobs, so a campaign where every
    conditioned job failed and no unconstrained job has run is still not
    testable rather than supported.
    """
    verdict = _module().f268_refinement_size_limit(_bench06(tmp_path, {}))
    assert verdict["status"] == "not yet testable", verdict
    assert verdict["conditioned_attempted"] == 5, verdict


def test_f306_counts_a_reduced_conditioned_attempt(tmp_path):
    """The same widening, and here it is symmetric.

    F306 reports `supported` on the first success and `WRONG` on the first
    failure, so admitting the conditioned arm admits evidence in both
    directions equally. Both directions are asserted, in this test and the
    next.
    """
    verdict = _module().f306_reduced_sampling_succeeds(
        _bench06(tmp_path, {},
                 conditioned_states={CONDITIONED: ["done"]},
                 samples={CONDITIONED: 9}))
    assert verdict["status"] == "supported", verdict
    assert verdict["done"] == [CONDITIONED], verdict


def test_f306_is_wrong_on_a_reduced_conditioned_failure(tmp_path):
    verdict = _module().f306_reduced_sampling_succeeds(
        _bench06(tmp_path, {},
                 conditioned_states={CONDITIONED: [FAILED]},
                 samples={CONDITIONED: 9}))
    assert verdict["status"] == "WRONG", verdict
    assert "needs replacing" in verdict["detail"], verdict


def test_f306_ignores_a_conditioned_attempt_at_the_full_count(tmp_path):
    """The exclusion that was already there, still there after the widening.

    An attempt at 25 samples failing again says nothing about whether nine
    would have worked, and the five conditioned failures already recorded
    are all at the full count.
    """
    verdict = _module().f306_reduced_sampling_succeeds(
        _bench06(tmp_path, {},
                 conditioned_states={CONDITIONED: [FAILED]},
                 samples={CONDITIONED: 25}))
    assert verdict["status"] == "not yet testable", verdict
    assert "either conditioning" in verdict["detail"], verdict


def test_the_two_falsifiers_both_say_either_conditioning():
    """The text is what a reader checks the verdict against.

    A scorer widened without its falsifier text is a prediction whose
    stated bar and actual bar differ, which is the defect F333 is.
    """
    module = _module()
    campaign = ROOT / "campaigns"
    live = sorted(campaign.glob("campaign_*"))
    if not live:
        import pytest
        pytest.skip("no campaign on this checkout")
    for predicate in (module.f268_refinement_size_limit,
                      module.f306_reduced_sampling_succeeds):
        verdict = predicate(live[-1])
        assert "either conditioning" in verdict["falsifier"], verdict


# F334. The clock rather than the confidence JSON: a 64 per cent cut in
# diffusion samples against six full-sample attempts that agree to 0.9 per
# cent. Scoreable whether the job succeeds or fails, which is what makes it
# worth registering separately from F268 and F306.

def test_f334_is_supported_when_the_reduced_job_lands_in_the_band(tmp_path):
    module = _module()
    inside = module.F334_BASELINE_SECONDS
    campaign = _bench06(
        tmp_path, {},
        conditioned_states={CONDITIONED: [FAILED]},
        samples={CONDITIONED: 9})
    # The fixture writes 9492.0 for a conditioned row, which is inside the
    # band by construction. Asserted rather than assumed.
    verdict = module.f334_sampling_buys_no_time(campaign)
    assert verdict["status"] == "supported", verdict
    low, high = verdict["band_seconds"]
    assert low < 9492.0 < high, (low, high, inside)
    assert "F331" in verdict["detail"], verdict


def test_f334_is_wrong_when_the_reduced_job_runs_long(tmp_path):
    """The content of the claim is the upper bound.

    The lower one was nearly spent when F334 was written, since the job was
    already at 9,037 seconds against a fastest-ever of 9,440.
    """
    module = _module()
    campaign = _bench06(tmp_path, {},
                        conditioned_states={CONDITIONED: [FAILED]},
                        samples={CONDITIONED: 9})
    rows = [json.loads(line) for line
            in (campaign / "state_tier2.jsonl").read_text().splitlines()
            if line.strip()]
    for row in rows:
        if row["job_id"] == CONDITIONED:
            row["seconds"] = 14000.0
    _write(campaign / "state_tier2.jsonl", rows)
    verdict = module.f334_sampling_buys_no_time(campaign)
    assert verdict["status"] == "WRONG", verdict
    assert verdict["outside_band"] == [CONDITIONED], verdict
    assert "something else" in verdict["detail"], verdict


def test_f334_is_scoreable_on_a_failure_as_well_as_a_success(tmp_path):
    """This is about the clock, not the confidence JSON.

    F268 and F306 both turn on whether a confidence JSON was written, so a
    failed job tells them one thing and a successful one the opposite. A
    duration is a duration either way, and the fixture above uses a failed
    row deliberately. Here is the other half.
    """
    module = _module()
    campaign = _bench06(tmp_path, {},
                        conditioned_states={CONDITIONED: ["done"]},
                        samples={CONDITIONED: 9})
    verdict = module.f334_sampling_buys_no_time(campaign)
    assert verdict["status"] == "supported", verdict


def test_f334_ignores_an_attempt_at_the_full_sample_count(tmp_path):
    """The six are the baseline, not the measurement.

    Scoring them against their own mean would report `supported` on the
    evidence the claim was built from, which is the shape of a prediction
    that cannot fail.
    """
    module = _module()
    verdict = module.f334_sampling_buys_no_time(
        _bench06(tmp_path, {},
                 conditioned_states={CONDITIONED: [FAILED]},
                 samples={CONDITIONED: 25}))
    assert verdict["status"] == "not yet testable", verdict
    assert "recorded duration" in verdict["detail"], verdict


def test_f334_says_so_when_no_reduced_attempt_has_a_duration(tmp_path):
    """The empty answer, given its own shape.

    A reduced attempt that is still running has no `seconds`, and so does
    one that was abandoned. Reporting `supported` over zero measurements
    would be the F321 to F324 pattern inside a predicate whose whole job is
    to report a measurement.
    """
    module = _module()
    verdict = module.f334_sampling_buys_no_time(
        _bench06(tmp_path, {},
                 conditioned_states={CONDITIONED: ["running"]},
                 samples={CONDITIONED: 9}))
    assert verdict["status"] == "not yet testable", verdict
    assert "reduced_durations" not in verdict, verdict


def test_f334_is_in_the_registry():
    """A prediction that is not in the print-out is one I grade myself."""
    source = (ROOT / "tools" / "check_registered.py").read_text()
    assert "f334_sampling_buys_no_time(main_campaign)" in source, (
        "F334 has a predicate and is not assembled into the verdicts, so "
        "nothing scores it"
    )


def test_f334_lists_the_six_durations_it_averages():
    """The mean is a number in the source and the six are how it is checked.

    `9512.0` with nothing beside it is a figure a reader has to trust. The
    six are listed in the comment above it, and 9,512 is their mean to the
    nearest second.
    """
    source = (ROOT / "tools" / "check_registered.py").read_text()
    for duration in ("9,440", "9,468", "9,492", "9,534", "9,536", "9,602"):
        assert duration in source, duration
    six = [9440, 9468, 9492, 9534, 9536, 9602]
    assert round(sum(six) / len(six)) == 9512
    assert _module().F334_BASELINE_SECONDS == 9512.0


def test_f334_is_refuted_by_a_running_job_already_past_the_band(tmp_path):
    """"Undecided" and "decided against me" had the same shape.

    The job passed 9,797 seconds still running, which refutes the claim
    whatever it does next, and the verdict said "not yet testable" because
    no `seconds` had been written. A running job's duration can only grow,
    so reading it can falsify this and can never support it, and that
    asymmetry is what makes reading it safe rather than a way of grading my
    own prediction early.
    """
    import time

    module = _module()
    campaign = _bench06(tmp_path, {},
                        conditioned_states={CONDITIONED: ["running"]},
                        samples={CONDITIONED: 9})
    rows = [json.loads(line) for line
            in (campaign / "state_tier2.jsonl").read_text().splitlines()
            if line.strip()]
    for row in rows:
        if row["job_id"] == CONDITIONED and row["status"] == "running":
            row["started_at"] = time.time() - 12000.0
    _write(campaign / "state_tier2.jsonl", rows)

    verdict = module.f334_sampling_buys_no_time(campaign)
    assert verdict["status"] == "WRONG", verdict
    assert CONDITIONED in verdict["running_past_the_band"], verdict
    assert "whatever it does next" in verdict["detail"], verdict


def test_f334_is_not_supported_by_a_running_job_inside_the_band(tmp_path):
    """The other half of the asymmetry, and the one that matters.

    A job an hour into a 2.6-hour run is inside the band trivially, and
    reporting `supported` on that would score the prediction before the
    evidence existed. Only a settled duration can support it.
    """
    import time

    module = _module()
    campaign = _bench06(tmp_path, {},
                        conditioned_states={CONDITIONED: ["running"]},
                        samples={CONDITIONED: 9})
    rows = [json.loads(line) for line
            in (campaign / "state_tier2.jsonl").read_text().splitlines()
            if line.strip()]
    for row in rows:
        if row["job_id"] == CONDITIONED and row["status"] == "running":
            row["started_at"] = time.time() - 3600.0
    _write(campaign / "state_tier2.jsonl", rows)

    verdict = module.f334_sampling_buys_no_time(campaign)
    assert verdict["status"] == "not yet testable", verdict


def test_f334_reads_a_running_jobs_sample_count_from_the_runner(tmp_path):
    """Not from arithmetic repeated in the scorer.

    `results_tier2.jsonl` is written on success, so a running job has no
    recorded sample count and the scorer has to work out what the runner
    gave it. Repeating `budget // tokens` here would be a second copy of
    the number, which is F181: the scorer could then disagree with what the
    runner actually did and the verdict would be about the copy.
    """
    module = _module()
    source = (ROOT / "tools" / "check_registered.py").read_text()
    assert "from nobble.execute.runner import sampling_for" in source, (
        "the scorer no longer asks the runner what it would have done"
    )
    assert "//" not in source.split("_reduced_samples")[1].split("def ")[1], (
        "the scorer appears to compute a sample count itself"
    )
    campaign = _bench06(tmp_path, {},
                        conditioned_states={CONDITIONED: ["running"]})
    # 1,223 tokens is over the configured budget, so the runner reduces it
    # and `_reduced_samples` must report the reduced figure rather than 25.
    from nobble import paths
    asked = int(paths.tuning()["campaign"]["tier2_diffusion_samples"])
    got = module._reduced_samples(campaign, CONDITIONED)
    assert got is not None and got < asked, (got, asked)
