"""Each way the featurisation check can be blind, counted on its own.

`tools/stale_featurisation.coverage` reports `blind` as the sum of three
causes: a job whose YAML is gone, a job that ran with no cached featurisation,
and a cache whose npz carries no `chains` or `residues`. `deploy/build_atlas`
refuses when `blind` is non-zero, because a job it could not compare is a job
whose poses might have come from a superseded input and nobody can say.

So `blind` is the gate, and a sum is as weak an assertion as a count: with any
one cause no longer counted, the others still make it non-zero on whatever
campaign is in front of it. All three mutations were caught by nothing, even
though each cause's name appears in a test file, which is the same thing that
happened in preflight (F274) and the manifest (F275). The fifth gate with the
shape (F277).

Each cause gets a fixture here, and the fixture asserts the cause's own count
as well as `blind`, because the sum is what hid them.
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


def _module():
    spec = importlib.util.spec_from_file_location(
        "stale_featurisation", ROOT / "tools" / "stale_featurisation.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _npz(path: Path, *, usable: bool) -> None:
    """A cache the reader can parse, or one it cannot.

    The unusable one is a real npz with the wrong arrays in it, which is what
    a change in Boltz's cache format would look like: present, loadable, and
    carrying nothing this can compare.
    """
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    if not usable:
        np.savez(path, something_else=np.array([1, 2, 3]))
        return
    chains = np.array([("P", 0)], dtype=[("name", "S4"), ("res_idx", "i4")])
    residues = np.array([("PRO",)], dtype=[("name", "S4")])
    np.savez(path, chains=chains, residues=residues)


def _campaign(tmp_path: Path, case: str) -> dict:
    """A one-job campaign in one of the states `coverage` distinguishes."""
    # One directory per case, because the identity test below walks all five
    # with a single tmp_path and a shared directory made the second case's
    # mkdir collide with the first's.
    campaign = tmp_path / f"campaign_blind_{case}"
    (campaign / "yaml").mkdir(parents=True, exist_ok=True)
    yaml_path = campaign / "yaml" / "j1.yaml"
    yaml_path.write_text(yaml_lib.safe_dump({"version": 1, "sequences": [
        {"protein": {"id": "P", "sequence": "PFQCNQCGASFTQKG", "msa": "empty"}},
    ]}))
    output = campaign / "outputs" / "j1"
    npz = (output / "boltz_results_j1" / "processed" / "structures" / "j1.npz")

    if case == "missing_yaml":
        yaml_path.unlink()
        output.mkdir(parents=True)
    elif case == "no_cache":
        output.mkdir(parents=True)
    elif case == "unreadable_cache":
        _npz(npz, usable=False)
    elif case == "no_output":
        pass
    elif case == "checked":
        _npz(npz, usable=True)
    else:
        raise AssertionError(case)

    (campaign / "queue.jsonl").write_text(json.dumps(
        {"job_id": "j1", "pair_id": "p1", "yaml": str(yaml_path)}) + "\n")
    return _module().coverage(campaign)


def test_a_missing_yaml_is_blind(tmp_path):
    seen = _campaign(tmp_path, "missing_yaml")
    assert seen["missing_yaml"] == 1, seen
    assert seen["blind"] == 1, seen


def test_a_job_that_ran_with_no_cache_is_blind(tmp_path):
    seen = _campaign(tmp_path, "no_cache")
    assert seen["no_cache"] == 1, seen
    assert seen["blind"] == 1, seen


def test_a_cache_with_the_wrong_arrays_is_blind(tmp_path):
    """What a change in Boltz's cache format would look like."""
    seen = _campaign(tmp_path, "unreadable_cache")
    assert seen["unreadable_cache"] == 1, seen
    assert seen["blind"] == 1, seen


def test_a_job_that_has_not_run_is_not_blind(tmp_path):
    """The one state that is neither checked nor blind.

    Without this the three above could pass by calling everything blind,
    which would refuse every build of a campaign that is still running.
    """
    seen = _campaign(tmp_path, "no_output")
    assert seen["no_output"] == 1, seen
    assert seen["blind"] == 0, seen
    assert seen["checked"] == 0, seen


def test_a_comparable_job_is_checked_and_not_blind(tmp_path):
    seen = _campaign(tmp_path, "checked")
    assert seen["checked"] == 1, seen
    assert seen["blind"] == 0, seen


def test_blind_is_the_sum_of_its_three_causes(tmp_path):
    """Stated as an identity, so a cause dropped from the sum is caught.

    The fixtures above each hold one cause, so each on its own cannot tell
    whether `blind` counts that cause or merely counts something.
    """
    for case in ("missing_yaml", "no_cache", "unreadable_cache", "no_output",
                 "checked"):
        seen = _campaign(tmp_path, case)
        assert seen["blind"] == (seen["no_cache"] + seen["unreadable_cache"]
                                 + seen["missing_yaml"]), (case, seen)


def test_the_examples_name_the_blind_jobs(tmp_path):
    """A count without names cannot be acted on.

    The builder prints these, and an operator with "3 blind" and no job ids
    has to go and find them.
    """
    seen = _campaign(tmp_path, "no_cache")
    assert seen["blind_examples"] == ["j1"], seen
