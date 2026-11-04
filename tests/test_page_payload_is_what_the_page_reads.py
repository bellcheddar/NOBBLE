"""The page payload carries what the page reads, and not the rest (F174).

The campaign and Delta pages serialise every scored pair into the document
with `{{ pairs | tojson }}`. That is the right shape for a read-only atlas,
with no fetch to wait on and no spinner, but it means the document grows
with the campaign. Measured on a 158-pair atlas, the shape the running
campaign will produce, the landing page was 3.37 MB of HTML and 99 per cent
of those bytes sat in five keys neither page accesses.

`data.PAGE_PAYLOAD_OMITS` leaves four of them out. These tests keep that
tuple honest in both directions, which is the point: the dangerous mistake
is not leaving a heavy key in, it is dropping one a page reads, because that
shows up as a blank cell rather than as an error.

So: nothing omitted may be accessed by either page, every key either page
does access must survive the projection, and the omitted detail must still
be reachable per pair, since dropping it from the page is a transport
decision and not a decision to stop publishing it.
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

TEMPLATES = ROOT / "nobble" / "app" / "templates"
JS = ROOT / "nobble" / "app" / "static" / "js"

# The two pages that embed the whole pair list.
PAGES = ("campaign.html", "delta.html")

# A property access on a pair object: `.key`, `['key']`, or a `data-sort`
# style attribute naming a field. Deliberately generous, because a false
# positive keeps a key and a false negative drops one.
ACCESS = re.compile(
    r"""\.([A-Za-z_][A-Za-z0-9_]*)"""
    r"""|\[\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]\s*\]"""
    r"""|data-[a-z-]+="([A-Za-z_][A-Za-z0-9_]*)\""""
)


# `url_for('static', filename='js/nobble.js')`, either quote style. The
# single-quoted form is what the templates use today, and matching only that
# is how this test would quietly stop covering the client script: a template
# reformatted to double quotes would find no scripts, read no JS, and pass
# because it was looking at nothing. `_scripts` asserts it found some.
SCRIPT = re.compile(r"""filename=['"]js/([A-Za-z0-9_.-]+)['"]""")


def _scripts(text: str) -> list[Path]:
    found = [JS / name for name in SCRIPT.findall(text)]
    present = [path for path in found if path.exists()]
    assert present, (
        "no client scripts were found in the template, so the key-access "
        "checks below would be reading the template alone. Either the pages "
        "stopped loading JavaScript or SCRIPT no longer matches how they do."
    )
    return present


def _page_text(name: str) -> str:
    """The template, the base it extends, and every script either loads."""
    parts = [(TEMPLATES / name).read_text(), (TEMPLATES / "base.html").read_text()]
    for script in _scripts("".join(parts)):
        parts.append(script.read_text())
    return "\n".join(parts)


def _accessed(name: str) -> set[str]:
    return {group for match in ACCESS.findall(_page_text(name)) for group in match if group}


@pytest.fixture(scope="module")
def atlas_path() -> Path | None:
    """The published bundle, which is the only atlas a test may assume."""
    bundle = ROOT / "deploy" / "atlas"
    return bundle if (bundle / "scores.jsonl").exists() else None


@pytest.fixture(scope="module")
def atlas_scores(atlas_path) -> list[dict]:
    if atlas_path is None:
        return []
    text = (atlas_path / "scores.jsonl").read_text()
    return [json.loads(line) for line in text.splitlines() if line.strip()]


@pytest.mark.parametrize("page", PAGES)
def test_nothing_the_page_reads_is_omitted_from_its_payload(page, atlas_scores):
    """The direction that matters: over-trimming blanks a cell silently."""
    if not atlas_scores:
        pytest.skip("no published atlas to read keys from")
    keys = set()
    for row in atlas_scores:
        keys |= set(row.keys())
    read = _accessed(page) & keys
    dropped = sorted(read & set(data.PAGE_PAYLOAD_OMITS))
    assert dropped == [], (
        f"{page} accesses {dropped}, which PAGE_PAYLOAD_OMITS leaves out of "
        "the payload it is handed. The cells would render empty."
    )


