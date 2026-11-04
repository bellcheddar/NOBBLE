"""The scan profile must belong to the parent that was scanned (F147).

`report.build()` picks a parent from the current scores and then asked the
newest design campaign about that parent's variants:

    lifts = lift_module.from_scores(scored[-1], chosen["peptide_id"])

The design campaign was assembled for whichever parent led when it was
assembled. The chain keeps them in step, because stage 4 re-assembles the
scan from this report's own preview, and nothing makes them stay in step
afterwards.

They are already apart. The assembled design campaign records
`benchmark_888fd2c63e` and `report.build()` now ranks `benchmark_83c557c3dc`
first, because the main campaign has scored more pairs since. Under the old
code the scan would have run its 240 jobs, scored them, and shown no profile
at all: `from_scores` matches variants by `parent_peptide_id`, finds none for
a parent the campaign is not about, and returns "parent not scored", which
reads as "the scan has not run".

The campaign's own `campaign.json` records `parent` and `parent_sequence`.
Reading the artefact's record rather than re-deriving is F137's lesson.
"""
from __future__ import annotations

import json
from pathlib import Path

from nobble import paths
from nobble.design import report

ROOT = Path(__file__).resolve().parents[1]

SEQUENCE = "PFQCNQCGASFTQKG"


def _design_campaign(root: Path, parent: str, variants: int = 3) -> Path:
    """A scored design campaign for one parent."""
    directory = root / "design_20260101T000000Z"
    directory.mkdir(parents=True)
    (directory / "campaign.json").write_text(json.dumps({
        "campaign_id": directory.name,
        "parent": parent,
        "parent_sequence": SEQUENCE,
    }))
    shared = {
        "tier": "design", "construct": "CRBN_CULT", "e3_gene": "CRBN",
        "ligand_key": "Y70", "modality": "glue",
        "seeds_binary": 5, "seeds_ternary": 10,
        "bridging_seeds_with_bridge": 5, "bridging_seeds_total": 10,
    }
    rows = [{**shared, "peptide_id": parent, "pair_id": f"d_{parent}",
             "parent_peptide_id": None, "peptide_sequence": SEQUENCE,
             "delta_iptm": -0.10}]
    for index in range(variants):
        position = index + 1
        rows.append({**shared,
                     "peptide_id": f"{parent}_v{position}",
                     "pair_id": f"d_{parent}_v{position}",
                     "parent_peptide_id": parent,
                     "substitution": f"{SEQUENCE[index]}{position}A",
                     "position": position,
                     "peptide_sequence": SEQUENCE,
                     "delta_iptm": -0.10 - 0.01 * position})
    (directory / "scores.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows))
    return directory


def test_the_profile_uses_the_scanned_parent_not_the_ranked_one(tmp_path, monkeypatch):
    """The defect, with the two deliberately apart."""
    monkeypatch.setattr(paths, "CAMPAIGNS", tmp_path)
    scanned = "benchmark_888fd2c63e"
    _design_campaign(tmp_path, scanned)
    built = report.build()
    lifts = built["lifts"]
    assert lifts["scan_parent"] == scanned, lifts
    assert lifts["computed"] == 3, (
        f"no lift computed: {lifts.get('status')}. The report asked the "
        "campaign about a parent it is not about"
    )
    profile = built["profile"]
    assert profile, "the scan ran and produced no profile"
    assert profile["parent_sequence"] == SEQUENCE
    assert profile["scored"] == 3


def test_a_mismatch_is_stated_rather_than_silent(tmp_path, monkeypatch):
    """A profile for a parent other than the one on top has to say so.

    Otherwise the design tab shows a ranking headed by one peptide and a
    per-position profile of another, with nothing connecting them.
    """
    monkeypatch.setattr(paths, "CAMPAIGNS", tmp_path)
    # Scanned parent chosen so it cannot be the one the report ranks first:
    # no such peptide exists in the parent list at all. The first version
    # returned early when the two happened to agree, which made it assert
    # nothing, and whether they agreed depended on which tests had run
    # before it (F152).
    scanned = "not_a_real_parent_id"
    _design_campaign(tmp_path, scanned)
    built = report.build()
    chosen = (built.get("preview") or {}).get("parent") or {}
    assert chosen.get("peptide_id") != scanned, (
        "the fixture's scanned parent is the ranked one, so there is no "
        "mismatch to state and this test checks nothing"
    )
    note = built["lifts"].get("note")
    assert note, (
        "the ranked parent and the scanned parent differ and nothing says so"
    )
    assert scanned in note
    assert chosen["peptide_id"] in note, (
        "the note names the scanned parent and not the ranked one, so a "
        "reader cannot tell which peptide the ranking is of"
    )


def test_it_names_the_campaign_the_profile_came_from(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "CAMPAIGNS", tmp_path)
    directory = _design_campaign(tmp_path, "benchmark_888fd2c63e")
    built = report.build()
    assert built["lifts"]["scan_campaign"] == directory.name


def test_a_campaign_with_no_record_falls_back_to_the_ranked_parent(tmp_path, monkeypatch):
    """Older design campaigns predate the recorded parent.

    Falling back is right, and falling back silently to a parent the
    campaign may not be about is what the old code did unconditionally, so
    the fallback must not become the normal path.
    """
    monkeypatch.setattr(paths, "CAMPAIGNS", tmp_path)
    directory = _design_campaign(tmp_path, "benchmark_888fd2c63e")
    (directory / "campaign.json").unlink()
    built = report.build()
    chosen = (built.get("preview") or {}).get("parent") or {}
    assert built["lifts"]["scan_parent"] == chosen.get("peptide_id")


def test_the_live_campaign_and_the_live_report_really_do_disagree():
    """The fact that makes this finding live rather than hypothetical.

    Both branches assert. The first version returned when the two agreed,
    so it recorded nothing in the case it exists to describe and nothing in
    the other case either: the sweep for never-executed assertions found it
    had never reached its only assert, because an earlier test had left
    `nobble.app.data` pinned elsewhere and the ranking came out different
    (F152).

    If the two ever agree again this test still passes, and says so by
    taking the other branch rather than by falling silent.
    """
    design = sorted((ROOT / "campaigns").glob("design_*/campaign.json"))
    if not design:
        return
    recorded = json.loads(design[-1].read_text()).get("parent")
    chosen = (report.build().get("preview") or {}).get("parent") or {}
    assert recorded, f"{design[-1]} records no parent"
    if recorded == chosen.get("peptide_id"):
        # They agree. The fix is unnecessary on today's data and still
        # correct; nothing to record beyond that they are both present.
        assert chosen.get("peptide_id")
        return
    assert chosen.get("peptide_id"), (
        "the report ranks no parent at all, so the disagreement this "
        "records is between a campaign and nothing"
    )
