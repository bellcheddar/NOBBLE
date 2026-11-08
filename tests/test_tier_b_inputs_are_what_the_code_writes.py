"""Tier B was the one arm the provenance check skipped (F340).

`inputs._regenerated_scan` compares a campaign's YAML against the code that
emits it, which is the third link of the three its own docstring sets out and
the one F262 broke. It applied only to `campaign_*`, by a deliberate
decision with a good reason: `regenerate_all` reproduces `assemble_campaign`,
and comparing another builder's output against that manifest "reports every
pair it has as work the code would not emit: a confident answer to a question
nobody asked".

The gap that left is specific. `tools/run_chain.sh` says of Tier B that the
arm "depends on the form and the library and both can change between runs",
and `assemble_tier_b` reuses a complete campaign by default, so reuse is the
default path. That is 1,540 jobs and about 33 hours with the one link that
would catch a changed form unverified, and the arm whose comment names the
hazard was the arm excluded from the check for it.

Closed by sharing the renderer rather than copying it (D-NOB-007).
`_tier_b_rendered` yields `(job, yaml text, queue extras)` and both
`assemble_tier_b` and `regenerate_tier_b` consume it, so the assembler and
the checker cannot disagree about what the code writes. A second copy of
that loop would have been able to agree with itself and be wrong, which is
F262's shape.

Measured on 2026-11-08: regenerating the arm on disk reproduced all 1,540
YAMLs byte for byte, so Tier B's form has not drifted. That is the answer to
the question, not an assumption in place of it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CAMPAIGN_SOURCE = (ROOT / "nobble" / "execute" / "campaign.py").read_text()
INPUTS_SOURCE = (ROOT / "nobble" / "validate" / "inputs.py").read_text()


def _tier_b():
    found = sorted(ROOT.glob("campaigns/tier_b_*"))
    found = [d for d in found if (d / "campaign.json").exists()]
    return found[-1] if found else None


def test_the_assembler_and_the_regenerator_share_one_renderer():
    """Not two copies of the loop, which could agree and be wrong."""
    assert "def _tier_b_rendered(manifest: dict, library: dict):" in \
        CAMPAIGN_SOURCE
    assert CAMPAIGN_SOURCE.count("_tier_b_rendered(manifest, library)") == 2, (
        "the renderer has other than two consumers; it exists so the "
        "assembler and the provenance check cannot diverge"
    )
    # And the assembler must not still carry its own copy of the ligand
    # routing, which is the fiddly part most likely to drift.
    assembler = CAMPAIGN_SOURCE[
        CAMPAIGN_SOURCE.index("def assemble_tier_b"):]
    assembler = assembler[:assembler.index("\ndef ", 10)]
    assert "benchmark_ligands()" not in assembler, (
        "assemble_tier_b resolves ligands itself again, so it can disagree "
        "with the regenerator about what the code writes"
    )


def test_the_scan_now_covers_tier_b():
    assert '"tier_b_": "regenerate_tier_b"' in INPUTS_SOURCE, (
        "the regenerated scan no longer has a Tier B regenerator, so the "
        "arm is back to being not_applicable"
    )
    assert "regenerate_all" in INPUTS_SOURCE, (
        "the main campaign's regenerator is gone"
    )


def test_the_regenerator_reproduces_the_arm_on_disk():
    """The decisive check, and it is why the refactor is trustworthy.

    1,540 YAMLs, byte for byte. A refactor of an assembler the chain will
    execute is worth doing only with a test that compares it against what
    the assembler already produced.
    """
    campaign = _tier_b()
    if campaign is None:
        pytest.skip("no Tier B campaign on this checkout")
    from nobble.execute import campaign as assembler

    fresh = assembler.regenerate_tier_b()
    rows = [json.loads(line) for line
            in (campaign / "queue.jsonl").read_text().splitlines()
            if line.strip()]
    assert rows, "the Tier B queue is empty, so this compared nothing"

    on_disk = {row["job_id"] for row in rows}
    assert set(fresh) == on_disk, {
        "regenerated_only": sorted(set(fresh) - on_disk)[:3],
        "queue_only": sorted(on_disk - set(fresh))[:3]}

    differing, compared = [], 0
    for row in rows:
        path = Path(row["yaml"])
        if not path.is_file():
            continue
        compared += 1
        if path.read_text() != fresh[row["job_id"]]:
            differing.append(row["job_id"])
    assert compared == len(rows), (
        f"only {compared} of {len(rows)} YAMLs were on disk, so this "
        "compared a subset and a clean answer means less than it looks"
    )
    assert differing == [], differing[:3]


def test_the_scan_calls_the_arm_clean_rather_than_not_applicable():
    campaign = _tier_b()
    if campaign is None:
        pytest.skip("no Tier B campaign on this checkout")
    from nobble.validate import inputs

    rows, status = inputs._regenerated_scan(campaign)
    assert rows == [], rows[:3]
    assert status.startswith("clean"), status
    assert "1540" in status, (
        f"the status does not say how many YAMLs produced it: {status}"
    )


def test_a_campaign_from_neither_assembler_is_still_not_applicable():
    """The distinction the docstring is careful about.

    "The comparison failed" is an unknown and the publish gate must refuse
    on it. "There is no comparison to make" is neither a pass nor a
    failure, and reporting it as unavailable once refused a legitimate
    build from the benchmark campaign.
    """
    from nobble.validate import inputs

    # `design` came out when F341 gave it a regenerator, one commit after
    # F340 named it as the remaining gap. The two that stay are complete
    # campaigns whose compute is spent and which the chain does not run
    # again, so a guard that refuses before the work has no work to get in
    # front of.
    for prefix in ("benchmark", "corrected"):
        found = sorted(ROOT.glob(f"campaigns/{prefix}_*"))
        found = [d for d in found if (d / "queue.jsonl").exists()]
        if not found:
            continue
        _rows, status = inputs._regenerated_scan(found[-1])
        assert status.startswith("not_applicable"), (prefix, status)


def test_the_regenerator_writes_nothing(tmp_path, monkeypatch):
    """The reason `_regenerate` exists at all.

    Re-deriving a YAML used to mean calling the assembler, which writes a
    whole campaign directory, and both the chain and `tools/status.sh` pick
    their campaign by the newest such directory. A scratch assembly would
    have become "the latest campaign".
    """
    from nobble.execute import campaign as assembler

    before = sorted(p.name for p in (ROOT / "campaigns").iterdir())
    assembler.regenerate_tier_b()
    after = sorted(p.name for p in (ROOT / "campaigns").iterdir())
    assert after == before, (
        "regenerating Tier B created or removed a campaign directory: "
        f"{set(after) ^ set(before)}"
    )


# F341. The design assembler, which F340 named and left.

def _design():
    found = sorted(ROOT.glob("campaigns/design_*"))
    found = [d for d in found if (d / "campaign.json").exists()]
    return found[-1] if found else None


def test_the_design_assembler_shares_its_renderer_too():
    source = (ROOT / "nobble" / "design" / "assemble.py").read_text()
    assert "def _design_rendered(manifest: dict):" in source
    assert source.count("_design_rendered(manifest)") == 2, (
        "the design renderer has other than two consumers; it exists so "
        "the assembler and the provenance check cannot diverge"
    )
    # The ligand branch is where F262 happened, so it must not be duplicated
    # back into the assembler.
    body = source[source.index("def assemble(parent_id: str"):]
    body = body[:body.index("\ndef ", 10)] if "\ndef " in body[10:] else body
    assert "L.by_smiles(" not in body, (
        "assemble() resolves ligands itself again, which is the branch F262 "
        "broke and the one most worth having a single copy of"
    )


def test_the_design_regenerator_reproduces_the_scan_on_disk():
    """240 YAMLs, byte for byte.

    F340 declined to write this regenerator on the grounds that one written
    without a campaign to verify it against would be a guess. There is a
    campaign, and its campaign.json records the parent to regenerate from,
    so the guess was avoidable.
    """
    campaign = _design()
    if campaign is None:
        pytest.skip("no design campaign on this checkout")
    from nobble.design import assemble

    meta = json.loads((campaign / "campaign.json").read_text())
    fresh = assemble.regenerate_design(
        meta["parent"], meta.get("generator") or "alanine_scan")
    rows = [json.loads(line) for line
            in (campaign / "queue.jsonl").read_text().splitlines()
            if line.strip()]
    assert rows, "the design queue is empty, so this compared nothing"
    assert set(fresh) == {row["job_id"] for row in rows}, {
        "regenerated_only": sorted(set(fresh) - {r["job_id"] for r in rows})[:3],
        "queue_only": sorted({r["job_id"] for r in rows} - set(fresh))[:3]}

    differing, compared = [], 0
    for row in rows:
        path = Path(row["yaml"])
        if not path.is_file():
            continue
        compared += 1
        if path.read_text() != fresh[row["job_id"]]:
            differing.append(row["job_id"])
    assert compared == len(rows), (
        f"only {compared} of {len(rows)} YAMLs were on disk, so a clean "
        "answer here means less than it looks"
    )
    assert differing == [], differing[:3]


def test_the_scan_regenerates_a_design_campaign_from_its_recorded_parent():
    """Not from today's ranked choice, which is a different question.

    Whether the parent is still the one the ranking would pick is F338's
    question and `tools/run_design.sh` asks it. This one is whether the
    YAML is what the code would write *for the parent this scan has*, and
    regenerating from a different parent would answer neither.
    """
    source = (ROOT / "nobble" / "validate" / "inputs.py").read_text()
    assert '"design_": "regenerate_design"' in source
    assert 'meta.get("parent")' in source, (
        "the scan no longer takes the design campaign's own parent, so it "
        "regenerates something other than the scan in front of it"
    )
    # And an absent parent is unavailable, not clean.
    window = source[source.index('if chosen == "regenerate_design":'):]
    window = window[:window.index("else:")]
    assert "unavailable: no campaign.json" in window
    assert "records no" in window and "parent" in window


def test_all_three_assemblers_the_chain_runs_are_covered():
    """The scope, stated as an assertion.

    `benchmark_*` and `corrected_*` stay out, and that is deliberate
    rather than unfinished: both are complete campaigns whose compute is
    spent and neither is a stage the chain runs again, so a guard that
    refuses before the work has no work to get in front of.
    """
    from nobble.validate import inputs

    clean, scoped = {}, 0
    for prefix in ("campaign_", "design_", "tier_b_"):
        found = sorted(ROOT.glob(f"campaigns/{prefix}*"))
        found = [d for d in found if (d / "queue.jsonl").exists()]
        if not found:
            continue
        scoped += 1
        rows, status = inputs._regenerated_scan(found[-1])
        clean[prefix] = (len(rows), status)
        assert not status.startswith("not_applicable"), (prefix, status)
    assert scoped >= 1, (
        "none of the three assemblers' campaigns is on this checkout, so "
        "this examined nothing"
    )
    for prefix, (count, status) in clean.items():
        assert count == 0, (prefix, status)
        assert status.startswith("clean"), (prefix, status)
