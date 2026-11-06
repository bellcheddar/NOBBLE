"""Tier 2 must refine at least one pair that has a deposited structure.

F212: the top decile took sixteen pairs by `nobble_score` and not one of them
had a crystal to compare against, so the refinement produced no RMSD against
ground truth. Pose recovery had failed on the benchmark panel (0 of 65 poses
within 3 A, median 17.54 A, in frames verified at 0.54 to 1.88 A), and
refinement was the one untested rung of the fallback ladder. It could not be
tested with the compute it was already spending.

These tests are about measurability, not about the decile: a refinement whose
effect on pose accuracy cannot be measured is not a cheaper refinement.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nobble.execute import tier2
from nobble.validate.layers import RECOVERY_TARGETS, recovery_target


def _score_row(pair_id: str, score: float, **extra) -> dict:
    row = {
        "pair_id": pair_id,
        "nobble_score": score,
        "e3_gene": pair_id.split("_")[-1],
        "peptide_gene": pair_id.split("_")[1] if "_" in pair_id else pair_id,
        "tier": "candidate",
    }
    row.update(extra)
    return row


def test_a_pair_with_a_crystal_is_carried_even_when_it_does_not_rank():
    # Twenty candidates all scoring above the benchmark pair. A decile of two
    # cannot reach it, which is the shape the live campaign had.
    rows = [_score_row(f"sv_pos_FAKE{i:02d}_CRBN", 0.9 - i * 0.001)
            for i in range(20)]
    bench = next(iter(RECOVERY_TARGETS))
    rows.append(_score_row(bench, 0.1))

    controls = tier2.recovery_controls_for(rows, already=set())
    assert [item["pair_id"] for item in controls] == [bench]
    assert controls[0]["role"] == "recovery_control"
    assert controls[0]["pdb_id"] == RECOVERY_TARGETS[bench]["pdb_id"]


def test_a_pair_already_in_the_decile_is_not_carried_twice():
    bench = next(iter(RECOVERY_TARGETS))
    rows = [_score_row(bench, 0.99)]
    assert tier2.recovery_controls_for(rows, already={bench}) == []


def test_the_controls_are_not_counted_as_decile_members(tmp_path: Path):
    # pairs_selected and arms describe the decile. Adding controls to them
    # would make "the top decile" mean something else, which is the trap the
    # separate list exists to avoid.
    campaign = tmp_path / "campaign_x"
    campaign.mkdir()
    rows = [_score_row(f"sv_pos_FAKE{i:02d}_CRBN", 0.9 - i * 0.001)
            for i in range(20)]
    rows += [_score_row(pair_id, 0.1) for pair_id in RECOVERY_TARGETS]
    (campaign / "scores.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows))

    selection = tier2.select_top_decile(campaign)
    assert selection.status == "selected"
    assert selection.pairs_selected == len(selection.selected)
    chosen = {item["pair_id"] for item in selection.selected}
    carried = {item["pair_id"] for item in selection.recovery_controls}
    assert chosen.isdisjoint(carried)
    assert carried == set(RECOVERY_TARGETS)
    assert sum(selection.arms.values()) == selection.pairs_selected


def test_the_selection_says_so_when_nothing_has_a_crystal(tmp_path: Path):
    # The absence is stated rather than left as an empty list for a reader to
    # interpret: it is a property of the campaign, not of the selector.
    campaign = tmp_path / "campaign_y"
    campaign.mkdir()
    rows = [_score_row(f"sv_pos_FAKE{i:02d}_CRBN", 0.9 - i * 0.001)
            for i in range(20)]
    (campaign / "scores.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows))

    selection = tier2.select_top_decile(campaign)
    assert selection.recovery_controls == []
    assert any("no pair in this campaign has a deposited structure" in note
               for note in selection.notes), selection.notes


def test_the_queue_refines_the_controls_and_puts_them_first(tmp_path: Path):
    campaign = tmp_path / "campaign_z"
    campaign.mkdir()
    bench = sorted(RECOVERY_TARGETS)[0]
    decile = "sv_pos_FAKE00_CRBN"
    # Deliberately written with the decile pair first, so passing cannot come
    # from the source order.
    queue = []
    for pair_id in (decile, bench):
        for seed in (1, 2):
            queue.append({
                "job_id": f"{pair_id}__ternary__conditioned__seed{seed}",
                "pair_id": pair_id, "complex_type": "ternary",
                "tokens": 150, "seed": seed,
            })
        queue.append({
            "job_id": f"{pair_id}__binary__unconstrained__seed1",
            "pair_id": pair_id, "complex_type": "binary",
            "tokens": 100, "seed": 1,
        })
    (campaign / "queue.jsonl").write_text(
        "".join(json.dumps(job) + "\n" for job in queue))

    selection = tier2.Selection(
        campaign=campaign.name, ranking_key="nobble_score", decile_fraction=0.1,
        pairs_considered=2, pairs_selected=1,
        selected=[{"pair_id": decile, "rank": 1}],
        recovery_controls=[{"pair_id": bench, "role": "recovery_control"}],
    )
    report = tier2.build_tier2_queue(campaign, selection)

    assert report["status"] == "built"
    assert report["recovery_control_pairs"] == [bench]
    assert report["decile_pairs"] == [decile]
    assert report["jobs_by_role"] == {"decile": 2, "recovery_control": 2}

    written = [json.loads(line) for line
               in (campaign / "queue_tier2.jsonl").read_text().splitlines()]
    # Ternary only, as tier 2 has always been.
    assert all(job["complex_type"] == "ternary" for job in written)
    # The controls come first, so the question they answer is answered first.
    assert [job["tier2_role"] for job in written] == (
        ["recovery_control"] * 2 + ["decile"] * 2)
    assert all(job["tier_setting"] == 2 for job in written)


@pytest.mark.parametrize("pair_id", sorted(RECOVERY_TARGETS))
def test_every_recovery_target_resolves_to_a_deposition(pair_id: str):
    # recovery_controls_for trusts recovery_target. If a target ever loses its
    # chains, the control would be carried and then measure nothing.
    target = recovery_target(pair_id)
    assert target is not None
    for field in ("pdb_id", "substrate_chain", "substrate_acc",
                  "receptor_chain", "receptor_acc"):
        assert target.get(field), f"{pair_id} has no {field}"


def test_the_controls_run_cheapest_first(tmp_path: Path):
    """Breadth before depth across the control panel.

    One control on the live campaign costs 11.66 h of the 18.80 h the panel
    costs in total. In pair-id order it ran sixth of seven, so the two pairs
    behind it reported most of a day late, for no gain: the question the panel
    answers is how many pairs refinement helps on.
    """
    campaign = tmp_path / "campaign_order"
    campaign.mkdir()
    targets = sorted(RECOVERY_TARGETS)[:3]
    # Deliberately inverted: the alphabetically first pair is the dearest, so
    # a pass cannot come from pair-id order.
    seconds = {targets[0]: 900.0, targets[1]: 300.0, targets[2]: 60.0}

    queue, results = [], []
    for pair_id in targets:
        job_id = f"{pair_id}__ternary__conditioned__seed1"
        queue.append({"job_id": job_id, "pair_id": pair_id,
                      "complex_type": "ternary", "tokens": 150, "seed": 1})
        results.append({"job_id": job_id, "pair_id": pair_id,
                        "complex_type": "ternary", "status": "done",
                        "seconds": seconds[pair_id], "tokens": 150, "seed": 1})
    (campaign / "queue.jsonl").write_text(
        "".join(json.dumps(job) + "\n" for job in queue))
    (campaign / "results.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in results))

    selection = tier2.Selection(
        campaign=campaign.name, ranking_key="nobble_score", decile_fraction=0.1,
        pairs_considered=3, pairs_selected=0, selected=[],
        recovery_controls=[{"pair_id": pair_id, "role": "recovery_control"}
                           for pair_id in targets],
    )
    tier2.build_tier2_queue(campaign, selection)

    written = [json.loads(line) for line
               in (campaign / "queue_tier2.jsonl").read_text().splitlines()]
    order = [job["pair_id"] for job in written]
    assert order == sorted(targets, key=lambda pair_id: seconds[pair_id]), order


def test_a_control_with_no_measured_cost_goes_last_rather_than_first(tmp_path: Path):
    """An unmeasured pair must not sort to the front as a zero.

    `tier1_worst_seconds` has no entry for a pair whose tier-1 jobs have not
    finished. Defaulting that to 0 would put the one pair whose cost is
    unknown ahead of every pair whose cost is known and small.
    """
    campaign = tmp_path / "campaign_unmeasured"
    campaign.mkdir()
    cheap, unknown = sorted(RECOVERY_TARGETS)[:2]

    queue = []
    for pair_id in (cheap, unknown):
        queue.append({"job_id": f"{pair_id}__ternary__conditioned__seed1",
                      "pair_id": pair_id, "complex_type": "ternary",
                      "tokens": 150, "seed": 1})
    (campaign / "queue.jsonl").write_text(
        "".join(json.dumps(job) + "\n" for job in queue))
    # Only the cheap pair has a measured tier-1 time.
    (campaign / "results.jsonl").write_text(json.dumps({
        "job_id": f"{cheap}__ternary__conditioned__seed1", "pair_id": cheap,
        "complex_type": "ternary", "status": "done", "seconds": 120.0,
        "tokens": 150, "seed": 1}) + "\n")

    selection = tier2.Selection(
        campaign=campaign.name, ranking_key="nobble_score", decile_fraction=0.1,
        pairs_considered=2, pairs_selected=0, selected=[],
        recovery_controls=[{"pair_id": pair_id, "role": "recovery_control"}
                           for pair_id in (cheap, unknown)],
    )
    tier2.build_tier2_queue(campaign, selection)
    written = [json.loads(line) for line
               in (campaign / "queue_tier2.jsonl").read_text().splitlines()]
    assert [job["pair_id"] for job in written] == [cheap, unknown]
