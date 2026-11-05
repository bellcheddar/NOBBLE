"""The crystal route serves from the bundle, not from the science stack (F196).

`/crystal/<pdb_id>.cif` imported `nobble.curate.structures`, which imports
gemmi at module level, and the droplet's virtualenv holds flask and gunicorn
and nothing else. So the route returned 500 in production for every
benchmark pair, and `pose.html` loads it into the viewer to superpose a
prediction on its deposited structure: the crystal overlay was dead on the
live site.

Measured rather than inferred: `curl https://nobble.mdeller.com/crystal/
6H0F.cif` returned 500 while `/structure/<job>.cif` returned 200 and 84,837
bytes.

The project had already learned this twice. Four sibling routes import the
same stack only as a fallback behind `if not precomputed`, and the comments
on two of them say so: "Importing nobble.curate here is what made this route
500 on the droplet while passing every local check", and "Two routes have
already returned 500 in production by importing that stack unconditionally".
`crystal()` was the one that kept the unconditional import.

It escaped the deploy's own check because that verifies nine fixed routes and
nothing parameterised, so a crystal URL was never fetched.

The assemblies are published into the bundle, which is what the crystal
*mapping* already does, and served as the stored gzip when the client accepts
it: 965 KB over the wire for 6H0F rather than the 4,127,262 bytes it expands
to. Nothing restricted travels with them, checked rather than assumed: an
assembly carries coordinates and no SMILES, InChI or chem_comp descriptor,
and spec 2.1's restrictions name PROTAC-DB, UbiBrowser and BioLiP2 rather
than the PDB.
"""
from __future__ import annotations

import ast
import gzip
import re
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ATLAS = ROOT / "deploy" / "atlas"
ROUTES = ROOT / "nobble" / "app" / "routes.py"


def crystal_source() -> str:
    """The crystal route's code, with its comments and docstring removed.

    The route's comment explains why it no longer imports
    `nobble.curate.structures`, and so names it. Without stripping, the
    import check matched that explanation and reported the fixed route as
    broken: the fifth time in one session a check has matched prose rather
    than code, and the second in a test written knowing about the trap.
    Stripping is now the default assumption for any check on source text.
    """
    source = ROUTES.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "crystal":
            body = ast.get_source_segment(source, node) or ""
            body = re.sub(r'"""2*.*?"""', "", body, flags=re.S)
            lines = [line for line in body.splitlines()
                     if not line.strip().startswith("#")]
            stripped = "\n".join(lines)
            assert "#" not in stripped or "pdbx" in stripped, (
                "comments survived the strip"
            )
            return stripped
    raise AssertionError("routes.py no longer defines a crystal route")


def referenced_ids() -> set[str]:
    document = ATLAS / "benchmark.json"
    if not document.exists():
        return set()
    mapping = json.loads(document.read_text()).get("crystal_by_pair") or {}
    return {str(value) for value in mapping.values() if value}


def test_the_route_imports_nothing_from_the_science_stack():
    """The property that was broken, stated directly."""
    body = crystal_source()
    for heavy in ("nobble.curate", "nobble.score", "nobble.validate",
                  "nobble.design", "gemmi", "duckdb"):
        assert heavy not in body, (
            f"the crystal route imports {heavy}, which is not installed on "
            "the droplet: the route will return 500 there and the pose page's "
            "crystal overlay will not load"
        )


def test_the_bundle_carries_every_assembly_the_atlas_references():
    ids = referenced_ids()
    if not ids:
        pytest.skip("no published atlas with a crystal mapping")
    missing = sorted(i for i in ids
                     if not (ATLAS / "crystals" / f"{i}.cif.gz").exists())
    assert not missing, (
        f"the atlas names crystals {missing} and does not publish them, so "
        "the route can only 404 for those pairs"
    )


def test_the_published_assemblies_are_readable_gzip():
    ids = sorted(referenced_ids())
    if not ids:
        pytest.skip("no published atlas with a crystal mapping")
    path = ATLAS / "crystals" / f"{ids[0]}.cif.gz"
    with gzip.open(path, "rt", errors="replace") as handle:
        head = handle.read(200)
    assert head.startswith("data_"), (
        f"{path.name} does not begin like an mmCIF document: {head[:40]!r}"
    )


def test_no_published_assembly_carries_restricted_chemistry():
    """Spec 2.1 names PROTAC-DB, UbiBrowser and BioLiP2; the PDB is not one.

    The skip is the point. Written without it, this looped over the glob of
    a directory that did not exist yet and passed on nothing: an assertion
    inside an empty loop, which is exactly what `tools/vacuous_tests.py`
    reports and which it would have named on the next sweep. Found by
    running that sweep twenty minutes after writing this file.
    """
    published = sorted((ATLAS / "crystals").glob("*.cif.gz"))
    if not published:
        pytest.skip("no crystals published yet")
    for path in published:
        with gzip.open(path, "rt", errors="replace") as handle:
            text = handle.read()
        for probe in ("SMILES", "InChI"):
            assert probe not in text, (
                f"{path.name} carries {probe}, which the licensing check "
                "scans for and which an assembly should not contain"
            )


def test_the_route_honours_accept_encoding():
    """Serving gzip unconditionally breaks a client that did not ask.

    Plain curl sends no Accept-Encoding, which is how the 500 was found in
    the first place, so this is not a hypothetical client.
    """
    body = crystal_source()
    assert "accept_encodings" in body, (
        "the route does not consult Accept-Encoding, so it either always "
        "sends gzip to clients that cannot read it or always expands 4 MB"
    )


def test_the_deploy_fetches_a_crystal_url():
    """The gap that hid this: nine fixed routes and nothing parameterised."""
    script = (ROOT / "deploy" / "deploy.sh").read_text()
    assert "/crystal/" in script, (
        "the deploy still verifies no crystal URL, so a 500 there would pass "
        "the same way it did before"
    )


def test_the_deploy_checks_every_parameterised_route():
    """The category, not the one that was broken (F196).

    `/crystal/<id>.cif` returned 500 while nine fixed paths answered 200,
    because none of them is parameterised. Adding only a crystal URL would
    leave the other three routes in exactly the position this one was in.

    Asked of production at the time: the crystal route was the only one of
    the four that was broken. `/structure/<job>.cif` served 84,837 bytes,
    `/api/pair/<id>` 21,177 and `/api/pair/<id>/structures` 3,578. That is
    the reason for checking all four rather than evidence that checking one
    would have been enough.
    """
    routes = ROUTES.read_text()
    parameterised = set(re.findall(r'@bp\.route\("(/[^"]*<[^"]*)"', routes))
    assert parameterised, "routes.py has no parameterised routes to check"

    script = (ROOT / "deploy" / "deploy.sh").read_text()
    missing = []
    for route in sorted(parameterised):
        # `/api/pair/<pair_id>` -> `/api/pair/`, which is what the deploy
        # builds a URL under.
        prefix = route.split("<")[0]
        if prefix not in script:
            missing.append(route)
    assert not missing, (
        f"the deploy verifies no URL for {missing}, so a 500 there would "
        "pass the same way /crystal/ did"
    )
