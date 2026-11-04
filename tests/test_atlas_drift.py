"""Is the published atlas what the current code builds?

F93's superseded-substrate caveat was written, tested and committed, and was
not on the page. `comparison.json` is built by the atlas, the atlas had not
been rebuilt, so the published conclusion ended before the caveat and a
deploy carried it to the droplet unchanged. Nothing noticed, because nothing
compared the published bundle against what the code would produce (F96).

F88 made that comparison by hand after a day of scoring changes, diffing
11,002 leaf values. `tools/atlas_drift.py` is that comparison as a command,
and `deploy.sh` refuses rather than publishing a bundle that has drifted
(F97).

Refusing rather than rebuilding, deliberately. A deploy that silently
rebuilds publishes something nobody looked at, and the rebuild is one
command whose output an operator should see.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import atlas_drift  # noqa: E402

PUBLISHED = ROOT / "deploy" / "atlas"


def _requires_atlas():
    if not (PUBLISHED / "ATLAS.json").exists():
        pytest.skip("no published atlas")


def test_the_published_atlas_is_in_step():
    """The state that should hold after every deploy. A failure here means
    the bundle on the droplet predates a change to the code."""
    _requires_atlas()
    report = atlas_drift.drift()
    assert report["status"] == "in step", report["moved"][:3]
    assert report["compared"] > 1000, report["compared"]


def test_it_detects_the_drift_that_f96_was():
    """The negative control, and the exact case: a caveat present in the
    code's output and absent from the published conclusion."""
    _requires_atlas()
    comparison = PUBLISHED / "comparison.json"
    if not comparison.exists():
        pytest.skip("no comparison in the published atlas")

    original = comparison.read_text()
    payload = json.loads(original)
    conclusion = payload.get("conclusion") or ""
    if len(conclusion) < 40:
        pytest.skip("no published conclusion to perturb")
    # Truncated at its last sentence boundary rather than at a named caveat.
    # This used to cut at ". 1 pair(s) used a substrate" and skip when that
    # phrase was absent, so when F107 removed the superseded-substrate
    # caveat by fixing the plan it described, the control for this whole
    # check went quiet instead of continuing to run. A test that skips is
    # not a test that passes, and the F96 case is the one it exists to
    # catch.
    cut = conclusion.rfind(". ")
    if cut < 20:
        cut = len(conclusion) // 2
    try:
        payload["conclusion"] = conclusion[:cut]
        comparison.write_text(json.dumps(payload, indent=2))
        report = atlas_drift.drift()
        assert report["status"] == "drifted", report
        keys = [row["key"] for row in report["moved"]]
        assert "comparison.json.conclusion" in keys, keys
    finally:
        comparison.write_text(original)

    assert atlas_drift.drift()["status"] == "in step", (
        "the atlas was not restored after the control"
    )


def test_build_time_facts_are_not_drift():
    """`built_at`, byte counts and the outstanding-campaign list move on
    every build by design. Counting them would make the check fire always,
    which is the same as never."""
    for field in ("built_at", "bytes", "atlas_bytes", "outstanding",
                  "jobs_done", "measured_at"):
        assert field in atlas_drift.VOLATILE, field


def test_the_science_is_not_excluded():
    """The other half of the exclusion list. A redaction count is a fact
    about what was withheld, not about the build, and F72 found it
    misreported, so it must not be excused as volatile."""
    for field in ("redactions", "redacted_ligands", "conclusion",
                  "median_rmsd", "auc"):
        assert not any(v in field for v in atlas_drift.VOLATILE), field


def test_deploy_refuses_a_drifted_atlas():
    """The wiring (F40), and where it matters: the F96 deploy carried a
    stale bundle because nothing checked before the rsync."""
    source = (ROOT / "deploy" / "deploy.sh").read_text()
    assert "tools/atlas_drift.py" in source
    assert "REFUSING TO DEPLOY" in source
    assert source.index("atlas_drift.py") < source.index(
        "sync the published atlas"), (
        "the drift check runs after the atlas is already synced"
    )


