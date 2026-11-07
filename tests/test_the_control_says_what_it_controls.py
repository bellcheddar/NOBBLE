"""The IKZF1 control is a control for the apparatus, not for noise.

The whole-domain comparison reports six pairs improving by more than 2 A, one
pair unchanged, and "control held: True". The unchanged pair is IKZF1, and it
moves 5.357 to 5.357 A: identical to three decimals.

That is not a coincidence and not a near miss. `corr04_IKZF1_CRBN` runs
`IKZF1_peptide_15mer`, PFQCNQCGASFTQKG, fifteen residues, with seeds 1 to 5,
and `bench04_IKZF1_CRBN` runs the same sequence with the same seeds. Boltz is
deterministic given an input and a seed: F219 measured fifteen re-run jobs as
ipTM bit-identical to sixteen significant figures. So an exact match is what a
sound apparatus produces.

What the control therefore rules out is a campaign-to-campaign offset in the
comparison itself, which is a real thing to rule out: the two campaigns have
different pair ids, different peptide ids, separate scoring and separate
validation, and a systematic shift anywhere in that would have moved IKZF1
too. What it does not rule out is sampling noise, because with fixed seeds
there is no sampling noise to survive. What rules that out is the size of the
six improvements, 1.7 to 39.6 A (F269).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _queue(campaign: Path) -> list[dict]:
    path = campaign / "queue.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]


def _pair(rows: list[dict], pair_id: str) -> list[dict]:
    return [row for row in rows if row.get("pair_id") == pair_id]


def _campaigns() -> tuple[Path, Path] | None:
    main = sorted((ROOT / "campaigns").glob("campaign_*"))
    corrected = sorted((ROOT / "campaigns").glob("corrected_*"))
    if not main or not corrected:
        return None
    return main[-1], corrected[-1]


def test_the_control_pair_is_the_same_peptide_and_seeds_in_both():
    """Which is why its number is identical rather than merely close."""
    found = _campaigns()
    if found is None:
        pytest.skip("need a main and a corrected campaign")
    main, corrected = found
    here = _pair(_queue(main), "bench04_IKZF1_CRBN")
    there = _pair(_queue(corrected), "corr04_IKZF1_CRBN")
    if not here or not there:
        pytest.skip("the control pair is not in both campaigns")
    assert {row["peptide_sequence"] for row in here} == {
        row["peptide_sequence"] for row in there}
    assert {row["seed"] for row in here} == {row["seed"] for row in there}
    assert all(len(row["peptide_sequence"]) == 15 for row in there), (
        "the control is no longer a 15-mer in the corrected campaign, so an "
        "exact match would no longer be the expected result")


def test_the_other_pairs_are_not_the_same_peptide():
    """Otherwise the comparison would have nothing to compare.

    The control's whole meaning is that it is the one pair held fixed while
    the others change, so this fails if a second pair is also unchanged.
    """
    found = _campaigns()
    if found is None:
        pytest.skip("need a main and a corrected campaign")
    main, corrected = found
    there = _queue(corrected)
    lengths = {}
    for row in there:
        lengths.setdefault(row["pair_id"], set()).add(
            len(row["peptide_sequence"]))
    fifteen = sorted(pair for pair, sizes in lengths.items() if sizes == {15})
    if not fifteen:
        pytest.skip("the corrected campaign has no 15-mer pair")
    assert fifteen == ["corr04_IKZF1_CRBN"], (
        f"{fifteen} are 15-mers in the corrected campaign, so more than one "
        "pair is held fixed and the comparison is not what it says")


def test_the_hold_does_not_claim_the_control_survived_noise():
    """Wording, because this output is read as the project's own account.

    "so it should not move" invites the reading that it might have moved,
    which is a claim about noise. With fixed seeds and a deterministic model
    there is no noise for it to survive, and saying otherwise overstates what
    the control establishes.
    """
    source = (ROOT / "tools" / "publication_hold.py").read_text()
    assert "apparatus agreeing with itself" in source, (
        "the control note no longer says what it controls for")
    assert "so it should not move" not in source, (
        "the control note reads as a noise control again")
