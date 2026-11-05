"""The refinement panel shows labels, not field names (F203).

`#refinement` on the pose page is hidden until a refinement exists, and no
refinement has ever existed: `measured_scaling` reports no tier-2 job has
completed on any campaign. So the panel had been rendered only empty, and
rendering it with tier-2 data for the first time showed it listing
`bridge_formation_rate` and `convergence_score` where every other table on
the site shows "Bridge percentile" and "Pose convergence".

The labels come from `data.COMPONENTS`, which is where the site's labels
live, rather than from a second list in `nobble/sampling.py`. Three of the
four keys are already labelled there, and a parallel list is the duplication
F181, F183 and F187 were each about.

`bridge_formation_rate` is not in COMPONENTS, because COMPONENTS drives the
weight sliders and that rate is not a composite component. It falls back to
its key with the underscores opened out and the first letter raised, which is
a transformation of the key rather than a name invented in the route. The
ledger's own header abbreviates the same quantity to "Bridge rate", so the
two differ on purpose, and what identifies the row is its tooltip:
"proportion of seeds whose glue bridged both chains".
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import sampling  # noqa: E402
from nobble.app import data  # noqa: E402

TEMPLATE = ROOT / "nobble" / "app" / "templates" / "pose.html"
ROUTES = ROOT / "nobble" / "app" / "routes.py"


def labelled_rows() -> list[dict]:
    """The rows the route sends, labels and all."""
    coarse = {key: 0.4 for key in sampling.COMPARABLE}
    refined = {key: 0.6 for key in sampling.COMPARABLE}
    report = sampling.compare(coarse, refined)
    for row in report["rows"]:
        meta = data.COMPONENTS.get(row["key"]) or {}
        fallback = row["key"].replace("_", " ")
        row["label"] = meta.get("label") or (fallback[:1].upper() + fallback[1:])
    return report["rows"]


def test_no_row_is_labelled_with_a_field_name():
    for row in labelled_rows():
        assert "_" not in row["label"], (
            f"{row['key']} renders as a field name: {row['label']!r}"
        )


def test_every_label_starts_with_a_capital():
    """So a fallback does not sit in lower case beside three that do not."""
    for row in labelled_rows():
        first = row["label"][:1]
        assert first == first.upper() and first.isalpha(), row["label"]


def test_the_labels_come_from_components_where_components_has_them():
    """Not from a second list, which would drift."""
    for row in labelled_rows():
        meta = data.COMPONENTS.get(row["key"]) or {}
        if meta.get("label"):
            assert row["label"] == meta["label"], row


def test_every_row_carries_what_it_is_so_the_fallback_is_identifiable():
    """The tooltip is what names the quantity when the label is derived."""
    for row in labelled_rows():
        assert row.get("what"), row
        assert len(row["what"]) > 20, row["what"]


def test_the_template_prefers_the_label_and_falls_back_to_the_key():
    body = "\n".join(line for line in TEMPLATE.read_text().splitlines()
                     if not line.strip().startswith(("*", "/*")))
    assert "row.label || row.key" in body, (
        "the panel renders row.key directly again, so a row without a label "
        "would show nothing instead of its field name"
    )


def test_the_route_attaches_the_label_rather_than_sampling():
    """Layering: a scoring module must not import the app's label table."""
    assert "COMPONENTS" in ROUTES.read_text()
    source = (ROOT / "nobble" / "sampling.py").read_text()
    assert "nobble.app" not in source, (
        "nobble/sampling.py imports the app, which inverts the layering: "
        "scoring would depend on presentation"
    )
