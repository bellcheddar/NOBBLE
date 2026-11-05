"""The published atlas said it had withheld nothing, and it had.

Spec 2.1: PROTAC-DB stays internal-use-only and is never redistributed.
`deploy/build_atlas.py` enforces that by nulling the `smiles` field of any
ligand record whose `source` is `protacdb`, and `ATLAS.json` reports how
many it withheld.

It reported 0. The key was initialised to 0 and incremented nowhere, so it
was a literal dressed as a count, and the atlas it described contained a
`smiles_withheld` field: one record had been withheld while the summary
said none had. On a licensing guarantee that reads as "no PROTAC-DB
chemistry was present", which is a stronger and different claim.

The real figure is 1, dBET57, the one benchmark ligand with no CCD entry.

The count alone is still not enough, which is why the ligands are recorded
beside it: a zero cannot distinguish "nothing needed withholding" from "the
detection stopped firing", and those need different responses (F72).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "deploy"))
from nobble.execute.campaign import latest_or_absent as _newest  # noqa: E402

import build_atlas  # noqa: E402

ATLAS = ROOT / "deploy" / "atlas"
PYTHON = str(ROOT.parent / "BINMAN" / ".pixi" / "envs" / "default" / "bin" / "python")


def _protacdb_record(ccd="dBET57"):
    return {"ccd": ccd, "source": "protacdb", "encoding": "smiles",
            "smiles": "CC1=C(C)C2=C(S1)N(C)C(=O)N2"}


def test_a_withheld_record_is_counted():
    build_atlas.reset_redactions()
    out = build_atlas.redact(_protacdb_record())
    assert out["smiles"] is None
    assert "smiles_withheld" in out
    assert build_atlas.redactions() == ["dBET57"]


def test_nothing_is_counted_when_nothing_is_withheld():
    """The other half. A counter that only ever goes up is as useless as
    one that never does."""
    build_atlas.reset_redactions()
    out = build_atlas.redact({"ccd": "85C", "source": "wwpdb",
                              "encoding": "ccd", "smiles": "CCO"})
    assert out["smiles"] == "CCO", "a wwPDB-sourced record was redacted"
    assert build_atlas.redactions() == []


def test_the_count_is_reset_between_builds():
    """Accumulating across builds would make the second atlas claim the
    first one's redactions."""
    build_atlas.reset_redactions()
    build_atlas.redact(_protacdb_record())
    assert len(build_atlas.redactions()) == 1
    build_atlas.reset_redactions()
    assert build_atlas.redactions() == []


def test_nested_records_are_counted_once_each():
    build_atlas.reset_redactions()
    build_atlas.redact({"pairs": [_protacdb_record("dBET57"),
                                  _protacdb_record("dBET6")],
                        "meta": {"ligand": _protacdb_record("dBET57")}})
    assert len(build_atlas.redactions()) == 3
    assert sorted(set(build_atlas.redactions())) == ["dBET57", "dBET6"]


def test_a_real_build_reports_a_count_that_matches_the_bundle(tmp_path):
    """End to end, into a temporary directory. The published atlas is never
    the target of a test (F66, D-NOB-051).

    The count has to agree with the bundle it describes: that agreement is
    the thing that was false, not the arithmetic.
    """
    campaign = _newest("benchmark")
    if not campaign.exists():
        pytest.skip("no benchmark campaign on this checkout")

    target = tmp_path / "atlas"
    completed = subprocess.run(
        [PYTHON, "deploy/build_atlas.py", str(campaign)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=900,
        env={**os.environ, "PYTHONPATH": str(ROOT),
             "KMP_DUPLICATE_LIB_OK": "TRUE",
             "NOBBLE_ATLAS_OUT": str(target)},
    )
    assert completed.returncode == 0, completed.stderr[-2000:]

    summary = json.loads((target / "ATLAS.json").read_text())
    withheld_fields = sum(
        path.read_text(errors="replace").count("smiles_withheld")
        for path in target.rglob("*")
        if path.is_file() and path.suffix in (".json", ".jsonl"))

    assert summary["redactions"] == withheld_fields, (
        f"ATLAS.json claims {summary['redactions']} redaction(s) and the "
        f"bundle carries {withheld_fields} withheld field(s)"
    )
    assert summary["redactions"] > 0, (
        "this campaign includes dBET57, whose chemistry is PROTAC-DB's, so a "
        "zero means the detection stopped firing rather than that there was "
        "nothing to withhold"
    )
    assert summary["redacted_ligands"] == ["dBET57"]


def test_the_published_atlas_agrees_with_itself():
    """The guarantee as published. A count of zero beside a withheld field
    is the state this finding is about, and it must not come back."""
    if not (ATLAS / "ATLAS.json").exists():
        pytest.skip("no published atlas")
    summary = json.loads((ATLAS / "ATLAS.json").read_text())
    withheld = sum(
        path.read_text(errors="replace").count("smiles_withheld")
        for path in ATLAS.rglob("*")
        if path.is_file() and path.suffix in (".json", ".jsonl"))
    assert summary.get("redactions") == withheld, (
        f"the published ATLAS.json claims {summary.get('redactions')} "
        f"redaction(s) and the bundle carries {withheld}"
    )
