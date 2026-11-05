"""The ledger's facets offer what the field holds (F191).

The pair table's Tier control offered `all / benchmark / A / B` and compared
its value with `p.tier === tier`. The score row's `tier` is the arm a pair
belongs to, `benchmark`, `sievers_zf`, `scramble` or `design`, and the LM
schema says so in as many words: "This is the arm the pair belongs to, not
the Tier A/Tier B curation tier". The control was built against one meaning
of the word and wired to the other.

Measured on the live site before it was fixed, by driving the control rather
than reading the code: `A` returned 0 rows and `B` returned 0 rows while
`benchmark` returned all 7. Two of four options were dead in production. The
same file explains three lines above why `furniture` is deliberately not
offered, "a control that can never match anything is worse than no control",
which is the rule this broke.

At campaign scale it is worse than cosmetic: of the 158 pairs the running
campaign will publish, 120 are `sievers_zf` and the rest `scramble` and
`design`, so 151 of them would have had no option at all.

The options are built from the tiers the payload carries, in Python rather
than in Jinja, because `map(attribute='tier')` yields `Undefined` for an
absent key and `reject('none')` does not filter that. These tests hold both
directions, so neither a dead option nor a missing arm can come back.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.app import create_app, data  # noqa: E402

ATLAS = ROOT / "deploy" / "atlas"


@pytest.fixture(scope="module")
def rendered() -> str:
    if not (ATLAS / "scores.jsonl").exists():
        pytest.skip("no published atlas")
    app = create_app()
    data.configure(ATLAS)
    return app.test_client().get("/").get_data(as_text=True)


@pytest.fixture(scope="module")
def tiers_present() -> set[str]:
    if not (ATLAS / "scores.jsonl").exists():
        return set()
    rows = [json.loads(line) for line
            in (ATLAS / "scores.jsonl").read_text().splitlines() if line.strip()]
    return {row["tier"] for row in rows if row.get("tier")}


def offered(html: str) -> list[str]:
    """The Tier select's option values, in document order."""
    block = re.search(r'<select id="f-tier".*?</select>', html, re.S)
    assert block, "the ledger no longer has a Tier control"
    return re.findall(r'<option value="([^"]*)"', block.group(0))


def test_every_tier_in_the_data_can_be_selected(rendered, tiers_present):
    """The half that matters at campaign scale."""
    missing = sorted(tiers_present - set(offered(rendered)))
    assert not missing, (
        f"{missing} appear in the data and cannot be selected. At campaign "
        "scale that is most of the table."
    )


def test_no_option_matches_nothing(rendered, tiers_present):
    """The half that was live: `A` and `B` returned no rows, ever."""
    dead = [value for value in offered(rendered)
            if value and value not in tiers_present]
    assert not dead, (
        f"option(s) {dead} match no row in the published atlas. The same file "
        "says a control that can never match anything is worse than no "
        "control."
    )


def test_the_all_option_is_still_first_and_empty(rendered):
    values = offered(rendered)
    assert values and values[0] == "", (
        "the unfiltered option is no longer first, so the table opens filtered"
    )


def test_the_options_are_not_written_into_the_template(rendered):
    """Hard-coded arms would drift from the data again.

    This is the thing that actually went wrong: a list of options typed once
    against a different meaning of the field. Retyping it correctly would
    leave the same failure mode in place for the next arm added.
    """
    template = (ROOT / "nobble" / "app" / "templates" / "campaign.html").read_text()
    body = "\n".join(line for line in template.splitlines()
                     if not line.strip().startswith("{#"))
    for arm in ("sievers_zf", "scramble", "design", '"A"', '"B"'):
        assert f'<option value="{arm}"' not in body, (
            f"{arm} is written into the template as a literal option"
        )


def test_the_route_derives_them_rather_than_the_template(rendered):
    routes = (ROOT / "nobble" / "app" / "routes.py").read_text()
    assert "tiers=" in routes, (
        "the route no longer passes the tier list, so the template is "
        "deriving it with Jinja, where a missing key is Undefined rather "
        "than None"
    )