def test_the_status_report_shows_it():
    """A drift noticed at deploy time is a refused deploy; a drift noticed
    in status is a rebuild."""
    source = (ROOT / "tools" / "provenance.py").read_text()
    assert "atlas_drift" in source


def test_cost_recomputed_from_new_timings_is_not_a_failure():
    """The gap F97 left one line from its own exclusion list.

    VOLATILE excluded `throughput` and not the values computed from it. A
    running campaign remeasures its token bands after every job, so every
    design preview's cost moves: thirteen jobs after F97 was committed the
    check reported 63 drifted values, all of them costs, and printed six of
    them with "and 57 more". The same mistake as F74, F78 and F89: the
    source handled, the consumers not (F101).
    """
    _requires_atlas()
    report = atlas_drift.drift()
    assert "recomputed" in report
    if not report["recomputed"]:
        # Nothing has been recomputed since the atlas was built, so there is
        # nothing to classify. Skipped rather than looped over an empty list,
        # so the never-executed-assertion sweep can tell a deliberate gap
        # from a silent one (F152).
        pytest.skip("no recomputed values in the current atlas")
    for row in report["recomputed"]:
        assert row["key"].endswith(atlas_drift.RECOMPUTED), row["key"]


def test_the_recomputed_category_is_matched_on_the_whole_leaf_name():
    """"cost" as a substring would swallow any key with cost in its path.
    Each pattern must be a full leaf name, so the category cannot widen by
    accident."""
    for pattern in atlas_drift.RECOMPUTED:
        assert pattern.startswith("."), pattern
        assert pattern.count(".") == 2, pattern
    assert "cost" not in atlas_drift.RECOMPUTED
    assert "basis" not in atlas_drift.RECOMPUTED


def test_the_science_is_not_recomputed_either():
    """The same guard as `test_the_science_is_not_excluded`, against the
    second category. A conclusion or a redaction count has no business
    being filed under new timings."""
    for field in ("redactions", "redacted_ligands", "conclusion",
                  "median_rmsd", "auc", "delta_iptm", "bridge_percentile"):
        assert not any(field in pattern for pattern in atlas_drift.RECOMPUTED), field


def test_a_real_drift_is_not_buried_behind_cost_churn():
    """The control, and the reason the split exists rather than a wider
    exclusion. With sixty-odd costs legitimately moving, a stripped
    conclusion must still be the thing the check reports and the thing it
    fails on."""
    _requires_atlas()
    published = atlas_drift.PUBLISHED / "comparison.json"
    original = published.read_text()
    data = json.loads(original)
    conclusion = data.get("conclusion")
    if not isinstance(conclusion, str) or len(conclusion) < 40:
        pytest.skip("no conclusion string to perturb")

    data["conclusion"] = conclusion[: len(conclusion) // 2]
    published.write_text(json.dumps(data, indent=2))
    try:
        report = atlas_drift.drift()
    finally:
        published.write_text(original)
    assert published.read_text() == original, "the control failed to restore"

    assert report["status"] == "drifted"
    keys = [row["key"] for row in report["moved"]]
    assert "comparison.json.conclusion" in keys, keys[:5]
    # And it is not competing for the six printed lines with the costs.
    assert not any(key.endswith(atlas_drift.RECOMPUTED) for key in keys), keys[:5]
    # It is the first thing printed, not the 58th.
    assert keys.index("comparison.json.conclusion") < 6, keys[:8]


def test_the_check_passes_while_only_costs_move():
    """The state right now: the atlas content is in step and the costs are
    not. That must read as a pass, or the deploy refusal fires for the whole
    length of every campaign and stops meaning anything."""
    _requires_atlas()
    report = atlas_drift.drift()
    if not report.get("recomputed"):
        pytest.skip("no recomputed values to distinguish from drift")
    assert report["status"] == "in step", report["moved"][:3]
    assert atlas_drift.main(["--quiet"]) == 0
