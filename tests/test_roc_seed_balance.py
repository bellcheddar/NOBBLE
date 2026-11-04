"""The headline curve must say how many seeds each side contributed.

Delta-ipTM is a difference of minima, and a minimum is not robust to the
number of seeds it was taken over: a minimum of ten draws sits below a
minimum of five for reasons that have nothing to do with the interface.
aggregate() already hard partitions by sampling tier for that reason, but
that says nothing about seeds lost *within* a tier, and a 2,360-job run is
expected to lose some, because the fallback ladder records a failure and
carries on by design.

Between the two groups this is bias rather than noise. If the degraded
pairs finish more seeds than their matched negatives, their minima are
pulled down relative to the negatives' and the AUC moves, with nothing in
the curve to show it.

The arm is in fact balanced today: all 120 Sievers pairs carry 10 ternary
and 5 binary jobs, and the two short pairs are benchmark and scramble,
both outside this curve's scope. That protection is incidental, which is
why it is pinned here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.validate import layers  # noqa: E402


def _row(pair_id, label, delta, seeds_ternary=10, seeds_binary=5):
    return {
        "pair_id": pair_id, "tier": "sievers_zf", "peptide_label": label,
        "delta_iptm": delta, "seeds_ternary": seeds_ternary,
        "seeds_binary": seeds_binary,
    }


def _campaign(tmp_path, rows):
    campaign = tmp_path / "campaign_roc"
    campaign.mkdir()
    (campaign / "scores.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    return campaign


def _balanced_rows():
    rows = [_row(f"sv{i}", "degraded", 0.30 + i * 0.01) for i in range(4)]
    rows += [_row(f"nd{i}", "not_degraded", 0.10 + i * 0.01) for i in range(4)]
    return rows


def test_a_balanced_arm_says_so_and_names_the_counts(tmp_path):
    layer = layers.matched_control_roc(_campaign(tmp_path, _balanced_rows()))
    assert layer.computed
    assert layer.summary["seed_balance"].startswith("balanced")
    assert "10 ternary and 5 binary" in layer.summary["seed_balance"]
    assert layer.summary["seed_counts"]["positives"]["ternary"] == {"10": 4} or \
           layer.summary["seed_counts"]["positives"]["ternary"] == {10: 4}
    # A balanced curve carries no qualifier.
    assert "imbalance" not in layer.summary["interpretation"]


def test_a_seed_lost_inside_one_group_is_named(tmp_path):
    """One failed job out of 2,360 is the realistic case."""
    rows = _balanced_rows()
    rows[0]["seeds_ternary"] = 9
    layer = layers.matched_control_roc(_campaign(tmp_path, rows))
    assert layer.computed, "one lost seed must qualify the curve, not withhold it"
    assert layer.summary["seed_balance"].startswith("uneven within a group")
    assert "imbalance" in layer.summary["interpretation"]


def test_groups_that_contributed_differently_are_named(tmp_path):
    """The bias case: every negative short by the same amount."""
    rows = _balanced_rows()
    for row in rows:
        if row["peptide_label"] == "not_degraded":
            row["seeds_ternary"] = 5
    layer = layers.matched_control_roc(_campaign(tmp_path, rows))
    assert layer.computed
    assert layer.summary["seed_balance"].startswith("uneven between groups")
    assert "imbalance" in layer.summary["interpretation"]


def test_an_empty_group_is_not_called_uneven(tmp_path):
    """Nothing to compare is not the same as a mismatch."""
    rows = [_row(f"sv{i}", "degraded", 0.3) for i in range(4)]
    layer = layers.matched_control_roc(_campaign(tmp_path, rows))
    assert not layer.computed
    assert layer.summary["seed_balance"].startswith("not assessable")


def test_the_real_sievers_arm_is_balanced_by_construction():
    """Why the live curve is safe, stated rather than assumed.

    If a future manifest gives some Sievers pairs a different number of
    ternary jobs, the curve becomes an order-statistic comparison between
    unlike pairs and this fails rather than going quiet.
    """
    import glob
    from collections import defaultdict

    queues = sorted(glob.glob(str(ROOT / "campaigns" / "campaign_*" / "queue.jsonl")))
    if not queues:
        import pytest
        pytest.skip("no main campaign assembled")

    shapes = defaultdict(lambda: {"ternary": 0, "binary": 0})
    for line in open(queues[-1]):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("tier") != "sievers_zf":
            continue
        shapes[row["pair_id"]][row["complex_type"]] += 1

    assert shapes, "no sievers_zf pairs in the main campaign"
    distinct = {(v["ternary"], v["binary"]) for v in shapes.values()}
    assert len(distinct) == 1, (
        f"Sievers pairs have differing job shapes {distinct}: Delta-ipTM minima "
        "across them are no longer comparable"
    )


def test_scores_without_seed_counts_are_not_called_uneven(tmp_path):
    """Score files written before seeds_ternary/seeds_binary existed.

    "Cannot be checked" and "checked and found uneven" are different
    claims, and only the second should qualify the curve. Getting this
    wrong attached an imbalance warning to every curve drawn from an older
    score file, which is how this case was found.
    """
    rows = []
    for index in range(4):
        row = _row(f"sv{index}", "degraded", 0.30 + index * 0.01)
        del row["seeds_ternary"], row["seeds_binary"]
        rows.append(row)
    for index in range(4):
        row = _row(f"nd{index}", "not_degraded", 0.10 + index * 0.01)
        del row["seeds_ternary"], row["seeds_binary"]
        rows.append(row)

    layer = layers.matched_control_roc(_campaign(tmp_path, rows))
    assert layer.computed
    assert layer.summary["seed_balance"].startswith("not assessable")
    assert "imbalance" not in layer.summary["interpretation"]


def test_group_sizes_differing_is_not_an_imbalance(tmp_path):
    """24 degraded against 96 matched negatives is the design, not a fault.

    The first version of this compared how many pairs held each seed
    count, so the real arm's 24-against-96 split read as uneven on every
    curve. What matters is whether a pair on one side was built like a
    pair on the other.
    """
    rows = [_row(f"sv{i}", "degraded", 0.30 + i * 0.01) for i in range(4)]
    rows += [_row(f"nd{i}", "not_degraded", 0.10 + i * 0.005) for i in range(20)]
    layer = layers.matched_control_roc(_campaign(tmp_path, rows))
    assert layer.computed
    assert layer.summary["seed_balance"].startswith("balanced")
    assert "imbalance" not in layer.summary["interpretation"]
