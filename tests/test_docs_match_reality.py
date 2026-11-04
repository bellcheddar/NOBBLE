"""The written record must match what the code and data actually say.

Documentation drift has been a recurring defect in this build rather than
a hypothetical one. PROGRESS has at various points claimed six tabs when
there were seven, an open Gate G3 that had been satisfied hours earlier,
and a running benchmark queue that had finished. Each was true when
written and quietly stopped being true.

These pin the claims that are mechanically checkable. A number in a
document that nothing verifies is a number that will drift.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROGRESS = (ROOT / "PROGRESS.md").read_text()
README = (ROOT / "README.md").read_text()


def _latest(prefix: str) -> Path | None:
    hits = sorted(ROOT.glob(f"campaigns/{prefix}_*"))
    return hits[-1] if hits else None


def test_the_main_campaign_size_is_what_progress_claims():
    campaign = _latest("campaign")
    if campaign is None or not (campaign / "queue.jsonl").exists():
        pytest.skip("no assembled main campaign")

    jobs = [json.loads(l) for l in (campaign / "queue.jsonl").read_text().splitlines() if l.strip()]
    pairs = len({j["pair_id"] for j in jobs})

    assert f"{len(jobs):,} jobs" in PROGRESS, f"PROGRESS does not mention {len(jobs):,} jobs"
    assert f"{pairs} pairs" in PROGRESS, f"PROGRESS does not mention {pairs} pairs"


def test_the_tab_count_in_progress_matches_the_app():
    from nobble.app import create_app

    app = create_app()
    with app.app_context():
        pass
    # The tab list lives in the app's context processor.
    import nobble.app as app_pkg
    source = Path(app_pkg.__file__).read_text()
    tabs = re.findall(r'\("([a-z]+)", "[A-Z]', source)
    assert tabs, "no tabs found in the app"

    words = {7: "Seven", 6: "Six", 8: "Eight"}
    expected = words.get(len(tabs))
    assert expected, f"unexpected tab count {len(tabs)}"
    assert f"{expected} tabs" in PROGRESS or f"{len(tabs)} tabs" in PROGRESS, (
        f"the app has {len(tabs)} tabs and PROGRESS says otherwise"
    )


def test_the_bridge_reference_count_is_consistent():
    """285,996 observed bridges is quoted in PROGRESS, the README and the
    app. It comes from BINMAN, so if the store changes the documents must
    not keep the old figure."""
    from nobble.curate import binman_store

    try:
        actual = binman_store.bridge_reference_count()
    except Exception:  # noqa: BLE001
        pytest.skip("BINMAN store not readable here")

    assert f"{actual:,}" in PROGRESS, f"PROGRESS quotes a different bridge count than {actual:,}"


def test_the_design_scan_cost_in_the_readme_matches_the_generator():
    """The README quotes 15 variants and 225 jobs for an alanine scan of a
    15-mer, and 285 variants and 4,275 jobs for saturation. Both follow
    from the generator and jobs_per_pair, so neither should be hand-kept."""
    from nobble.curate.manifest import jobs_per_pair
    from nobble.design import variants

    per_pair = jobs_per_pair()
    scan = variants.generate("p", "A" * 15)["count"]
    assert scan == 15
    assert f"{scan} variants, {scan * per_pair} jobs" in README or \
           f"{scan} variants and {scan * per_pair} jobs" in README, \
           f"README does not state {scan} variants and {scan * per_pair} jobs"

    saturation = 15 * 19
    assert f"{saturation} variants and {saturation * per_pair:,} jobs" in README, \
        f"README does not state {saturation} variants and {saturation * per_pair:,} jobs"
