"""F252 names positions; the scan has to have scanned them.

F251 was registered against a measurement that could not exist, and the
lesson was to check the measurement before trusting the prediction. F252
claims the most sensitive alanine-scan position falls in {5, 6, 7} and is
refuted if it falls in {1, 2, 12, 13, 14, 15}. No `scan_profile.json` has ever
been written, so the whole claim rests on a stage that has not run.

Checked against the queued scan rather than waited for: 16 peptides, all
15-mers, one parent and 15 variants differing from it at exactly one position
each, covering 1 to 15 with no gaps. Every position F252 names is scanned, so
the prediction is answerable in both directions (F264).

Also checked: zinc is absent from the parent and from all 15 variants in both
arms. The parent is IKZF1's ZF2 degron, PFQCNQCGASFTQKG, with cysteines at 4
and 7, and position 7 is in F252's supported set. Had the motif detector added
zinc to the parent and not to C4A and C7A, those two lifts would have measured
the loss of a cofactor rather than the loss of a CRBN contact, in exactly the
position the prediction is about. It does not: the scan is zinc-free
throughout, so the comparison is internally consistent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml as yaml_lib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

F252_SUPPORTED = (5, 6, 7)
F252_REFUTED = (1, 2, 12, 13, 14, 15)


def _scan() -> tuple[str, dict[int, tuple[str, str]], list[dict]] | None:
    """(parent sequence, {position: (wild type, mutant)}, queue rows)."""
    for directory in sorted((ROOT / "campaigns").glob("design_*"),
                            reverse=True):
        queue = directory / "queue.jsonl"
        if not queue.exists():
            continue
        rows = [json.loads(line) for line in queue.read_text().splitlines()
                if line.strip()]
        sequences = {row["peptide_id"]: row["peptide_sequence"] for row in rows}
        parents = [row["peptide_id"] for row in rows
                   if row.get("peptide_label") == "degraded"]
        if not parents or not sequences:
            continue
        parent = sequences[parents[0]]
        covered: dict[int, tuple[str, str]] = {}
        for peptide_id, sequence in sequences.items():
            if peptide_id == parents[0] or len(sequence) != len(parent):
                continue
            differ = [(i + 1, parent[i], sequence[i])
                      for i in range(len(parent)) if sequence[i] != parent[i]]
            if len(differ) == 1:
                position, wild, mutant = differ[0]
                covered[position] = (wild, mutant)
        return parent, covered, rows
    return None


def test_every_position_f252_names_is_scanned():
    scan = _scan()
    if scan is None:
        pytest.skip("no design campaign assembled")
    parent, covered, _ = scan
    missing = sorted(set(F252_SUPPORTED + F252_REFUTED) - set(covered))
    assert not missing, (
        f"F252 names position(s) {missing} that the scan does not cover, so "
        "the prediction cannot be answered there")


def test_the_scan_covers_every_position_once():
    """One substitution per position, and no position twice.

    `scan_profile` keys `by_position` by position, so a second variant at the
    same position would silently replace the first and leave a gap
    elsewhere.
    """
    scan = _scan()
    if scan is None:
        pytest.skip("no design campaign assembled")
    parent, covered, _ = scan
    assert sorted(covered) == list(range(1, len(parent) + 1)), (
        f"covered {sorted(covered)} of 1..{len(parent)}")


def test_the_scan_is_zinc_consistent_between_parent_and_variants():
    """A cofactor in one and not the other would confound the lift.

    Lift is delta_iptm(variant) minus delta_iptm(parent), so a zinc present
    for the parent and absent for C4A or C7A would put the loss of a cofactor
    into the lift at those positions, and position 7 is one F252 predicts.
    """
    scan = _scan()
    if scan is None:
        pytest.skip("no design campaign assembled")
    _, _, rows = scan
    by_peptide: dict[str, set[bool]] = {}
    for row in rows:
        path = Path(row.get("yaml") or "")
        if not path.exists():
            continue
        document = yaml_lib.safe_load(path.read_text()) or {}
        zinc = any("ligand" in entry
                   and entry["ligand"].get("ccd") == "ZN"
                   for entry in document.get("sequences") or [])
        by_peptide.setdefault(row["peptide_id"], set()).add(zinc)
    if not by_peptide:
        pytest.skip("the scan's YAMLs are not on disk")
    mixed = {k: v for k, v in by_peptide.items() if len(v) > 1}
    assert not mixed, f"zinc differs between arms of the same peptide: {mixed}"
    states = {next(iter(v)) for v in by_peptide.values()}
    assert len(states) == 1, (
        "zinc is present for some peptides of the scan and absent for others, "
        "so a lift would include the cofactor: "
        f"{ {k: v for k, v in by_peptide.items()} }")
