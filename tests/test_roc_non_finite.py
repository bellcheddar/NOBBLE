"""A NaN in the headline curve would bias it, not break it.

`matched_control_roc` selected its two groups with
`isinstance(row.get(statistic), (int, float))`. NaN is a float. A NaN
reaching the Mann-Whitney estimator loses every comparison, because NaN is
neither greater than nor equal to anything, so it is scored as a unanimous
loss rather than as missing data: one NaN among three positives takes the
AUC from 1.0 to 0.667.

Python's `json` writes NaN as a bare `NaN` literal and reads it back, so a
non-finite value round-trips through `scores.jsonl` with nothing objecting.
No scored record carries one today, which is how every latent defect in this
project has looked before it fired.

`_finite` is now the filter, `_auc` refuses non-finite input rather than
returning a number, and the layer reports how many rows it dropped for this
reason, because a silent change of denominator is its own problem (F74).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.validate import layers  # noqa: E402

NAN = float("nan")
INF = float("inf")


def _campaign(tmp_path, rows):
    campaign = tmp_path / "campaign_20261104T000000Z"
    campaign.mkdir()
    (campaign / "scores.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    return campaign


def _row(pair_id, label, delta, seeds=10):
    return {"pair_id": pair_id, "tier": layers.ROC_ARM, "peptide_label": label,
            "delta_iptm": delta, "seeds_ternary": seeds, "seeds_binary": 5}


def test_a_nan_is_not_a_number_for_this_purpose():
    assert layers._finite(0.3) and layers._finite(0) and layers._finite(-1)
    assert not layers._finite(NAN)
    assert not layers._finite(INF)
    assert not layers._finite(-INF)
    assert not layers._finite(None)
    assert not layers._finite("0.3")


def test_a_bool_is_not_a_number_for_this_purpose():
    """`isinstance(True, int)` is True, so a boolean would have been
    compared as 1 and 0 against real deltas."""
    assert not layers._finite(True)
    assert not layers._finite(False)


def test_the_estimator_refuses_rather_than_returning_a_biased_number():
    """The floor under the filter. A biased AUC is indistinguishable from a
    real one, so this must raise rather than quietly score the NaN as a
    loss."""
    with pytest.raises(ValueError, match="non-finite"):
        layers._auc([0.3, 0.4, NAN], [0.1, 0.2, 0.15])
    with pytest.raises(ValueError, match="non-finite"):
        layers._auc([0.3, 0.4], [0.1, INF])


def test_the_estimator_still_scores_ties_at_a_half():
    """The property that must survive the new guard: Mann-Whitney credits a
    tie with half a win, and 0.0 against 0.0 is a realistic tie here."""
    assert layers._auc([0.0], [0.0]) == 0.5
    # 0.2 beats both; 0.0 ties one and loses to the other: 2.5 of 4.
    assert layers._auc([0.2, 0.0], [0.0, 0.1]) == 0.625


def test_a_non_finite_row_is_dropped_and_counted(tmp_path):
    """Not silently. A pair that was scored and then excluded changes the
    denominator, and a reader comparing the positive count against the
    campaign has to be able to see why."""
    rows = [_row(f"sv{i}", "degraded", 0.30 + i * 0.01) for i in range(4)]
    rows += [_row(f"nd{i}", "not_degraded", 0.10 + i * 0.01) for i in range(4)]
    rows.append(_row("svbad", "degraded", NAN))
    layer = layers.matched_control_roc(_campaign(tmp_path, rows))

    assert layer.computed, layer.status
    assert layer.summary["positives"] == 4, "the NaN row was counted as a positive"
    assert layer.summary["non_finite_dropped"] == 1


def test_a_missing_value_is_not_counted_as_non_finite(tmp_path):
    """None means the pair was never scored, which is a different thing
    from a pair whose score came back as NaN, and conflating them would
    make the dropped count meaningless."""
    rows = [_row(f"sv{i}", "degraded", 0.30 + i * 0.01) for i in range(4)]
    rows += [_row(f"nd{i}", "not_degraded", 0.10 + i * 0.01) for i in range(4)]
    rows.append(_row("svnone", "degraded", None))
    layer = layers.matched_control_roc(_campaign(tmp_path, rows))
    assert layer.summary["non_finite_dropped"] == 0
    assert layer.summary["positives"] == 4


def test_the_curve_is_unchanged_when_nothing_is_non_finite(tmp_path):
    """The guard must not move the answer on clean data."""
    rows = [_row(f"sv{i}", "degraded", 0.30 + i * 0.01) for i in range(4)]
    rows += [_row(f"nd{i}", "not_degraded", 0.10 + i * 0.01) for i in range(4)]
    layer = layers.matched_control_roc(_campaign(tmp_path, rows))
    assert layer.computed
    assert layer.summary["auc"] == 1.0
    assert layer.summary["non_finite_dropped"] == 0


def test_a_nan_cannot_reach_the_curve_through_json(tmp_path):
    """The route in. Python's json writes NaN as a bare literal and reads
    it back, so this is not hypothetical: the value survives the file."""
    text = json.dumps({"delta_iptm": NAN})
    assert "NaN" in text
    restored = json.loads(text)["delta_iptm"]
    assert isinstance(restored, float)
    assert not layers._finite(restored)


def test_the_live_scores_hold_no_non_finite_delta():
    """The premise of calling this latent. If it ever fires, the layer now
    reports it rather than absorbing it."""
    import math

    found = []
    for scores in sorted((ROOT / "campaigns").glob("*/scores.jsonl")):
        for line in scores.read_text().splitlines():
            if not line.strip():
                continue
            value = json.loads(line).get("delta_iptm")
            if isinstance(value, float) and not math.isfinite(value):
                found.append(scores.parent.name)
    assert not found, f"non-finite delta_iptm in {sorted(set(found))}"
