"""An alignment for the wrong receptor is worse than no alignment at all.

F39 established that the MSA policy is the highest-consequence thing in
the pipeline: dropping the receptor's cached alignment degrades every
prediction with nothing raising. This is the other half of that, and the
worse half. The cache is content-addressed, so a file's *name* matches its
sequence by construction. Its *contents* are written by a separate step,
`tools/run_msa.sh`, and nothing checked that the alignment in a given file
is the alignment of the sequence it is filed under.

A receptor handed another protein's conservation does not fail. It folds,
confidently, against the wrong evolutionary signal, and every number
downstream inherits that.

The live cache is correct: 17 files, every query line matching its key,
none empty, and all eleven sequences the constructs need usably present.
These tests keep it that way and make preflight say so before a 52-hour
run rather than after.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from nobble.curate import constructs as C  # noqa: E402
from nobble.execute import msa  # noqa: E402

import preflight as preflight_module  # noqa: E402


def _needed():
    """Every receptor sequence the constructs require, by cache key."""
    needed = {}
    for name, construct in C.CONSTRUCTS.items():
        for index, segment in enumerate(construct.segments):
            try:
                sequence = segment.sequence()
            except Exception:               # noqa: BLE001
                continue                    # InterPro unavailable here
            needed[msa.sequence_key(sequence)] = (name, index, sequence)
    return needed


def _query_of(path: Path) -> str | None:
    seen_header = False
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if seen_header:
                return None
            seen_header = True
            continue
        if seen_header:
            return line
    return None


def test_every_needed_receptor_sequence_has_a_usable_alignment():
    needed = _needed()
    if not needed:
        pytest.skip("no construct sequences resolvable on this checkout")
    missing = [f"{name} segment {index}"
               for name, index, sequence in needed.values()
               if not msa.is_cached(sequence)]
    assert not missing, f"receptor sequences with no usable cached MSA: {missing}"


def test_every_cached_alignment_is_the_alignment_of_its_own_key():
    """The check that was absent. A file named for one sequence and
    containing another's alignment passes every other test here."""
    needed = _needed()
    if not needed:
        pytest.skip("no construct sequences resolvable on this checkout")

    checked, wrong = 0, []
    for key, (name, index, sequence) in needed.items():
        path = msa.a3m_path(sequence)
        if not path.exists():
            continue
        query = _query_of(path)
        if query is None:
            wrong.append((path.name, name, index, "no query sequence"))
            continue
        gapless = query.replace("-", "").replace(".", "").upper()
        if gapless != sequence.upper():
            wrong.append((path.name, name, index,
                          f"queries {len(gapless)} residues, chain has {len(sequence)}"))
        checked += 1

    assert checked, "no cached alignment was actually compared"
    assert not wrong, f"alignment(s) filed under the wrong sequence: {wrong}"


def test_no_cached_alignment_is_empty():
    """is_cached requires a non-zero size, so a truncated file passes it.
    A header with no alignment behind it is the realistic truncation.

    The count of files read is asserted as well. Every assertion here used
    to sit inside the loop, so an empty cache satisfied the test by
    examining nothing, and an empty MSA cache is not a harmless state: F39
    showed that losing the receptor's alignment degrades every prediction
    rather than failing them (F72).
    """
    cached = sorted(msa.CACHE.glob("*.a3m"))
    for path in cached:
        lines = [l for l in path.read_text(errors="replace").splitlines() if l.strip()]
        assert len(lines) >= 2, f"{path.name} has {len(lines)} non-blank line(s)"
    assert cached, (
        "no alignment was examined, so this says nothing about whether the "
        "cached ones are intact. Phase 1 caches one per receptor chain"
    )


def test_preflight_rejects_an_alignment_belonging_to_another_protein(tmp_path):
    """The check made executable, through preflight's own helper."""
    other = tmp_path / "wrong.a3m"
    other.write_text(">query\nMMMMMMMMMMMM\n>hit1\nMMMMMMMMMMMA\n")

    problem = preflight_module._msa_query_mismatch(str(other), "ACDEFGHIKLMN")
    assert problem and "not this chain's alignment" in problem, problem

    # And accepts the right one, so it is not simply rejecting everything.
    right = tmp_path / "right.a3m"
    right.write_text(">query\nACDEFGHIKLMN\n>hit1\nACDEFGHIKLMA\n")
    assert preflight_module._msa_query_mismatch(str(right), "ACDEFGHIKLMN") is None


