"""A ternary arm without the glue is a second binary arm.

scr_bench03_BRD4_CRBN ran a whole campaign that way. Every one of its ten
queue records named ligand dBET57, and none of its five ternary YAMLs carried
a ligand block, so what was folded was receptor plus peptide twice over. Its
Delta-ipTM came out at exactly 0.0, which for a scramble control reads as the
cleanest possible result, and its bridge rate was unmeasurable with
`no_ligand_chain_in_output` on all five seeds.

The cause: a pair id that is not a benchmark member fell back to
`L.by_ccd(pair["ligand"]["ccd"])`, and dBET57 is SMILES-only, so the lookup
returned None and `build_yaml` omitted the block. The other thirty scrambles
carry CCD-encoded glues and were unaffected, which is why one pair in 158 was
wrong (F262).

Two things are tested here: that the resolution keeps a SMILES-only glue, and
that preflight refuses a queue where a record and its YAML disagree about one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml as yaml_lib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.curate import ligands as L
from nobble.execute import campaign as C


def _record(**overrides) -> dict:
    import dataclasses

    base = {field.name: None for field in dataclasses.fields(L.Ligand)}
    base.update({"key": "dBET57", "encoding": "smiles", "ccd": None,
                 "smiles": "CC1=C(C)C2=C(S1)N1C(C)=NN=C1", "name": "dBET57",
                 "heavy_atoms": 60, "ccd_class": None, "is_furniture": False,
                 "affinity_available": False, "modality": "protac",
                 "source": "protacdb", "notes": []})
    base.update(overrides)
    return base


def test_a_smiles_only_glue_survives_the_fallback():
    """The exact case that was dropped: no CCD to look up."""
    ligand = C._ligand_of({"ligand": _record()})
    assert ligand is not None, "a SMILES-only glue resolved to None again"
    assert ligand.key == "dBET57"
    assert ligand.encoding == "smiles"
    assert ligand.smiles


def test_a_ccd_encoded_glue_still_resolves():
    ligand = C._ligand_of({"ligand": _record(key="Y70", encoding="ccd",
                                             ccd="Y70")})
    assert ligand is not None and ligand.ccd == "Y70", ligand


def test_a_pair_with_no_ligand_is_none():
    assert C._ligand_of({}) is None
    assert C._ligand_of({"ligand": {}}) is None


def test_an_incomplete_record_falls_back_to_the_ccd_lookup():
    """A partial record is not trusted into the dataclass.

    Splatting it would raise here, inside an assembler, which is a worse
    failure than falling back to the lookup that at least handles a CCD.
    """
    ligand = C._ligand_of({"ligand": {"key": "Y70", "ccd": "Y70"}})
    assert ligand is None or ligand.ccd == "Y70", ligand


def test_the_ternary_yaml_carries_a_smiles_glue():
    """End to end through the writer, not just the resolution.

    `build_yaml` adds the block only when the ligand is not None, so the
    resolution above is the whole of the bug, and this pins the other half.
    """
    from nobble.execute import yaml_gen as Y

    class _Job:
        complex_type = "ternary"
        conditioning = "unconstrained"
        job_id = "x__ternary__unconstrained__seed1"
        pair_id = "scr_x"
        seed = 1
        construct = "CRBN_CULT"
        e3_gene = "CRBN"
        required_modification = None

    # The real dataclass, with its defaults, rather than a stub. A stub grew
    # a field at a time as the writer reached for `required_modification`,
    # then `cofactor`, and each miss skipped or failed the test for a reason
    # that had nothing to do with the glue.
    from nobble.curate import peptides as P

    peptide = P.Peptide(
        peptide_id="scramble_x", sequence="IYKPGKTITMIKDKM", source="scramble",
        label="negative_control", accession="O60885", gene="BRD4",
        start_res=1, end_res=15)

    ligand = C._ligand_of({"ligand": _record()})
    document = Y.build_yaml(_Job(), peptide, ligand, None)
    kinds = [next(iter(entry)) for entry in document.get("sequences", [])]
    assert "ligand" in kinds, document
    block = next(entry["ligand"] for entry in document["sequences"]
                 if "ligand" in entry)
    assert block.get("smiles"), block


def _preflight(tmp_path: Path, with_ligand: bool) -> dict:
    """A one-job campaign whose YAML either carries the glue or does not."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "preflight", ROOT / "tools" / "preflight.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    campaign = tmp_path / "campaign_fixture"
    (campaign / "yaml").mkdir(parents=True)
    msa = campaign / "receptor.a3m"
    msa.write_text(">query\nMKVLA\n")
    sequences = [
        {"protein": {"id": "A", "sequence": "MKVLA", "msa": str(msa)}},
        {"protein": {"id": "P", "sequence": "IYKPGKTITMIKDKM", "msa": "empty"}},
    ]
    if with_ligand:
        sequences.append({"ligand": {"id": "L", "smiles": "CC1=C(C)C2=C(S1)"}})
    path = campaign / "yaml" / "job1.yaml"
    path.write_text(yaml_lib.safe_dump({"version": 1, "sequences": sequences}))
    (campaign / "queue.jsonl").write_text(json.dumps({
        "job_id": "job1", "pair_id": "scr_x", "complex_type": "ternary",
        "ligand_key": "dBET57", "ligand_encoding": "smiles",
        "tokens": 150, "construct": "CRBN_CULT", "yaml": str(path)}) + "\n")
    return module.preflight(campaign)


def test_preflight_refuses_a_ternary_job_whose_glue_is_missing(tmp_path):
    report = _preflight(tmp_path, with_ligand=False)
    assert report["ok"] is False, report
    assert report["ternary_jobs_missing_their_ligand"] == 1, report
    assert any("no ligand chain" in item["problem"]
               for item in report["errors"]), report["errors"]


def test_preflight_passes_when_the_glue_is_there(tmp_path):
    report = _preflight(tmp_path, with_ligand=True)
    assert report["ternary_jobs_missing_their_ligand"] == 0, report
    assert not [item for item in report["errors"]
                if "no ligand chain" in item["problem"]], report["errors"]
