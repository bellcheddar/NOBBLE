"""Everything the atlas publishes has a reader in the app (F137).

Tier 2 wrote `scores_tier2.jsonl`, the atlas builder published it, and
nothing read it. The refinement's coordinates were openable and its
measurements were not, so there was no way to tell whether refinement had
improved anything. The file was referenced in two places, by the builder that
published it and by a comment, so looking for an unreferenced file would not
have found it.

The invariant that was actually broken is narrower: a file goes into the
published atlas so that the app can serve it, and one with no reader in the
app is compute whose only product is a file on a droplet.

Derived from the builder rather than from `deploy/atlas/`, because what is
on disk depends on which stages have run and the builder is the statement of
intent.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "deploy" / "build_atlas.py"
APP = ROOT / "nobble" / "app"

# Written for the app to serve, but read by name in the atlas's own tooling
# rather than by the app: the queue and the state file drive the campaign
# ledger's progress figures through `campaign_state`, which reads them via
# `queue()` and the state helper rather than by these literals.
NOT_SERVED_BY_NAME = {"state.jsonl"}


def _published_names() -> set[str]:
    source = BUILDER.read_text()
    found = set(re.findall(r'"([A-Za-z_][A-Za-z0-9_]*\.jsonl?)"', source))
    # The builder also composes names from a tier suffix. Those are the
    # tier-2 siblings and they are published the same way.
    found |= {"scores_tier2.jsonl", "results_tier2.jsonl"}
    assert len(found) >= 10, f"only found {found}: the regex has stopped matching"
    return found


def _app_text() -> str:
    parts = [path.read_text() for path in sorted(APP.glob("*.py"))]
    parts += [path.read_text() for path in sorted((APP / "templates").glob("*.html"))]
    return "\n".join(parts)


def test_every_published_file_has_a_reader_in_the_app():
    text = _app_text()
    orphans = []
    for name in sorted(_published_names()):
        if name in NOT_SERVED_BY_NAME:
            continue
        stem = name.rsplit(".", 1)[0]
        if name in text:
            continue
        if re.search(r"[\"']" + re.escape(stem) + r"[\"']", text):
            continue
        orphans.append(name)
    assert not orphans, (
        f"{orphans} are published into the atlas and read by nothing in the "
        "app, so the compute that produced them has no reader"
    )


def test_the_tier_two_siblings_are_among_them():
    """The two the finding was about, named so the check cannot lose them.

    `_published_names` adds them by hand because the builder composes their
    names, so without this a change to that helper could drop them and the
    test above would still pass.
    """
    text = _app_text()
    for name in ("scores_tier2.jsonl", "results_tier2.jsonl"):
        assert name in text, f"nothing in the app reads {name}"


def test_the_builder_publishes_the_tier_two_files():
    """The other half: the app reads them and the atlas has to ship them.

    An app reader for a file the atlas does not publish is the same defect
    pointing the other way, and on the droplet it is the one that shows: the
    page would render empty with no error.
    """
    source = BUILDER.read_text()
    for name in ("scores_tier2.jsonl", "results_tier2.jsonl"):
        assert name in source, f"the atlas does not publish {name}"
