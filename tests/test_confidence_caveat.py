"""Spec 4.5's calibration caveat, with the number rather than an adjective.

    Calibration note for the UI copy and the About page: the Thera-SAbDab
    benchmark of Boltz-2 across 519 therapeutic antibodies paired with
    cognate and non-cognate antigens found confidence metrics gave only
    weak though above-chance discrimination (ROC-AUC between 0.5 and 0.60),
    with ipTM-min carrying the strongest signal ... the app must not
    present ipTM as a verdict.

The caveat was already on the page and said "separates cognate from
non-cognate antigens poorly", which is the conclusion without its basis. A
reader asking how weak got an adjective. The range costs five words.

Recorded here because I first grepped for "Thera-SAbDab" and "0.60", found
neither, and concluded the caveat was missing altogether: differently
worded presence read as absence, which is F20's mistake in a smaller
place (F49).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ATLAS = ROOT / "deploy" / "atlas"


def _about() -> str:
    from nobble.app import create_app

    app = create_app(str(ATLAS))
    with app.test_client() as client:
        response = client.get("/about")
        assert response.status_code == 200
        return response.get_data(as_text=True)


@pytest.mark.skipif(not ATLAS.exists(), reason="no published atlas")
def test_the_about_page_carries_the_calibration_range():
    body = _about()
    assert "519 therapeutic antibodies" in body, "the benchmark's size is gone"
    assert re.search(r"0\.5 to 0\.60|0\.5-0\.60", body), (
        "the caveat no longer gives the ROC-AUC range, so 'weak' is an "
        "adjective with nothing behind it"
    )
    assert "ipTM-min" in body, "the metric that carried the signal is unnamed"


@pytest.mark.skipif(not ATLAS.exists(), reason="no published atlas")
def test_the_app_does_not_present_iptm_as_a_verdict():
    """Spec 4.5's instruction, and the sentence that keeps it."""
    assert "enrichment, not a verdict" in _about()


@pytest.mark.skipif(not ATLAS.exists(), reason="no published atlas")
def test_the_caveat_stays_two_short_sentences():
    """CLAUDE.md allows a disclaimer where a figure would be actively
    misread, and then one sentence. This is two short ones: the measurement
    and what follows from it. Pinned so it cannot grow into a paragraph."""
    body = _about()
    paragraph = next(
        (re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", block)).strip()
         for block in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)
         if "519 therapeutic" in block),
        None,
    )
    assert paragraph, "the caveat paragraph is gone"
    assert len(paragraph.split()) <= 40, f"{len(paragraph.split())} words"
    # A full stop followed by whitespace or the end, so the dots inside
    # "0.5" and "0.60" are not counted. Counting bare dots gave four and is
    # the third naive string check of mine to be wrong today.
    sentences = re.findall(r"\.(?:\s|$)", paragraph)
    assert len(sentences) == 2, f"{len(sentences)} sentences: {paragraph}"
