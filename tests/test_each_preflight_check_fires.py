"""Each of preflight's checks, triggered on its own.

`tools/preflight.py` appends to one `errors` list and reports
`ok: not errors`, so with any single check removed the others still fail the
campaign in front of it. A test asserting that preflight refuses the main
campaign passes with any one check deleted: that is F273's finding about
guards in series, in the gate that would have caught F262 before a minute of
GPU was spent.

`tools/mutate.py` confirmed it. Replacing each of six conditions with a
constant was caught by nothing, including the two whose message text appears
in a test elsewhere.

So: one fixture per check, each breaking exactly one thing and asserting that
check's own error, with a base case that must produce none. The base case is
what makes the rest meaningful; without it a fixture that errors for an
unrelated reason would pass every assertion below (F274).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml as yaml_lib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RECEPTOR = "MKVLAAGIVGL"
PEPTIDE = "IYKPGKTITMIKDKM"


def _module():
    spec = importlib.util.spec_from_file_location(
        "preflight", ROOT / "tools" / "preflight.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _campaign(tmp_path: Path, sequences=None, rows=None,
              msa_query: str | None = None) -> dict:
    """A one-pair campaign that preflights clean, unless broken on purpose.

    Not named `campaign_*`, and the name is load-bearing (F340).
    `inputs._regenerated_scan` reproduces a named assembler's output and
    compares against it, and preflight now runs that before the compute
    rather than leaving it to the atlas build at the end. This fixture is a
    synthetic two-job campaign, so the current manifest emits no such job
    and the scan said so, correctly: two disagreements, and the base case
    stopped being clean.

    The scan is right and the old name was the misnomer. A fixture is not
    any assembler's output, which is the `not_applicable` case the module
    reserves for "there is no comparison to make", as distinct from "the
    comparison failed". Renaming it says what it is rather than exempting it
    from a question it genuinely cannot answer.

    Do not rename this back to a prefix that has a regenerator. The base
    case would fail, and making it pass by loosening the provenance check
    would be mutating a refusal to keep a fixture, which is what
    `deploy/build_atlas.py`'s own comment warns about.
    """
    campaign = tmp_path / "preflight_checks"
    (campaign / "yaml").mkdir(parents=True, exist_ok=True)
    msa = campaign / "receptor.a3m"
    msa.write_text(f">query\n{msa_query or RECEPTOR}\n")

    def _default(complex_type: str) -> list[dict]:
        out = [{"protein": {"id": "A", "sequence": RECEPTOR, "msa": str(msa)}},
               {"protein": {"id": "P", "sequence": PEPTIDE, "msa": "empty"}}]
        if complex_type == "ternary":
            out.append({"ligand": {"id": "L", "ccd": "Y70"}})
        return out

    queue = []
    for complex_type in ("binary", "ternary"):
        path = campaign / "yaml" / f"job_{complex_type}.yaml"
        body = (sequences(complex_type) if callable(sequences)
                else _default(complex_type))
        path.write_text(yaml_lib.safe_dump({"version": 1, "sequences": body}))
        queue.append({
            "job_id": f"job_{complex_type}", "pair_id": "p1",
            "complex_type": complex_type, "peptide_sequence": PEPTIDE,
            "tokens": 150, "construct": "CRBN_CULT",
            "ligand_key": "Y70" if complex_type == "ternary" else None,
            "ligand_encoding": "ccd" if complex_type == "ternary" else None,
            "yaml": str(path)})
    for row in rows or []:
        queue.append(row)
    (campaign / "queue.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in queue))
    return _module().preflight(campaign)


def _problems(report: dict) -> str:
    return " | ".join(item["problem"] for item in report["errors"])


def test_the_base_case_is_clean(tmp_path):
    """Without this, every test below could pass on an unrelated error."""
    report = _campaign(tmp_path)
    assert report["ok"] is True, _problems(report)


def test_a_peptide_chain_with_an_msa_is_flagged(tmp_path):
    """Spec 1.3: the peptide gets no alignment."""
    def sequences(complex_type):
        msa = tmp_path / "preflight_checks" / "receptor.a3m"
        return [{"protein": {"id": "A", "sequence": RECEPTOR, "msa": str(msa)}},
                {"protein": {"id": "P", "sequence": PEPTIDE, "msa": str(msa)}}]

    report = _campaign(tmp_path, sequences=sequences)
    assert "peptide chain carries an MSA" in _problems(report), _problems(report)


def test_a_receptor_chain_without_an_msa_is_flagged(tmp_path):
    """Or the campaign calls a server mid-run."""
    def sequences(complex_type):
        return [{"protein": {"id": "A", "sequence": RECEPTOR, "msa": "empty"}},
                {"protein": {"id": "P", "sequence": PEPTIDE, "msa": "empty"}}]

    report = _campaign(tmp_path, sequences=sequences)
    assert "no cached MSA" in _problems(report), _problems(report)


def test_an_msa_named_but_absent_is_flagged(tmp_path):
    """The YAML naming a file is not the file being there."""
    def sequences(complex_type):
        return [{"protein": {"id": "A", "sequence": RECEPTOR,
                             "msa": str(tmp_path / "gone.a3m")}},
                {"protein": {"id": "P", "sequence": PEPTIDE, "msa": "empty"}}]

    report = _campaign(tmp_path, sequences=sequences)
    assert "missing on disk" in _problems(report), _problems(report)


def test_an_msa_for_the_wrong_chain_is_flagged(tmp_path):
    """F40: an a3m for another protein is worse than none.

    Boltz would fold confidently against someone else's conservation, and the
    file name is content-addressed so it matches by construction while the
    contents are written by a separate step.
    """
    report = _campaign(tmp_path, msa_query="TOTALLYDIFFERENTSEQUENCE")
    assert report["ok"] is False, "an a3m for the wrong chain was accepted"
    assert _problems(report), _problems(report)


def test_duplicate_chain_ids_are_flagged(tmp_path):
    def sequences(complex_type):
        msa = tmp_path / "preflight_checks" / "receptor.a3m"
        return [{"protein": {"id": "A", "sequence": RECEPTOR, "msa": str(msa)}},
                {"protein": {"id": "A", "sequence": RECEPTOR, "msa": str(msa)}},
                {"protein": {"id": "P", "sequence": PEPTIDE, "msa": "empty"}}]

    report = _campaign(tmp_path, sequences=sequences)
    assert "duplicate chain id" in _problems(report), _problems(report)


def test_a_missing_peptide_chain_is_flagged(tmp_path):
    def sequences(complex_type):
        msa = tmp_path / "preflight_checks" / "receptor.a3m"
        return [{"protein": {"id": "A", "sequence": RECEPTOR, "msa": str(msa)}}]

    report = _campaign(tmp_path, sequences=sequences)
    assert "no peptide chain" in _problems(report), _problems(report)


def test_zinc_in_one_arm_only_is_flagged(tmp_path):
    """Delta-ipTM would report the cofactor rather than the glue."""
    def sequences(complex_type):
        msa = tmp_path / "preflight_checks" / "receptor.a3m"
        out = [{"protein": {"id": "A", "sequence": RECEPTOR, "msa": str(msa)}},
               {"protein": {"id": "P", "sequence": PEPTIDE, "msa": "empty"}}]
        if complex_type == "ternary":
            out.append({"ligand": {"id": "L", "ccd": "Y70"}})
            out.append({"ligand": {"id": "Z", "ccd": "ZN"}})
        return out

    report = _campaign(tmp_path, sequences=sequences)
    assert "zinc present in one arm only" in _problems(report), _problems(report)


def test_zinc_in_both_arms_is_not_flagged(tmp_path):
    """The symmetric case, so the check above is not merely 'zinc is bad'."""
    def sequences(complex_type):
        msa = tmp_path / "preflight_checks" / "receptor.a3m"
        out = [{"protein": {"id": "A", "sequence": RECEPTOR, "msa": str(msa)}},
               {"protein": {"id": "P", "sequence": PEPTIDE, "msa": "empty"}},
               {"ligand": {"id": "Z", "ccd": "ZN"}}]
        if complex_type == "ternary":
            out.append({"ligand": {"id": "L", "ccd": "Y70"}})
        return out

    report = _campaign(tmp_path, sequences=sequences)
    assert "zinc present in one arm only" not in _problems(report), (
        _problems(report))
