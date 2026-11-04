"""Spec 2.2 wants a SMILES fallback visible in the results table.

    Prefer CCD codes over SMILES ... Fall back to `smiles:` only when no
    CCD match exists, and flag those jobs in the manifest so the difference
    is visible in the results table.

The manifest did flag it. The queue row carries `ligand_encoding: smiles`
and `flags: ['smiles_fallback']`, and the summary records twenty warnings
reading "no CCD match: encoded as SMILES and flagged". None of it reached
the table, because `aggregate` built pair-level metrics without carrying
the encoding across, so the scored record's `ligand_encoding` was null and
the table had nothing to show.

Which matters because the two are not interchangeable. A CCD-resolved
ligand's chemistry is the wwPDB component dictionary's and travels freely;
a SMILES fallback's is PROTAC-DB's, is withheld from every published
record (F22), and is the less canonical of the two. Spec 2.2 asks for that
difference to be on the page and it was one join away from being
unknowable.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEMPLATE = ROOT / "nobble" / "app" / "templates" / "campaign.html"


def _job(job_id, encoding, flags, ligand_key="85C"):
    return {
        "job_id": job_id, "pair_id": "p1", "seed": 1, "tokens": 400,
        "tier_setting": 1, "complex_type": "ternary",
        "conditioning": "unconstrained", "construct": "CRBN_CULT",
        "e3_gene": "CRBN", "peptide_id": "pep", "tier": "benchmark",
        "ligand_key": ligand_key, "ligand_encoding": encoding, "flags": flags,
        "confidence": {"pair_chains_iptm": {"0": {"1": 0.5}, "1": {"0": 0.5}}},
    }


def _aggregate(tmp_path, jobs):
    from nobble.score import metrics

    path = tmp_path / "results.jsonl"
    path.write_text("\n".join(json.dumps(j) for j in jobs) + "\n")
    pairs = metrics.aggregate(path)
    assert len(pairs) == 1
    return pairs[0]


def test_the_encoding_survives_aggregation(tmp_path):
    """The join that was missing."""
    pair = _aggregate(tmp_path, [
        _job("j1", "smiles", ["smiles_fallback"]),
        _job("j2", "smiles", ["smiles_fallback"]),
    ])
    assert pair.ligand_encoding == "smiles"
    assert pair.ligand_flags == ["smiles_fallback"]


def test_a_ccd_resolved_pair_says_so(tmp_path):
    pair = _aggregate(tmp_path, [_job("j1", "ccd", [])])
    assert pair.ligand_encoding == "ccd"
    assert pair.ligand_flags == []


def test_the_encoding_is_taken_from_the_arm_that_has_one(tmp_path):
    """A binary job carries neither a ligand nor an encoding, exactly as it
    carries no ligand_key, so the pair's value comes from the ternary arm."""
    binary = _job("j1", None, [])
    binary["complex_type"] = "binary"
    binary["ligand_key"] = None
    pair = _aggregate(tmp_path, [binary, _job("j2", "smiles", ["smiles_fallback"])])
    assert pair.ligand_encoding == "smiles"
    assert pair.ligand_key == "85C"


def test_flags_are_merged_across_the_pairs_jobs(tmp_path):
    """One job flagged and another not still means the pair is flagged."""
    pair = _aggregate(tmp_path, [
        _job("j1", "smiles", ["smiles_fallback"]),
        _job("j2", "smiles", ["token_cap_declared_exception"]),
    ])
    assert pair.ligand_flags == ["smiles_fallback", "token_cap_declared_exception"]


def _run_ligand_cell(rows):
    """Run the template's own ligandCell helper under node (F50)."""
    source = TEMPLATE.read_text()
    match = re.search(r"const ligandCell = p => \{.*?\n  \};\n", source, re.S)
    assert match, "ligandCell is no longer a named helper in campaign.html"
    script = match.group(0) + "console.log(JSON.stringify(" \
        + json.dumps(rows) + ".map(ligandCell)));"
    completed = subprocess.run(["node", "-e", script], capture_output=True,
                               text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_the_table_marks_a_smiles_fallback_and_only_that():
    """Six of seven benchmark pairs resolve to a CCD, so a column of blanks
    would be worse than a mark on the exception."""
    ccd, smiles, missing = _run_ligand_cell([
        {"ligand_key": "85C", "ligand_encoding": "ccd"},
        {"ligand_key": "dBET57", "ligand_encoding": "smiles"},
        {"ligand_key": None, "ligand_encoding": None},
    ])
    assert ccd == "85C", ccd
    assert "SMILES" in smiles and "dBET57" in smiles, smiles
    assert "SMILES" not in ccd
    assert "SMILES" not in missing


def test_the_mark_says_why_it_matters():
    """Not a bare label: a reader has to be able to tell what the fallback
    costs, which is that the chemistry is PROTAC-DB's and withheld."""
    (marked,) = _run_ligand_cell([
        {"ligand_key": "dBET57", "ligand_encoding": "smiles"},
    ])
    assert "No CCD match" in marked
    assert "PROTAC-DB" in marked
    assert "withheld" in marked


def test_the_live_benchmark_pair_is_marked():
    """bench03_BRD4_CRBN is the real one: dBET57 has no CCD entry."""
    from nobble.score import metrics

    results = ROOT / "campaigns" / "benchmark_20261103T192126Z" / "results.jsonl"
    if not results.exists():
        pytest.skip("no benchmark campaign on this checkout")

    pairs = {pair.pair_id: pair for pair in metrics.aggregate(results)}
    pair = pairs.get("bench03_BRD4_CRBN")
    if pair is None:
        pytest.skip("bench03 not scored on this checkout")
    assert pair.ligand_encoding == "smiles"
    assert "smiles_fallback" in pair.ligand_flags

    (cell,) = _run_ligand_cell([
        {"ligand_key": pair.ligand_key, "ligand_encoding": pair.ligand_encoding},
    ])
    assert "SMILES" in cell