def test_preflight_rejects_a_same_length_substitution(tmp_path):
    """The case a length comparison alone would miss: a different protein
    of exactly the same size."""
    path = tmp_path / "same_length.a3m"
    path.write_text(">query\nMCDEFGHIKLMN\n>hit1\nMCDEFGHIKLMA\n")
    problem = preflight_module._msa_query_mismatch(str(path), "ACDEFGHIKLMN")
    assert problem and "same length" in problem, problem


def test_preflight_rejects_a_header_with_no_alignment(tmp_path):
    path = tmp_path / "headless.a3m"
    path.write_text(">query only, nothing after it\n")
    problem = preflight_module._msa_query_mismatch(str(path), "ACDEFGHIKLMN")
    assert problem and "no query sequence" in problem, problem


def test_preflight_tolerates_gapped_query_lines(tmp_path):
    """a3m query lines carry insertions as dots and gaps as dashes; the
    comparison is against the gapless residues."""
    path = tmp_path / "gapped.a3m"
    path.write_text(">query\nACDE-FGHI..KLMN\n>hit1\nACDEFGHIKLMNAAA\n")
    assert preflight_module._msa_query_mismatch(
        str(path), "ACDEFGHIKLMN") is None


def _synthetic_campaign(tmp_path, msa_path, receptor_sequence):
    """One ternary job whose receptor chain names the given alignment."""
    import json

    import yaml

    campaign = tmp_path / "campaign_synthetic"
    (campaign / "yaml").mkdir(parents=True)
    document = {
        "version": 1,
        "sequences": [
            {"protein": {"id": "A", "sequence": receptor_sequence,
                         "msa": str(msa_path)}},
            {"protein": {"id": "P", "sequence": "ACDEFGHIKLMNPQR",
                         "msa": "empty"}},
            {"ligand": {"id": "L", "ccd": "85C"}},
        ],
    }
    yaml_path = campaign / "yaml" / "j1.yaml"
    yaml_path.write_text(yaml.safe_dump(document, sort_keys=False))
    (campaign / "queue.jsonl").write_text(json.dumps({
        "job_id": "j1", "pair_id": "p1", "seed": 1, "tokens": 400,
        "complex_type": "ternary", "conditioning": "unconstrained",
        "construct": "CRBN_CULT", "yaml": str(yaml_path),
    }) + "\n")
    return campaign


def test_preflight_itself_reports_a_wrong_alignment(tmp_path):
    """The wiring, not the helper.

    A mutation that removed the call from preflight's own loop left every
    test above passing: they exercise _msa_query_mismatch directly, and a
    checked helper nobody calls is the same shape as F32's statuses that
    were computed and never displayed.
    """
    wrong = tmp_path / "wrong.a3m"
    wrong.write_text(">query\nMMMMMMMMMMMM\n>hit\nMMMMMMMMMMMA\n")
    campaign = _synthetic_campaign(tmp_path, wrong, "ACDEFGHIKLMN")

    report = preflight_module.preflight(campaign)
    problems = [e["problem"] for e in report["errors"]]
    assert any("not this chain's alignment" in p for p in problems), problems
    assert report["ok"] is False


def test_preflight_passes_a_matching_alignment(tmp_path):
    """So the test above cannot be satisfied by preflight rejecting
    everything."""
    right = tmp_path / "right.a3m"
    right.write_text(">query\nACDEFGHIKLMN\n>hit\nACDEFGHIKLMA\n")
    campaign = _synthetic_campaign(tmp_path, right, "ACDEFGHIKLMN")

    report = preflight_module.preflight(campaign)
    problems = [e["problem"] for e in report["errors"]]
    assert not any("alignment" in p for p in problems), problems
