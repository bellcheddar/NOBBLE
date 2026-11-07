"""Wrong site and wrong register are different failures with one RMSD.

Pose recovery reports 0 of 65 within 3 A and a median of 17.54 A (F212). That
number is consistent with the model never finding the degron site, and it is
equally consistent with the model finding the site and laying the chain along
it in the wrong register. The headline reads differently in each case, and
`tools/pose_site.py` is the measurement that tells them apart: footprints on
the receptor, in the frame the RMSD already superposes.

What these tests hold is the honesty of that measurement rather than its
values, which are a property of the campaign and will change when bench02 is
re-run.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE = (ROOT / "tools" / "pose_site.py").read_text()


def _module():
    spec = importlib.util.spec_from_file_location(
        "pose_site", ROOT / "tools" / "pose_site.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _newest_campaign() -> Path | None:
    from nobble.execute.campaign import latest
    campaign = latest("campaign") or latest("benchmark")
    return Path(campaign) if campaign else None


def test_the_cutoff_comes_from_config():
    from nobble import paths

    expected = next(float(section["contact_cutoff_a"])
                    for section in paths.thresholds().values()
                    if isinstance(section, dict) and "contact_cutoff_a" in section)
    assert _module().contact_cutoff() == expected


def test_no_acceptance_threshold_is_applied_to_the_overlap():
    """D-NOB-076 refused to invent a success radius to decide pose recovery.

    A tool that printed "right site" above some Jaccard would be doing the
    same thing one column over: an acceptance cutoff, in Python, deciding how
    a failed positive control reads. The first draft of this tool had exactly
    that, `jacc >= 0.3`, and it is gone.
    """
    import ast

    tree = ast.parse(SOURCE)

    # No float literal anywhere in the code. Every distance this tool uses
    # comes from config, every rounding argument is an integer, and a float
    # written into the source would be a cutoff by another name.
    #
    # Checked structurally rather than by searching the text: the first
    # version of this test banned the phrase "the right site" and failed on
    # the docstring that explains why the tool does not print it, which is
    # the same mistake as counting `trap` occurrences in one's own comments.
    floats = [node.value for node in ast.walk(tree)
              if isinstance(node, ast.Constant) and isinstance(node.value, float)]
    assert not floats, f"float literal(s) in the source: {floats}"

    # And nothing compares the overlap against anything.
    def _mentions_overlap(node) -> bool:
        return any(
            isinstance(inner, ast.Constant) and inner.value in
            ("jaccard", "shared_contacts")
            or isinstance(inner, ast.Name) and inner.id in ("jaccard", "shared")
            for inner in ast.walk(node))

    # Against a number, specifically. `'jaccard' not in record` and
    # `record['jaccard'] is not None` are presence checks, not thresholds,
    # and a test that banned them would be banning the tool from reporting
    # the field at all.
    def _against_a_number(node) -> bool:
        return any(isinstance(c, ast.Constant) and isinstance(c.value, (int, float))
                   and not isinstance(c.value, bool)
                   for c in node.comparators)

    offenders = [ast.unparse(node) for node in ast.walk(tree)
                 if isinstance(node, ast.Compare)
                 and _mentions_overlap(node) and _against_a_number(node)]
    assert not offenders, offenders


def test_a_window_that_touches_no_receptor_is_not_scored_as_zero_overlap():
    """Zero overlap that is guaranteed is not a measurement.

    bench03_BRD4_CRBN's deposited degron window sits against the glue rather
    than against CRBN, so no pose of any quality can share a receptor contact
    with it. Reporting that as a Jaccard of 0.0 beside bench07's real 0.0
    would put a pair that cannot be measured next to one that was measured
    and failed.
    """
    campaign = _newest_campaign()
    if campaign is None:
        pytest.skip("no campaign assembled")
    module = _module()
    records = module.footprints(campaign, only={"bench03_BRD4_CRBN"})
    if not records:
        pytest.skip("this campaign has no pose recovery detail for the pair")
    record = records[0]
    if record.get("deposited_contacts") != 0:
        pytest.skip("the deposited window now contacts the receptor, so the "
                    "pair is measurable and this case has moved elsewhere")
    assert record["status"].startswith("not_measurable"), record


def test_a_confounded_pair_is_flagged_rather_than_reported():
    """Its poses came from an input that is no longer on disk (F219)."""
    campaign = _newest_campaign()
    if campaign is None:
        pytest.skip("no campaign assembled")
    module = _module()
    confounded = module._confounded(campaign)
    if not confounded:
        pytest.skip("no pair is confounded, so the correction has run")
    pair = sorted(confounded)[0]
    records = module.footprints(campaign, only={pair})
    if not records:
        pytest.skip(f"{pair} has no pose recovery detail")
    assert records[0]["status"] == "confounded", records[0]


def test_an_unrunnable_featurisation_check_does_not_clear_every_pair():
    """A failed import must not read as "nothing is confounded" (F216)."""
    module = _module()
    source = (ROOT / "tools" / "pose_site.py").read_text()
    assert "return set()" in source
    # The only two ways to reach that empty set are an ImportError and an
    # OSError from the comparison itself, both of which are the absence of an
    # answer. Neither may be reached by a comparison that ran and found
    # disagreements.
    body = source[source.index("def _confounded"):source.index("def _best_per_pair")]
    assert body.count("return set()") == 2, body
    assert "disagreements(campaign)" in body


def test_the_per_residue_profile_accompanies_every_measured_record():
    """A whole-window RMSD cannot say where along the chain the error is.

    Those are different claims. A uniform 5 A is a displaced peptide; 0.5 A
    in the middle with 10 A at both ends is a degron placed correctly inside
    a window that extends past it. bench04 and bench06 are the second, and no
    single number can show it.
    """
    campaign = _newest_campaign()
    if campaign is None:
        pytest.skip("no campaign assembled")
    module = _module()
    records = module.footprints(campaign, only={"bench04_IKZF1_CRBN"})
    if not records or "jaccard" not in records[0]:
        pytest.skip("the pair has no measurable pose in this campaign")
    record = records[0]
    profile = record["ca_deviation_a"]
    assert profile, record
    assert all(value is None or value >= 0 for value in profile), profile
    measured = [value for value in profile if value is not None]
    assert len(measured) >= 2, profile


def test_the_profile_is_one_value_per_peptide_residue():
    """Not per backbone atom, and not per deposited residue.

    A profile indexed differently from the peptide would still plot, and the
    position of the minimum would mean nothing.
    """
    campaign = _newest_campaign()
    if campaign is None:
        pytest.skip("no campaign assembled")
    module = _module()
    records = module.footprints(campaign, only={"bench04_IKZF1_CRBN"})
    if not records or "ca_deviation_a" not in records[0]:
        pytest.skip("no measurable pose")
    from nobble.score import poses as poses_module

    structure = poses_module._load(records[0]["job_id"] and
                                   _structure_of(campaign, records[0]["job_id"]))
    peptide = [chain for chain in structure[0]
               if chain.name == poses_module.PEPTIDE_CHAIN]
    assert peptide, "the prediction has no peptide chain"
    assert len(records[0]["ca_deviation_a"]) == len(list(peptide[0]))


def _structure_of(campaign: Path, job_id: str) -> str:
    import json

    for line in (campaign / "results.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("job_id") == job_id:
            return row["structure"]
    raise AssertionError(f"{job_id} is not in results.jsonl")
