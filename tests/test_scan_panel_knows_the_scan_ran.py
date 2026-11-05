"""A panel headed "Planned scan" over fifteen measured lifts.

No design campaign has run, so `design.json` carries
`lifts: {"status": "no design campaign has run yet", "lifts": []}` and the
design tab has only ever been rendered unscanned. Rendering it with a
completed alanine scan put the measured state on screen for the first time:
fifteen lifts, three substitutions that lost the bridge outright and six
that weakened it, all correct.

Around them, two lines still described the unscanned state. The panel's
heading read "Planned scan", and under the table a projection of the work:
"15 variants, 225 jobs, about 4.4 hours." Both were static. A reader saw a
plan and an estimate of what it would cost wrapped around its own results.

The Lift column had the same defect and was fixed, with a comment in
`design.html` saying the page "disagreed with itself about whether the scan
had run". That fix stopped at the column. The heading and the cost line are
F206, and the lesson is the one F203 keeps producing: a panel's state is not
one field, and fixing the field that showed the measurement leaves the
surrounding prose asserting the old state.

`data.scan_state` is keyed on the substitutions the profile has a lift for,
which is the mapping the Lift column already builds, so the heading cannot
claim a scan the table does not show. It is computed in the route rather
than the template because the route blanks the profile when the chosen
parent is not the one that was scanned.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.app import create_app, data as app_data  # noqa: E402
from nobble.design import lift as lift_module  # noqa: E402

ATLAS = ROOT / "deploy" / "atlas" / "design.json"
CONDITIONS = {"construct": "CRBN_CULT", "e3_gene": "CRBN",
              "ligand_key": "Y70", "modality": "glue"}
SEEDS = {"seeds_binary": 5, "seeds_ternary": 10}


def _published() -> dict:
    if not ATLAS.exists():
        pytest.skip("no published atlas on this checkout")
    document = json.loads(ATLAS.read_text())
    if not (document.get("preview") or {}).get("variants"):
        pytest.skip("the published design document has no preview to scan")
    return document


def _scanned(document: dict, how_many: int | None = None) -> dict:
    """The document as it would be after a scan, via the real lift module.

    Lifts are computed by `nobble/design/lift.py` from synthesised scores
    rather than written out here, so the fixture carries the field names and
    the refusal logic the pipeline would produce (F205's fixture was wrong
    about the bridging keys and the bridge columns came back empty).
    """
    document = json.loads(json.dumps(document))
    preview = document["preview"]
    parent = preview["parent"]
    pair = parent["peptide_id"]
    variants = preview["variants"]
    if how_many is not None:
        variants = variants[:how_many]

    rows = [dict(peptide_id=pair, pair_id=f"{pair}_ternary", tier="benchmark",
                 peptide_sequence=parent["sequence"], delta_iptm=0.316,
                 bridging_seeds_total=10, bridging_seeds_with_bridge=8,
                 **CONDITIONS, **SEEDS)]
    chance = random.Random(20261105)
    for variant in variants:
        weight = 1.0 - abs(variant["position"] - 7) / 10.0
        with_bridge = int(round(max(0.0, 0.8 - 0.85 * weight) * 10))
        rows.append(dict(
            peptide_id=variant["variant_id"], pair_id=variant["variant_id"],
            tier="design", parent_peptide_id=pair,
            peptide_sequence=variant["sequence"],
            substitution=variant["substitution"], position=variant["position"],
            delta_iptm=round(0.316 - 0.30 * weight + chance.gauss(0, 0.02), 4),
            bridging_seeds_total=10, bridging_seeds_with_bridge=with_bridge,
            **CONDITIONS, **SEEDS))

    return rows, document


def _document_with_scan(tmp_path: Path, how_many: int | None = None) -> dict:
    document = _published()
    rows, document = _scanned(document, how_many)
    scores = tmp_path / "scan_scores.jsonl"
    scores.write_text("".join(json.dumps(row) + "\n" for row in rows))
    pair = document["preview"]["parent"]["peptide_id"]
    lifts = lift_module.from_scores(scores, pair)
    assert lifts.get("computed"), f"the fixture computed no lifts: {lifts}"
    lifts["scan_parent"] = pair
    lifts["scan_campaign"] = "design_20261105T000000Z"
    objects = [lift_module.Lift(**item) for item in lifts["lifts"]]
    document["lifts"] = lifts
    document["profile"] = lift_module.scan_profile(
        objects, document["preview"]["parent"]["sequence"])
    return document


def _render(tmp_path: Path, document: dict, query: str = "") -> str:
    atlas = tmp_path / "atlas"
    atlas.mkdir(exist_ok=True)
    (atlas / "design.json").write_text(json.dumps(document))
    page = create_app(str(atlas)).test_client().get("/design" + query)
    assert page.status_code == 200, page.status_code
    return page.get_data(as_text=True)


def test_the_fixture_really_is_a_completed_scan(tmp_path):
    """Otherwise every assertion below passes against an unscanned page."""
    document = _document_with_scan(tmp_path)
    lifts = [row for row in document["profile"]["positions"]
             if row["lift"] is not None]
    assert len(lifts) == len(document["preview"]["variants"])
    assert document["profile"]["bridge_breaking"], (
        "no substitution lost its bridge, so the chart's outlined-point "
        "branch is not exercised"
    )


def test_a_completed_scan_is_not_headed_planned(tmp_path):
    body = _render(tmp_path, _document_with_scan(tmp_path))
    assert "Planned scan" not in body, (
        "the panel calls a scan with fifteen measured lifts a plan"
    )
    assert "Completed scan" in body


def test_a_completed_scan_does_not_project_the_work_it_has_done(tmp_path):
    document = _document_with_scan(tmp_path)
    body = _render(tmp_path, document)
    hours = document["preview"]["cost"]["projected_hours"]
    assert f"about {hours}" not in body, (
        "the panel still forecasts the hours the scan has already spent"
    )
    state = app_data.scan_state(document)
    assert f"{state['scored']} of {state['of']} variants scored" in body


def test_an_unscanned_parent_keeps_its_plan_and_its_projection(tmp_path):
    """The projection is the right line before the scan runs, and this is
    the branch the live site is in."""
    document = _published()
    body = _render(tmp_path, document)
    assert "Planned scan" in body
    assert "variants scored" not in body
    cost = document["preview"].get("cost")
    if cost:
        assert str(cost["jobs"]) in body


def test_a_part_way_scan_says_so_and_still_shows_the_full_projection(tmp_path):
    document = _document_with_scan(tmp_path, how_many=4)
    body = _render(tmp_path, document)
    assert "Scan in progress" in body
    assert "4 of" in body
    cost = document["preview"].get("cost")
    if cost:
        assert str(cost["jobs"]) in body, (
            "a part-finished scan hides what the rest of it costs"
        )


def test_switching_to_another_parent_does_not_inherit_the_heading(tmp_path):
    """The route blanks the profile when the chosen parent is not the one
    that was scanned, so the heading has to follow the profile and not the
    atlas (F147's shape, one field over)."""
    document = _document_with_scan(tmp_path)
    scanned = document["preview"]["parent"]["peptide_id"]
    other = next((p["peptide_id"] for p in document["parents"]
                  if p["peptide_id"] != scanned), None)
    if other is None:
        pytest.skip("only one scannable parent")
    body = _render(tmp_path, document, f"?parent={other}")
    assert "Planned scan" in body
    assert "Completed scan" not in body
    assert "Scan profile" not in body


def test_the_states_are_three_and_distinct():
    headings = set()
    for scored, total in ((0, 15), (4, 15), (15, 15)):
        positions = [{"substitution": f"X{i}A", "lift": -0.1}
                     for i in range(scored)]
        variants = [{"substitution": f"X{i}A"} for i in range(total)]
        state = app_data.scan_state(
            {"preview": {"variants": variants}, "profile": {"positions": positions}})
        assert state["scored"] == scored and state["of"] == total
        headings.add(state["heading"])
    assert len(headings) == 3, headings


def test_an_absent_profile_is_planned_rather_than_complete():
    """Zero of zero is the empty case, not a finished scan."""
    for document in ({}, {"preview": {}}, {"preview": {"variants": []}},
                     {"preview": {"variants": [{"substitution": "P1A"}]}}):
        assert app_data.scan_state(document)["status"] == "planned", document


def test_a_position_without_a_lift_does_not_count_as_scored():
    """`positions` has a row per residue whether or not it was scanned, so
    counting rows rather than lifts would call every scan complete."""
    state = app_data.scan_state({
        "preview": {"variants": [{"substitution": "P1A"},
                                 {"substitution": "F2A"}]},
        "profile": {"positions": [{"substitution": "P1A", "lift": -0.1},
                                  {"substitution": "F2A", "lift": None}]},
    })
    assert state["scored"] == 1 and state["status"] == "partial"