def test_every_omitted_key_is_dead_weight_on_both_pages(atlas_scores):
    """And the other direction: an entry that is actually used is a bug."""
    if not atlas_scores:
        pytest.skip("no published atlas to read keys from")
    touched = set()
    for page in PAGES:
        touched |= _accessed(page)
    alive = sorted(set(data.PAGE_PAYLOAD_OMITS) & touched)
    assert alive == [], (
        f"PAGE_PAYLOAD_OMITS names {alive}, which a page does access. Either "
        "the page changed or the entry was never dead."
    )


def test_the_projection_drops_exactly_the_named_keys(atlas_path):
    if atlas_path is None:
        pytest.skip("no published atlas")
    data.configure(atlas_path)
    try:
        full = data.scores()
        trimmed = data.scores_for_pages()
        assert len(full) == len(trimmed)
        for before, after in zip(full, trimmed):
            assert set(before) - set(after) <= set(data.PAGE_PAYLOAD_OMITS)
            assert set(after) == set(before) - set(data.PAGE_PAYLOAD_OMITS)
            for key, value in after.items():
                assert value == before[key], key
    finally:
        data.configure(atlas_path)


def test_the_omitted_detail_is_still_reachable_per_pair(atlas_path):
    """Trimming the page is a transport decision, not an unpublishing."""
    if atlas_path is None:
        pytest.skip("no published atlas")
    app = create_app()
    data.configure(atlas_path)
    rows = data.scores()
    if not rows:
        pytest.skip("no scored pairs")
    present = [key for key in data.PAGE_PAYLOAD_OMITS if key in rows[0]]
    if not present:
        pytest.skip("this atlas carries none of the omitted keys")
    client = app.test_client()
    response = client.get(f"/api/pair/{rows[0]['pair_id']}")
    assert response.status_code == 200
    served = json.loads(response.data)
    missing = [key for key in present if key not in served]
    assert missing == [], (
        f"/api/pair stopped serving {missing}, so the detail the page no "
        "longer embeds is now unreachable."
    )


def test_the_page_payload_stays_within_its_budget_per_pair(atlas_path):
    """The direction the two tests above cannot see.

    Those hold `PAGE_PAYLOAD_OMITS` against what the pages access, which
    only ever covers keys someone has already thought about. The way this
    page grew to 3.3 MB was a field being added to a score row and nobody
    asking whether the page reads it, and no list of names catches that.
    A budget does, because the payload is paid for once per pair.

    What it catches, measured rather than asserted: against the 3,125 bytes
    per pair the trimmed page carries and a 6,000 budget, putting
    `seed_records` back adds 11,069 and `plip` 3,869, both of which breach
    it; `contact_map` adds 2,048 and `convergence` 917, neither of which
    does on its own. So this is not a replacement for the named list, it is
    the half of the problem a list of names cannot reach. The two tests
    above cover keys someone has thought about, and this covers the weight
    of keys nobody has.
    """
    if atlas_path is None:
        pytest.skip("no published atlas")
    from nobble import paths
    budget = int(paths.thresholds()["app"]["page_payload_bytes_per_pair_max"])

    app = create_app()
    data.configure(atlas_path)
    client = app.test_client()
    for route in ("/", "/delta"):
        html = client.get(route).get_data(as_text=True)
        found = re.search(r"const PAIRS = (\[.*?\]);\n", html, re.S)
        assert found, f"{route} no longer embeds a PAIRS payload"
        payload = found.group(1)
        pairs = json.loads(payload)
        if not pairs:
            continue
        per_pair = len(payload) / len(pairs)
        assert per_pair <= budget, (
            f"{route} carries {per_pair:.0f} bytes of payload per pair against "
            f"a budget of {budget}. At campaign scale that is "
            f"{per_pair * 158 / 1024 / 1024:.1f} MB of document. Either the "
            "page reads the new field, in which case raise the budget and say "
            "why, or it does not, in which case add it to PAGE_PAYLOAD_OMITS."
        )
