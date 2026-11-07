"""Measured accessibility basics, which nothing covered.

`tests/test_app_chrome.py` is about theme colours and the manifest. Nothing
asserted anything about how the pages read to someone navigating by headings
or hearing a chart announced, so the gaps were measurable and unmeasured
(F294):

* every page began at `h2`, so the document had no top-level heading and a
  reader navigating by headings started a level down with nothing naming the
  page;
* four chart containers had no accessible name, so each announced as an empty
  group;
* `scope` appeared on 4 of about 75 `th` elements.

`lang` and the skip link were already right on all eight pages, which is why
this asserts them too: a check that only covers what was broken stops being a
check the moment something else breaks.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PAGES = ["/", "/about", "/benchmark", "/campaign", "/delta", "/design",
         "/interactions", "/pose"]


def _client():
    from nobble.app import create_app
    from nobble.execute.campaign import latest

    campaign = latest("campaign") or str(ROOT / "deploy" / "atlas")
    app = create_app(str(campaign))
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture(scope="module")
def pages():
    client = _client()
    return {path: client.get(path).get_data(as_text=True) for path in PAGES}


@pytest.mark.parametrize("path", PAGES)
def test_the_page_has_exactly_one_top_level_heading(path, pages):
    """One, because none is unnavigable and several is ambiguous."""
    found = re.findall(r"<h1[^>]*>(.*?)</h1>", pages[path], re.S)
    assert len(found) == 1, f"{path} has {len(found)} h1 element(s)"
    assert found[0].strip(), f"{path}'s h1 is empty"


@pytest.mark.parametrize("path", PAGES)
def test_the_page_declares_a_language(path, pages):
    assert re.search(r"<html[^>]*\blang=", pages[path]), path


@pytest.mark.parametrize("path", PAGES)
def test_the_page_offers_a_skip_link(path, pages):
    assert "#main" in pages[path], path
    assert 'id="main"' in pages[path], path


def test_every_chart_says_what_it_plots(pages):
    """A chart container with no name announces as an empty group.

    Named for the quantity rather than the word "chart", and the ROC's label
    points at the line above it, where the AUC and interval are text.
    """
    unnamed = []
    for path, text in pages.items():
        for container in re.findall(r'<div class="chart[^"]*"[^>]*>', text):
            if "aria-label" not in container:
                unnamed.append((path, container[:70]))
    assert not unnamed, f"chart container(s) with no accessible name: {unnamed}"


def test_the_headings_do_not_skip_a_level(pages):
    """h1 then h2 then h3, with no jump.

    A visually hidden h1 is only useful if the h2s under it are the panels,
    which is how Depot lays the pages out.
    """
    for path, text in pages.items():
        levels = [int(m) for m in re.findall(r"<h([1-6])\b", text)]
        for before, after in zip(levels, levels[1:]):
            assert after <= before + 1, (
                f"{path} jumps from h{before} to h{after}")
