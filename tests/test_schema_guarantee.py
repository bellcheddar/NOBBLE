"""Every scored pair carries every key, whichever branches ran.

run.score_campaign has a block whose comment explains itself:

    A pair whose PLIP or geometry has not run yet must still carry every
    key, as null, rather than omitting it: a consumer that reaches for a
    missing key gets an error instead of a "not computed", and the app's
    Benchmark tab did exactly that on the first pair whose ternary arm had
    not finished.

The block is right and it is maintained by hand, so it goes out of date
exactly when something new is added. Three fields added during this
session were set only on the branch that computes them:
`bridging_unmeasurable_reasons` was absent whenever there were no
unmeasurable seeds, which is every pair in both campaigns, and
`plip_fingerprint_match_status` was absent whenever PLIP had not run,
which `--no-plip` makes a real path.

So this derives the key set from a scored pair rather than restating it,
and requires it to be the same across every branch combination. A field
added on one branch and not the others fails here instead of on the first
consumer that reaches for it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Keys that legitimately appear only sometimes, with the reason.
OPTIONAL = {
    "errors": "only when a stage raised, and its absence is the healthy case",
}


def _score(tmp_path, results, monkeypatch=None, **kwargs):
    """Score a trimmed campaign, with the two expensive stages stubbed.

    This file is about which keys a record carries, not about geometry or
    PLIP. Running them for real took 112 seconds against a 28-second suite,
    and a slow test is a test that gets skipped.
    """
    from nobble.score import geometry, run as run_module

    campaign = tmp_path / f"c_{abs(hash(str(kwargs)))}"
    campaign.mkdir()
    (campaign / "results.jsonl").write_text(results)

    if monkeypatch is not None:
        monkeypatch.setattr(
            run_module.geometry, "score_structure",
            lambda job: geometry.BridgeScore(
                job_id=job["job_id"], structure=job.get("structure", ""),
                found=True, dsasa_total=300.0, dsasa_receptor=150.0,
                dsasa_peptide=150.0, contacts_receptor=8, contacts_peptide=6,
                bridging_balance=0.5, buried_fraction=0.4, heavy_atoms=31,
                bridge_percentile=88.0, percentile_basis="stubbed",
            ),
        )
        monkeypatch.setattr(run_module.geometry, "contact_map",
                            lambda job: {"status": "ok", "contacts": []})

        class _Finger:
            status = "ok"
            canonical_matched = ["TRP380", "TRP386"]
            canonical_missing = []
            peptide_contacts = ["GLY1"]
            canonical_e3 = "CRBN"

            def to_dict(self):
                return {"status": "ok"}

        monkeypatch.setattr(run_module.plip, "fingerprint", lambda job: _Finger())

    run_module.score_campaign(campaign, **kwargs)
    return [json.loads(line) for line
            in (campaign / "scores.jsonl").read_text().splitlines() if line.strip()]


def _real_results(pairs: int = 3):
    """A few real pairs: enough to compare key sets, not the whole campaign."""
    import glob

    for path in sorted(glob.glob(str(ROOT / "campaigns" / "*" / "results.jsonl"))):
        lines = [l for l in Path(path).read_text().splitlines() if l.strip()]
        if not lines:
            continue
        wanted, kept = [], set()
        for line in lines:
            pair_id = json.loads(line)["pair_id"]
            if pair_id not in kept and len(kept) >= pairs:
                continue
            kept.add(pair_id)
            wanted.append(line)
        return "\n".join(wanted) + "\n"
    pytest.skip("no scored campaign on this checkout")


def test_every_pair_carries_the_same_keys_with_plip_off(tmp_path, monkeypatch):
    rows = _score(tmp_path, _real_results(), monkeypatch, with_plip=False)
    assert len(rows) > 1, "need several pairs to compare key sets"
    union = set().union(*(set(row) for row in rows))
    for row in rows:
        missing = union - set(row) - set(OPTIONAL)
        assert not missing, f"{row['pair_id']} is missing {sorted(missing)}"


def test_the_key_set_does_not_depend_on_whether_plip_ran(tmp_path, monkeypatch):
    """The branch that was absent. A consumer cannot be asked to know which
    flags a campaign was scored with."""
    results = _real_results()
    without = _score(tmp_path, results, monkeypatch, with_plip=False)
    with_plip = _score(tmp_path, results, monkeypatch, with_plip=True)

    keys_without = set().union(*(set(row) for row in without)) - set(OPTIONAL)
    keys_with = set().union(*(set(row) for row in with_plip)) - set(OPTIONAL)
    assert keys_without == keys_with, {
        "only when plip ran": sorted(keys_with - keys_without),
        "only when it did not": sorted(keys_without - keys_with),
    }


def test_the_fields_added_this_session_are_always_present(tmp_path, monkeypatch):
    """Named explicitly, so the derived checks above cannot pass by having
    all branches equally incomplete."""
    rows = _score(tmp_path, _real_results(), monkeypatch, with_plip=False)
    required = (
        "bridging_seeds_unmeasurable", "bridging_unmeasurable_reasons",
        "plip_fingerprint_match", "plip_fingerprint_match_status",
        "pair_level_disagreements",
    )
    for row in rows:
        for key in required:
            assert key in row, f"{row['pair_id']} has no {key}"


def test_a_skipped_fingerprint_says_why_rather_than_being_null(tmp_path, monkeypatch):
    """A null with no reason is the thing this project keeps finding: the
    difference between refused, failed, and never attempted has to survive
    into the record."""
    rows = _score(tmp_path, _real_results(), monkeypatch, with_plip=False)
    for row in rows:
        status = row["plip_fingerprint_match_status"]
        assert status and status.startswith("not_computed:"), status
        assert "not run" in status or "no ternary" in status, status
        assert row["plip_fingerprint_match"] is None


def test_the_unmeasurable_reasons_default_to_an_empty_mapping(tmp_path, monkeypatch):
    """Not null: consumers index it, and `{}` is the shape that means none."""
    rows = _score(tmp_path, _real_results(), monkeypatch, with_plip=False)
    for row in rows:
        assert row["bridging_unmeasurable_reasons"] == {}, row["pair_id"]
