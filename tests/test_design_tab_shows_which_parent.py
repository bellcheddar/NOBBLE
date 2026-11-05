"""The scan profile has to say which peptide it is of (F160).

F147 attached the profile to the parent the campaign scanned rather than the
one the report ranks first, and computed a note saying when those differ.
Nothing rendered the note, and the panel above the chart still names the
ranked parent, so the page showed "Parent GSPT1" over the per-position
profile of a different peptide.

Getting the data right and leaving the label wrong is worse than the silence
it replaced: before F147 the profile simply did not appear, which is
unhelpful and not misleading.

Found by rendering the design tab with a scored scan for the first time.
Every QC run before this was against a campaign where no scan had run, so
the panel was an empty state.
"""
from __future__ import annotations

import json
import random
import shutil
from pathlib import Path
from nobble.execute.campaign import latest_or_absent as _newest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = _newest("benchmark")
DESIGN = sorted((ROOT / "campaigns").glob("design_*"))


def _served_campaign(root: Path, monkeypatch) -> tuple[Path, dict]:
    """A benchmark campaign plus a design.json built from a scored scan."""
    if not DESIGN:
        return None, {}
    source = DESIGN[-1]
    served = root / "campaign"
    served.mkdir(parents=True)
    for name in ("campaign.json", "queue.jsonl", "state.jsonl",
                 "results.jsonl", "scores.jsonl", "weights.json"):
        shutil.copy(BENCHMARK / name, served / name)

    campaigns = root / "campaigns"
    scan = campaigns / source.name
    scan.mkdir(parents=True)
    shutil.copy(source / "campaign.json", scan / "campaign.json")
    queue = [json.loads(line) for line
             in (source / "queue.jsonl").read_text().splitlines()
             if line.strip()]
    first = {}
    for row in queue:
        first.setdefault(row["peptide_id"], row)
    chance = random.Random(20261104)
    rows = [{
        "peptide_id": pid, "pair_id": row["pair_id"], "tier": "design",
        "parent_peptide_id": row.get("parent_peptide_id"),
        "substitution": row.get("substitution"), "position": row.get("position"),
        "construct": row["construct"], "e3_gene": row["e3_gene"],
        "ligand_key": row["ligand_key"], "modality": row["modality"],
        "peptide_sequence": row["peptide_sequence"],
        "seeds_binary": 5, "seeds_ternary": 10,
        "delta_iptm": round(chance.gauss(-0.05, 0.06), 4),
        "bridging_seeds_with_bridge": chance.randint(0, 10),
        "bridging_seeds_total": 10,
    } for pid, row in first.items()]
    (scan / "scores.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows))

    from nobble import paths
    monkeypatch.setattr(paths, "CAMPAIGNS", campaigns)
    from nobble.design import report
    document = report.build()
    (served / "design.json").write_text(
        json.dumps(document, indent=2, default=str))
    return served, document


def test_the_fixture_produces_a_profile(tmp_path, monkeypatch):
    """Otherwise everything below checks an empty state."""
    served, document = _served_campaign(tmp_path, monkeypatch)
    if served is None:
        return
    assert document["lifts"]["computed"] > 0, document["lifts"].get("status")
    assert document["profile"]["positions"]


def test_the_page_names_the_peptide_the_profile_is_of(tmp_path, monkeypatch):
    served, document = _served_campaign(tmp_path, monkeypatch)
    if served is None:
        return
    from nobble.app import create_app

    body = create_app(str(served)).test_client().get("/design").get_data(
        as_text=True)
    scanned = document["lifts"]["scan_parent"]
    assert 'id="scan-parent"' in body, (
        "the scan panel does not say which peptide its profile is of"
    )
    assert scanned in body, f"{scanned} is not named on the page"


def test_a_mismatch_with_the_ranking_is_shown_and_not_merely_computed(
        tmp_path, monkeypatch):
    """The note F147 computed and nothing rendered."""
    served, document = _served_campaign(tmp_path, monkeypatch)
    if served is None:
        return
    note = document["lifts"].get("note")
    from nobble.app import create_app

    body = create_app(str(served)).test_client().get("/design").get_data(
        as_text=True)
    if not note:
        assert 'id="scan-parent-note"' not in body, (
            "a note element is rendered with no note to put in it"
        )
        return
    assert 'id="scan-parent-note"' in body, (
        "the ranked parent and the scanned parent differ, the note says so, "
        "and the page does not show it"
    )
    ranked = (document.get("preview") or {}).get("parent", {}).get("peptide_id")
    assert ranked and ranked in body


def test_the_note_is_pipeline_output_and_marked_as_such():
    """Every specific in it is computed, so the copy budget excludes it."""
    template = (ROOT / "nobble" / "app" / "templates" / "design.html").read_text()
    for marker in ('id="scan-parent"', 'id="scan-parent-note"'):
        at = template.index(marker)
        assert 'class="mono"' in template[at - 60:at + 20], marker
