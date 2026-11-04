"""One filename, built in three places (F148).

A predicted structure reaches the browser through three independent
constructions of its name:

- `deploy/build_atlas.py` copies the file to `f"{row['job_id']}.cif"` under
  `structures/` and rewrites the row's `structure` field to that path;
- `nobble/app/routes.py` offers it as `f"/structure/{row['job_id']}.cif"`;
- the same module serves `/structure/<path:job_id>.cif` by looking the job
  up in the campaign's records.

Nothing tied the three together. They agree today, and if the published name
ever gained a prefix, a tier suffix or a different extension on one side
only, every pose URL would 404 while the atlas, the API and the page all
looked correct in isolation: the catalogue would list structures and the
viewer would show the empty state.

Verified end to end once, against an atlas built from a campaign carrying
tier-2 results: 25 structures offered, 10 of them refined, all 10 URLs
serving 200 from the published bundle. These are the checks that keep the
three spellings in step without rebuilding an atlas.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = (ROOT / "deploy" / "build_atlas.py").read_text()
ROUTES = (ROOT / "nobble" / "app" / "routes.py").read_text()


def test_the_builder_publishes_under_the_job_id():
    assert 'f"{row[\'job_id\']}.cif"' in BUILDER, (
        "the atlas no longer names a published structure after its job id"
    )


def test_the_api_offers_the_same_name():
    assert "f\"/structure/{row['job_id']}.cif\"" in ROUTES, (
        "the API builds the pose URL from something other than the job id, "
        "so it will not match what the atlas published"
    )


def test_the_route_accepts_a_job_id_containing_slashes_or_dots():
    """`<path:job_id>` rather than `<job_id>`.

    A job id is tier, gene, E3, arm, conditioning and seed joined by double
    underscores, and the tier-2 ones carry a further suffix. A plain string
    converter stops at the first slash, which none currently contain, and
    the `path` converter is what makes that a non-question.
    """
    assert "/structure/<path:job_id>.cif" in ROUTES


def test_the_structures_directory_is_the_one_the_builder_writes():
    """The route resolves `structure` against the campaign, and the atlas
    writes `structures/<name>`, so the two have to agree on the folder."""
    assert '(OUT / "structures")' in BUILDER
    assert 'f"structures/{published}"' in BUILDER or \
           '"structures/" + published' in BUILDER, (
        "the builder copies into structures/ and records a different path, "
        "so the route will resolve to a file that is not there"
    )


def test_every_published_structure_has_a_row_that_names_it():
    """The published bundle, checked as it stands.

    A file in `structures/` that no row points at is dead weight on the
    droplet; a row pointing at a file that is not there is a 404 in the
    viewer. Both directions, over whatever the current atlas holds.
    """
    import json

    atlas = ROOT / "deploy" / "atlas"
    if not (atlas / "structures").exists():
        return
    on_disk = {path.name for path in (atlas / "structures").glob("*.cif")}
    named = set()
    for results in sorted(atlas.glob("results*.jsonl")):
        for line in results.read_text().splitlines():
            if not line.strip():
                continue
            structure = json.loads(line).get("structure")
            if structure:
                named.add(Path(structure).name)
    assert named, "no published row names a structure"
    assert not (named - on_disk), (
        f"{sorted(named - on_disk)[:3]} are named by a row and absent from "
        "structures/, so the viewer would 404 on them"
    )
    assert not (on_disk - named), (
        f"{sorted(on_disk - named)[:3]} are published and named by no row"
    )
