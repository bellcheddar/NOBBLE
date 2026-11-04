"""Spec 5.3 asks for two tests in the matched-control layer, not one.

    Matched-control ROC: Delta-ipTM on the Sievers degraded versus
    non-degraded split, with the Slabicki graded labels as a secondary
    continuous test

The binary split is computed. The graded one cannot be: BINMAN's
validation store holds seventeen parsed datasets and none is Slabicki's,
the name appearing only as three bibliography entries in
`references.json`, one of them the Sievers paper he co-authored. NOBBLE
consumes BINMAN's stores rather than acquiring its own.

So the layer satisfied half a requirement and looked complete, and
nothing anywhere recorded that the other half had been asked for. It now
names the missing test, on the same principle as the furniture veto in
D-NOB-010, which reports `not_computed` rather than `false` because
ProtCID was never acquired (F52, D-NOB-046).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.validate import layers  # noqa: E402


def _campaign(tmp_path, rows):
    campaign = tmp_path / "campaign_roc"
    campaign.mkdir()
    (campaign / "scores.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    return campaign


def _row(pair_id, label, delta):
    return {"pair_id": pair_id, "tier": "sievers_zf", "peptide_label": label,
            "delta_iptm": delta, "seeds_ternary": 10, "seeds_binary": 5}


def test_the_missing_secondary_test_is_named_when_the_curve_computes(tmp_path):
    rows = [_row(f"sv{i}", "degraded", 0.30 + i * 0.01) for i in range(4)]
    rows += [_row(f"nd{i}", "not_degraded", 0.10 + i * 0.01) for i in range(4)]
    layer = layers.matched_control_roc(_campaign(tmp_path, rows))

    assert layer.computed, layer.status
    secondary = layer.summary["secondary_graded_test"]
    assert secondary.startswith("not_computed:"), secondary
    assert "slabicki" in secondary.lower()


def test_it_is_named_even_when_the_curve_refuses(tmp_path):
    """The two are independent. A campaign with no matched negatives still
    has a secondary test it cannot run, and saying only one of the two
    would leave the other invisible."""
    rows = [_row(f"sv{i}", "degraded", 0.30) for i in range(4)]
    layer = layers.matched_control_roc(_campaign(tmp_path, rows))

    assert not layer.computed
    assert "slabicki" in layer.summary["secondary_graded_test"].lower()


def test_the_reason_says_why_rather_than_only_that(tmp_path):
    """"not computed" with no cause is the thing this project keeps
    finding. The reason has to distinguish "not acquired" from "failed"
    and from "not yet run"."""
    rows = [_row(f"sv{i}", "degraded", 0.30 + i * 0.01) for i in range(4)]
    rows += [_row(f"nd{i}", "not_degraded", 0.10 + i * 0.01) for i in range(4)]
    layer = layers.matched_control_roc(_campaign(tmp_path, rows))
    secondary = layer.summary["secondary_graded_test"]
    assert "unavailable" in secondary
    assert "did not acquire" in secondary or "not acquire" in secondary
    assert "binary only" in secondary


def test_the_dataset_really_is_absent_from_binman():
    """The premise of the decision, checked rather than asserted. If the
    data is ever acquired this fails, which is the reminder to implement
    the secondary test rather than leave the note standing."""
    from nobble.curate import binman_store as store

    candidates = ("slabicki_graded", "slabicki", "graded_degradation")
    found = []
    for name in candidates:
        try:
            rows = store.dataset(name)
        except Exception:                   # noqa: BLE001
            continue
        if rows:
            found.append(name)
    assert not found, (
        f"BINMAN now holds {found}, so spec 5.3's secondary continuous test "
        "can be implemented and D-NOB-046 should go"
    )


def test_the_decision_is_recorded():
    """An unimplementable requirement with no record is the gap this
    closes; the record is the fix as much as the field is."""
    decisions = (ROOT / "DECISIONS.md").read_text()
    assert "D-NOB-046" in decisions
    assert "Slabicki" in decisions or "Słabicki" in decisions
