"""The crystal control as the About page renders it (F297).

Four cases, because they read differently to someone deciding whether to
trust the bridge percentile and the panel must not collapse them: a control
that found every bridge, one that missed a bridge present in the
coordinates, one whose deposition models no glue, and a bundle built before
the control existed. The third and fourth both mean "no measurement" and the
first two are the measurement, so an empty table rendering as a clean
result would be the F293 error on screen.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.app import data                                 # noqa: E402

FOUND = {
    "pair_id": "bench04_IKZF1_CRBN", "pdb_id": "6H0F", "glue_ccd": "Y70",
    "measurable": True, "found": True, "reject_reason": None,
    "dsasa_receptor": 540.6, "dsasa_peptide": 228.3, "dsasa_total": 768.9,
    "bridge_percentile": 50.08, "notes": [],
}
MISSED = dict(FOUND, pair_id="bench05_CSNK1A1_CRBN", pdb_id="5FQD",
              found=False, reject_reason="single_chain:1_qualifying_of_1",
              dsasa_receptor=None, dsasa_peptide=None, dsasa_total=None,
              bridge_percentile=None,
              notes=["best single half-interface: receptor"])
UNMEASURABLE = dict(FOUND, pair_id="bench03_BRD4_CRBN", pdb_id="6BNB",
                    glue_ccd=None, measurable=False, found=False,
                    reject_reason="glue_not_modelled_in_deposition",
                    dsasa_receptor=None, dsasa_peptide=None,
                    dsasa_total=None, bridge_percentile=None,
                    notes=["6BNB carries no heteroatom large enough to be "
                           "a glue"])


def _page(tmp_path: Path, about: dict | None) -> str:
    from nobble.app import create_app

    if about is not None:
        (tmp_path / "about.json").write_text(json.dumps(about))
    app = create_app(str(tmp_path))
    app.config["TESTING"] = True
    body = app.test_client().get("/about")
    assert body.status_code == 200, body.status_code
    return body.get_data(as_text=True)


def test_the_counts_separate_a_miss_from_an_unmeasurable_row():
    counts = data.crystal_control_counts(
        {"status": "measured", "rows": [FOUND, MISSED, UNMEASURABLE]})
    assert counts == {
        "intended": 3, "measurable": 2, "found": 1,
        "unmeasurable": [UNMEASURABLE], "status": "measured",
    }


def test_a_clean_control_states_its_denominator(tmp_path):
    page = _page(tmp_path, {"crystal_control": {
        "status": "measured", "rows": [FOUND, UNMEASURABLE]}})
    assert "The bridge detector against deposited coordinates" in page
    assert "1 / 1" in page
    assert "of 2 benchmark pair(s)" in page
    assert "768.9" in page
    assert "50.08" in page


def test_a_missed_bridge_is_shown_as_a_miss(tmp_path):
    """A false negative of the instrument is the one thing this panel is
    for, so it has to be visible as one rather than as a blank row."""
    page = _page(tmp_path, {"crystal_control": {
        "status": "measured", "rows": [FOUND, MISSED]}})
    assert "missed" in page
    assert "single_chain:1_qualifying_of_1" in page
    assert "1 / 2" in page


def test_an_unmodelled_glue_is_not_counted_as_a_miss(tmp_path):
    page = _page(tmp_path, {"crystal_control": {
        "status": "measured", "rows": [FOUND, UNMEASURABLE]}})
    assert "not measurable" in page
    assert "glue_not_modelled_in_deposition" in page
    assert "no heteroatom large enough" in page
    assert "missed" not in page


def test_an_older_bundle_says_so_rather_than_showing_nothing(tmp_path):
    page = _page(tmp_path, {"sources": {}})
    assert "The bridge detector against deposited coordinates" in page
    assert "built before the control existed" in page


def test_a_failed_control_carries_its_reason(tmp_path):
    """`unavailable:` is not the same as every deposition passing, and the
    build records the reason rather than omitting the key (F266)."""
    page = _page(tmp_path, {"crystal_control": {
        "status": "unavailable: ImportError: no module named freesasa",
        "rows": []}})
    assert "no module named freesasa" in page


def test_the_atlas_build_computes_it(tmp_path):
    """Without this the panel would render `not computed` on every bundle."""
    source = (ROOT / "deploy" / "build_atlas.py").read_text()
    assert "bridge_on_crystals" in source
    assert '"crystal_control": crystal_control' in source


def test_the_publication_hold_prints_the_control():
    """The hold's reason is that pose recovery fails its positive control,
    which is about where a peptide lands. Spec 4.1's primary signal is the
    bridge geometry, and someone deciding a release should see both."""
    import ast

    source = (ROOT / "tools" / "publication_hold.py").read_text()
    tree = ast.parse(source)
    called = {node.name: {child.func.id for child in ast.walk(node)
                          if isinstance(child, ast.Call)
                          and isinstance(child.func, ast.Name)}
              for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert "detector_control" in called.get("main", set()), (
        "publication_hold.main no longer prints the detector control, so a "
        "release decision sees the recovery failure without the primary "
        "signal's own control"
    )
