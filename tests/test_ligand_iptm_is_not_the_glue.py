"""`ligand_iptm` is Boltz's name for whichever het group was in the job.

PLIP perceives every het group as a ligand and F81 dealt with that. Boltz
does the same thing one level up, in a confidence field, and that one had
not been looked at.

Measured on the first Sievers result of the main campaign,
`sv_neg_ZN346_d5063d__binary__unconstrained__seed1`: `ligand_iptm` is
0.9946, which is exactly `pair_chains_iptm["2"]["0"]`, the structural zinc's
row. That job is the binary arm and contains no glue at all. Across the
120-pair Sievers arm the field would describe the finger holding itself
together, on both arms.

Nothing reads it today, which is why nothing is wrong today. It is recorded
in `scores.jsonl` under a name that invites being read as the glue's grip on
the degron, and it is not in the published atlas. This pins both facts, so
that wiring it to a panel fails here with the reason rather than shipping a
plausible number (F102).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCES = ("nobble", "deploy", "tools", "qc")
ALLOWED = {
    # The dataclass field and the one assignment that fills it from Boltz.
    "nobble/score/metrics.py",
}


def _python_files():
    for root in SOURCES:
        for path in sorted((ROOT / root).rglob("*.py")):
            if "vendor" in path.parts or "__pycache__" in path.parts:
                continue
            yield path


def test_only_metrics_mentions_it():
    """A consumer is a reader, and a reader of this field is reading the
    cofactor on 120 of the 158 pairs."""
    mentions = sorted(
        str(path.relative_to(ROOT)) for path in _python_files()
        if "ligand_iptm" in path.read_text()
    )
    assert set(mentions) <= ALLOWED, (
        f"{sorted(set(mentions) - ALLOWED)} reads ligand_iptm. It is Boltz's "
        "name for whichever het group was in the job, which on a Sievers "
        "pair is the structural zinc and on a binary Sievers job is the only "
        "het group present. Use the glue's own chain explicitly."
    )


def test_it_is_not_in_the_app_or_the_published_atlas():
    for pattern in ("*.html", "*.js"):
        for path in (ROOT / "nobble" / "app").rglob(pattern):
            if "vendor" in path.parts:
                continue
            assert "ligand_iptm" not in path.read_text(), path

    atlas = ROOT / "deploy" / "atlas"
    if not atlas.exists():
        pytest.skip("no published atlas")
    for path in sorted(atlas.glob("*.json")):
        assert "ligand_iptm" not in path.read_text(), path


def test_the_cofactor_is_what_boltz_calls_the_ligand_on_a_real_job():
    """The measurement behind the claim, against the campaign's own records
    rather than a fixture, because the whole point is what Boltz actually
    reports for a job carrying a structural ion."""
    from nobble.execute.campaign import latest

    campaign = latest("campaign")
    if campaign is None or not (campaign / "results.jsonl").exists():
        pytest.skip("no campaign results")

    rows = [json.loads(line) for line
            in (campaign / "results.jsonl").read_text().splitlines() if line.strip()]
    zinc_binaries = [
        row for row in rows
        if row.get("tier") == "sievers_zf"
        and row.get("complex_type") == "binary"
        and row.get("status") == "done"
        and isinstance(row.get("confidence"), dict)
    ]
    if not zinc_binaries:
        pytest.skip("the Sievers arm has not reached a completed binary job")

    row = zinc_binaries[0]
    confidence = row["confidence"]
    reported = confidence.get("ligand_iptm")
    matrix = confidence.get("pair_chains_iptm") or {}
    assert reported is not None, row["job_id"]

    # The binary arm has no glue, so any ligand ipTM at all is the cofactor.
    cells = [value for rowdict in matrix.values()
             for value in (rowdict or {}).values()]
    assert reported in cells, (
        f"{row['job_id']}: ligand_iptm {reported} is not a cell of the "
        "pair matrix, so which chain it describes would need rechecking"
    )
    assert reported > 0.5, (
        "a high confidence for a chain that is a zinc ion, which is the point"
    )


def test_the_metric_the_pipeline_does_use_excludes_the_cofactor():
    """The contrast, and the reason this is a note rather than a defect:
    `iptm_receptor_peptide` is taken over the receptor chains only, so the
    zinc's zero column and high row both stay out of it."""
    from nobble.execute.campaign import latest
    from nobble.score import metrics

    campaign = latest("campaign")
    if campaign is None or not (campaign / "results.jsonl").exists():
        pytest.skip("no campaign results")
    rows = [json.loads(line) for line
            in (campaign / "results.jsonl").read_text().splitlines() if line.strip()]
    sievers = [row for row in rows if row.get("tier") == "sievers_zf"
               and row.get("status") == "done"]
    if not sievers:
        pytest.skip("the Sievers arm has not produced a result yet")

    record = metrics.seed_record(sievers[0]).to_dict()
    assert record["iptm_receptor_chains"] == [0], record["iptm_receptor_chains"]
    assert record["iptm_receptor_peptide"] not in (0.0, None)
    assert record["iptm_receptor_peptide"] != record["ligand_iptm"], (
        "the metric and the cofactor's score have become the same number"
    )
