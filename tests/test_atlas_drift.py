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
    if "no longer specifies" not in payload.get("conclusion", ""):
        pytest.skip("the published conclusion carries no caveat to remove")
    try:
        payload["conclusion"] = payload["conclusion"].split(
            ". 1 pair(s) used a substrate")[0]
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
