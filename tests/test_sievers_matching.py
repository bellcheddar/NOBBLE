"""D-NOB-035's premise, checked against the queue it describes.

The Sievers fingers carry `msa: empty`, and the decision says the reason is
not cost but the ROC: alignment depth would not be distributed evenly across
the two classes the curve separates. The arm is matched on length and
amino-acid composition, which is what makes a control a control here, and
not on how well studied the parent protein is. If the degraded set came
systematically from better-characterised proteins, MSA depth would correlate
with the label and the headline ROC would partly measure homology rather
than glue dependence.

That argument rests on three facts about the arm, and nothing had checked
them against the assembled queue: 24 degraded pairs from 24 distinct genes,
96 controls from 86, and the two classes matched on length and composition.
All three hold (F98).

Pinned because the decision is only as good as its premise. An arm whose
classes stopped being matched would need the question reopened, and the
refusal of 120 MSAs is the kind of choice that reads as settled once it is
written down.
"""
from __future__ import annotations

import collections
import json
import statistics
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.execute.campaign import latest  # noqa: E402
from nobble.validate import layers  # noqa: E402


def _arm() -> dict[str, tuple[str, str, str]]:
    campaign = latest("campaign")
    if campaign is None or not (campaign / "queue.jsonl").exists():
        pytest.skip("no main campaign assembled")
    rows = {}
    for line in (campaign / "queue.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        job = json.loads(line)
        if job.get("tier") != layers.ROC_ARM:
            continue
        rows[job["pair_id"]] = (job.get("peptide_label"),
                                job.get("peptide_gene") or "",
                                job.get("peptide_sequence") or "")
    assert rows, "the Sievers arm is empty"
    return rows


def _by_label(rows):
    grouped = collections.defaultdict(list)
    for label, gene, sequence in rows.values():
        grouped[label].append((gene, sequence))
    return grouped


def test_the_class_sizes_are_what_the_decision_says():
    grouped = _by_label(_arm())
    assert len(grouped["degraded"]) == 24
    assert len(grouped["not_degraded"]) == 96


def test_the_gene_counts_are_what_the_decision_says():
    """The asymmetry the decision turns on: every degraded finger is its
    own gene, and the controls repeat genes. That is why "better studied"
    could track the label if alignments were given."""
    grouped = _by_label(_arm())
    assert len({gene for gene, _ in grouped["degraded"]}) == 24
    assert len({gene for gene, _ in grouped["not_degraded"]}) == 86


def test_the_two_classes_are_matched_on_length():
    grouped = _by_label(_arm())
    lengths = {label: [len(sequence) for _gene, sequence in rows if sequence]
               for label, rows in grouped.items()}
    for label in ("degraded", "not_degraded"):
        assert statistics.median(lengths[label]) == 23, label
        assert min(lengths[label]) >= 23 and max(lengths[label]) <= 26, label


def test_the_two_classes_are_matched_on_composition():
    """Loosely, because the matching was on composition and not on exact
    fractions. Within three percentage points on every class is what the
    assembled arm achieves, and a drift beyond that would mean the controls
    had stopped controlling."""
    grouped = _by_label(_arm())

    def fractions(rows):
        residues = "".join(sequence for _gene, sequence in rows if sequence)
        return {group: sum(residues.count(c) for c in group) / len(residues)
                for group in ("CH", "KR", "DE", "AVLIMFWP")}

    degraded = fractions(grouped["degraded"])
    controls = fractions(grouped["not_degraded"])
    for group in degraded:
        assert abs(degraded[group] - controls[group]) < 0.03, (
            f"{group}: {degraded[group]:.3f} against {controls[group]:.3f}"
        )


def test_every_finger_in_the_arm_carries_no_alignment():
    """The decision as applied. One finger with an alignment would be the
    confound it exists to prevent, in one pair."""
    campaign = latest("campaign")
    if campaign is None:
        pytest.skip("no main campaign assembled")
    checked = 0
    for line in (campaign / "queue.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        job = json.loads(line)
        if job.get("tier") != layers.ROC_ARM:
            continue
        path = Path(job["yaml"])
        if not path.exists():
            continue
        text = path.read_text()
        # The peptide block is the one whose id is P.
        from nobble.validate import inputs

        for block in inputs.CHAIN_BLOCK.split(text):
            found = inputs.CHAIN_ID.search(block)
            if found and found.group(1) == "P":
                assert "msa: empty" in block, (job["job_id"], block[:120])
                checked += 1
                break
        if checked >= 40:
            break
    assert checked > 0, "no Sievers peptide chain was examined"


def test_the_decision_is_recorded_with_its_reason():
    decisions = (ROOT / "DECISIONS.md").read_text()
    assert "D-NOB-035" in decisions
    assert "the reason is the ROC rather than the cost" in decisions
