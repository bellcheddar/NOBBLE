"""The app must serve without the curation stack importable.

This exists because of a real deployment failure. /benchmark and /about
imported nobble.curate at request time, which pulls in gemmi, pandas and
BINMAN's store. All of that exists on the build machine and none of it exists
on the droplet, so both routes passed every local check and returned 500 in
production. Spec Phase 4 says the droplet serves a precomputed atlas with no
compute at request time; this test is that sentence made executable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ATLAS = ROOT / "deploy" / "atlas"
BLOCKED = ("gemmi", "pandas", "freesasa", "rdkit", "sklearn", "transformers", "torch")
PAGES = ("/", "/campaign", "/pose", "/interactions", "/delta", "/benchmark",
         "/about", "/healthz", "/api/state", "/api/pairs")


class _Blocker:
    """Make the heavy scientific stack unimportable, as it is on the droplet."""

    def find_module(self, name, path=None):
        return self if name.split(".")[0] in BLOCKED else None

    def load_module(self, name):
        raise ImportError(f"No module named {name!r} (blocked by the deployment test)")


@pytest.fixture
def droplet_like(monkeypatch):
    for name in list(sys.modules):
        if name.split(".")[0] in BLOCKED or name.startswith("nobble"):
            monkeypatch.delitem(sys.modules, name, raising=False)
    blocker = _Blocker()
    sys.meta_path.insert(0, blocker)
    monkeypatch.setenv("NOBBLE_CAMPAIGN", str(ATLAS))
    yield
    sys.meta_path.remove(blocker)


@pytest.mark.skipif(not ATLAS.exists(),
                    reason="no published atlas: run deploy/build_atlas.py")
def test_every_page_serves_without_the_curation_stack(droplet_like):
    from nobble.app import create_app

    app = create_app()
    with app.test_client() as client:
        for path in PAGES:
            response = client.get(path)
            assert response.status_code == 200, f"{path} returned {response.status_code}"


@pytest.mark.skipif(not ATLAS.exists(), reason="no published atlas")
def test_structures_serve_from_the_atlas(droplet_like):
    from nobble.app import create_app

    app = create_app()
    with app.test_client() as client:
        listing = client.get("/api/pair/bench01_GSPT1_CRBN/structures").get_json()
        assert listing["structures"], "no structures published for the first pair"
        response = client.get(listing["structures"][0]["url"])
        assert response.status_code == 200
        assert len(response.data) > 1000


@pytest.mark.skipif(not ATLAS.exists(), reason="no published atlas")
def test_published_atlas_withholds_protacdb_chemistry():
    """Publishing to a public site is redistribution, exactly as a repo is."""
    marker = "CC1=C(C)C2=C(S1)"          # the dBET57 SMILES from PROTAC-DB
    for path in ATLAS.rglob("*"):
        if path.is_file() and path.suffix in (".json", ".jsonl"):
            assert marker not in path.read_text(errors="replace"), path
