""""Published" names two things, and only one of them is the site.

`deploy/atlas/` is a build directory. The droplet is a host. Deploying is an
rsync between them that `tools/publication_hold.py` refuses as the first
pre-flight step of `deploy/deploy.sh`, so the two diverge by design whenever
the hold is on.

F261 read the build directory and reported what the site publishes. The site
publishes the benchmark panel; the build directory holds the main campaign.
The correction is recorded under F261; this is the check that would have
caught it, and the instrument is a request to the site rather than a file
read.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "deploy" / "atlas"
SITE = "https://nobble.mdeller.com"


def _live(path: str) -> dict | None:
    """The live site's JSON, or None when it cannot be reached.

    Skipped rather than failed on a network problem: this asserts what the
    site says when it answers, and a test that fails without a network would
    fail on every machine that is not this one.
    """
    out = subprocess.run(["curl", "-s", "--max-time", "25", SITE + path],
                         capture_output=True, text=True)
    if out.returncode != 0 or not out.stdout.strip():
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return None


def test_the_build_directory_is_not_the_site():
    """And if they ever agree, say so rather than asserting they differ.

    The point is not that they must differ; it is that a claim about one is
    not a claim about the other. So this reports the pair and only fails if
    the local bundle names no campaign at all.
    """
    if not (ATLAS / "ATLAS.json").exists():
        pytest.skip("no local bundle built")
    local = json.loads((ATLAS / "ATLAS.json").read_text()).get("campaign")
    assert local, "the local bundle names no campaign"
    state = _live("/api/state")
    if state is None:
        pytest.skip("the site could not be reached")
    served = state.get("campaign_id")
    assert served, state
    if served == local:
        # Deployed and up to date. Nothing to warn about.
        return
    # Divergent, which is what the hold produces. The assertion is that the
    # hold is on, because a divergence with no hold is an undeployed build
    # nobody decided to withhold.
    held = ROOT / "config" / "publication_hold.toml"
    assert held.exists(), (
        f"the site serves {served} and the bundle holds {local}, and there is "
        "no publication_hold.toml, so the divergence is an accident rather "
        "than a decision")
    assert "held = true" in held.read_text().replace('"', ""), (
        f"the site serves {served} and the bundle holds {local} with the hold "
        "released, so a deploy is overdue rather than withheld")


def test_the_documents_describe_the_site_and_not_the_build():
    """README and PROGRESS both make a claim about what the site serves.

    Pinned to the campaign the site actually names, so if a deploy changes
    it, this fails and the documents get updated with it rather than drifting.
    """
    state = _live("/api/state")
    if state is None:
        pytest.skip("the site could not be reached")
    served = str(state.get("campaign_id") or "")
    readme = (ROOT / "README.md").read_text()
    progress = (ROOT / "PROGRESS.md").read_text()
    if served.startswith("benchmark_"):
        assert "benchmark bundle" in readme, (
            "the site serves the benchmark panel and the README no longer "
            "says so")
        assert "benchmark bundle" in progress, (
            "the site serves the benchmark panel and PROGRESS no longer "
            "says so")
    else:
        # Deliberately unreached while the hold stands, and
        # tools/vacuous_tests.py reports it as such: the site serves the
        # benchmark bundle, so this branch is the one that fires the first
        # time a deploy changes that and the documents have not kept up.
        # Said here because an untaken branch nobody has accounted for is
        # the thing that report exists to surface.
        assert "benchmark bundle" not in readme.split(
            "## 📉 The main campaign")[-1], (
            f"the site now serves {served} and the README still says it "
            "serves the benchmark bundle")


def test_the_site_reports_its_own_pair_count():
    """Seven pairs, not 158, and the difference is the whole point."""
    pairs = _live("/api/pairs")
    if pairs is None:
        pytest.skip("the site could not be reached")
    rows = pairs if isinstance(pairs, list) else (
        (pairs or {}).get("pairs") or (pairs or {}).get("rows") or [])
    state = _live("/api/state")
    if state is None:
        pytest.skip("the site could not be reached")
    assert len(rows) == state.get("pairs_total"), (
        f"the site serves {len(rows)} pair(s) and reports "
        f"{state.get('pairs_total')}")
