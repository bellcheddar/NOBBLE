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
    assert not drifted, (
        "the same job id predicts different interfaces in two campaigns, so "
        f"something upstream of Boltz changed: {drifted[:5]}"
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
