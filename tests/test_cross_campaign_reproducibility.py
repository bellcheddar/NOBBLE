"""The benchmark panel must predict the same thing in every campaign.

Every campaign runs the seven benchmark pairs first, with the same
constructs, the same peptides, the same ligands and the same five seeds.
Boltz is deterministic given one YAML and one seed, so a job id that
appears in two campaigns must carry the same numbers in both.

That makes the overlap a canary for the whole input-generation path. A
construct boundary that moved (F41), a receptor that lost its cached MSA
(F39), a structural zinc that stopped being added (D-NOB-034), a pocket
constraint that appeared on an unconstrained arm: none of those raise, and
every one of them changes the prediction for a job whose id did not
change.

Checked against the campaigns on disk rather than by rerunning anything,
and the first nine shared jobs of the main campaign reproduced the
benchmark campaign's to every decimal place recorded.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _scored(path: Path) -> dict[str, dict]:
    out = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("confidence"):
            out[row["job_id"]] = row
    return out


def _campaign_pairs():
    """Every pair of campaigns that scored at least one job id in common."""
    campaigns = {}
    for results in sorted(glob.glob(str(ROOT / "campaigns" / "*" / "results.jsonl"))):
        path = Path(results)
        scored = _scored(path)
        if scored:
            campaigns[path.parent.name] = scored

    names = sorted(campaigns)
    for index, first in enumerate(names):
        for second in names[index + 1:]:
            shared = set(campaigns[first]) & set(campaigns[second])
            if shared:
                yield first, second, campaigns[first], campaigns[second], sorted(shared)


# Job ids known to differ between campaigns, with the reason and what has to
# happen before the entry goes. An expected failure that is named is a record;
# an unnamed one is a red suite that trains you to ignore it.
#
# **Empty, and that is the end state rather than a gap.**
#
# It held bench02_BRD4_VHL's fifteen jobs, emitted with a hydroxyproline on
# BRD4 Pro379 because the modification rule keyed on the E3 rather than on the
# degron class (F47). The rule and the library were fixed the same day; the
# YAMLs already on disk were not, and correcting them mid-run would have left
# one pair holding two different inputs, so the entry recorded the debt and
# `test_the_known_drift_is_still_drifting` below was the reminder.
#
# `tools/corrections.sh --apply` ran on 2026-11-07 and re-ran all fifteen
# against the corrected YAMLs. All fifteen now agree between campaigns, which
# is what made that test fail, so the entry goes and the strict check above
# becomes the live guard with nothing excluded from it.
#
# Kept as an empty dict rather than deleted, because the mechanism is worth
# having for the next correction and a named expected failure is a record
# where an unnamed one is a red suite that trains you to ignore it.
KNOWN_DRIFT: dict[str, str] = {}


def test_a_shared_job_predicts_the_same_interface_in_both_campaigns():
    from nobble.score import metrics

    comparisons = list(_campaign_pairs())
    if not comparisons:
        pytest.skip("no two campaigns share a scored job id on this checkout")

    drifted = []
    checked = 0
    for first, second, left, right, shared in comparisons:
        for job_id in shared:
            a = metrics.seed_record(left[job_id]).iptm_receptor_peptide
            b = metrics.seed_record(right[job_id]).iptm_receptor_peptide
            if a is None or b is None:
                continue
            checked += 1
            if abs(a - b) > 1e-6:
                drifted.append((job_id, first, round(a, 4), second, round(b, 4)))

    assert checked, "no shared job carried a comparable number"
    unexplained = [row for row in drifted if row[0] not in KNOWN_DRIFT]
    assert not unexplained, (
        "the same job id predicts different interfaces in two campaigns, so "
        f"something upstream of Boltz changed: {unexplained[:5]}"
    )


def test_the_known_drift_is_still_drifting():
    """An allowlist that outlives what it allows is a hole.

    When `tools/rerun_pair.py` has corrected those fifteen jobs they will
    agree again, and this fails until the entry is removed, which is the
    only reminder that the correction is done.
    """
    from nobble.score import metrics

    comparisons = list(_campaign_pairs())
    if not comparisons:
        pytest.skip("no two campaigns share a scored job id")

    still_drifting, present = set(), set()
    for _first, _second, left, right, shared in comparisons:
        for job_id in shared:
            if job_id not in KNOWN_DRIFT:
                continue
            present.add(job_id)
            a = metrics.seed_record(left[job_id]).iptm_receptor_peptide
            b = metrics.seed_record(right[job_id]).iptm_receptor_peptide
            if a is not None and b is not None and abs(a - b) > 1e-6:
                still_drifting.add(job_id)

    if not KNOWN_DRIFT:
        pytest.skip("the allowlist is empty, so the strict check above is the "
                    "guard and there is nothing here to retire")
    if not present:
        pytest.skip("none of the known-drifted jobs has been scored in two "
                    "campaigns yet")
    agreed = present - still_drifting
    assert not agreed, (
        f"{len(agreed)} job(s) in KNOWN_DRIFT now agree between campaigns, so "
        f"the correction has landed and the entries should go: {sorted(agreed)[:5]}"
    )


def test_a_shared_job_was_given_the_same_token_count():
    """The cheapest symptom of a changed construct or peptide, and the one
    that would move before the confidence did."""
    comparisons = list(_campaign_pairs())
    if not comparisons:
        pytest.skip("no two campaigns share a scored job id")

    drifted = []
    for first, second, left, right, shared in comparisons:
        for job_id in shared:
            a, b = left[job_id].get("tokens"), right[job_id].get("tokens")
            if a is not None and b is not None and a != b:
                drifted.append((job_id, first, a, second, b))
    assert not drifted, f"token counts changed between campaigns: {drifted[:5]}"


def test_a_shared_job_used_the_same_yaml_chain_layout():
    """A zinc that stopped being added, or a ligand that appeared in the
    binary arm, changes the chain count without changing the job id."""
    import yaml

    comparisons = list(_campaign_pairs())
    if not comparisons:
        pytest.skip("no two campaigns share a scored job id")

    def layout(row):
        path = row.get("yaml")
        if not path or not Path(path).exists():
            return None
        document = yaml.safe_load(Path(path).read_text())
        return tuple(
            next(iter(entry)) + ":" + str(entry[next(iter(entry))].get("id"))
            for entry in document.get("sequences", [])
        )

    drifted, checked = [], 0
    for first, second, left, right, shared in comparisons:
        for job_id in shared:
            a, b = layout(left[job_id]), layout(right[job_id])
            if a is None or b is None:
                continue
            checked += 1
            if a != b:
                drifted.append((job_id, first, a, second, b))
    if not checked:
        pytest.skip("no shared job has both YAMLs still on disk")
    assert not drifted, f"chain layout changed between campaigns: {drifted[:3]}"
