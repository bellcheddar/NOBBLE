"""The app must serve without the curation stack importable.

This exists because of a real deployment failure. /benchmark and /about
imported nobble.curate at request time, which pulls in gemmi, pandas and
BINMAN's store. All of that exists on the build machine and none of it exists
on the droplet, so both routes passed every local check and returned 500 in
production. Spec Phase 4 says the droplet serves a precomputed atlas with no
compute at request time; this test is that sentence made executable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ATLAS = ROOT / "deploy" / "atlas"
BLOCKED = ("gemmi", "pandas", "freesasa", "rdkit", "sklearn", "transformers", "torch")
# Every argument-free GET route is enumerated from the app itself rather than
# listed here. The list that used to live at this name stopped covering
# /design the day the design arm shipped, and nothing noticed, because a test
# that checks a stale list goes on passing. This one grows with the app.
#
# MUST_INCLUDE is the opposite guard: it fails if a route disappears, which
# enumeration alone cannot catch.
MUST_INCLUDE = ("/", "/campaign", "/pose", "/interactions", "/delta",
                "/benchmark", "/design", "/about", "/healthz",
                "/api/state", "/api/pairs")


def _argument_free_get_routes(app) -> list[str]:
    """Routes a plain GET can reach, so the test needs no fixtures to call them.

    Parameterised routes (/structure/<job_id>.cif and friends) need a real id
    and are covered by test_structures_serve_from_the_atlas instead.
    """
    return sorted({
        str(rule.rule)
        for rule in app.url_map.iter_rules()
        if not rule.arguments
        and rule.endpoint != "static"
        and "GET" in (rule.methods or ())
    })


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
    routes = _argument_free_get_routes(app)

    missing = [path for path in MUST_INCLUDE if path not in routes]
    assert not missing, f"route(s) gone from the app: {missing}"

    with app.test_client() as client:
        for path in routes:
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
    """Publishing to a public site is redistribution, exactly as a repo is.

    The loop used to be the whole test, and every assertion was inside it,
    so an absent or empty atlas passed by examining nothing. The count of
    files actually read is asserted first: a licensing guarantee that holds
    vacuously is not a guarantee (F72).
    """
    marker = "CC1=C(C)C2=C(S1)"          # the dBET57 SMILES from PROTAC-DB
    examined = 0
    for path in ATLAS.rglob("*"):
        if path.is_file() and path.suffix in (".json", ".jsonl"):
            examined += 1
            assert marker not in path.read_text(errors="replace"), path
    assert examined > 0, (
        "no published record was examined, so this test proves nothing about "
        "whether PROTAC-DB chemistry travels"
    )


def test_the_published_atlas_says_what_it_withheld():
    """And the positive half: the record whose chemistry was withheld is
    named, so an atlas that withheld nothing is distinguishable from one
    whose detection stopped firing."""
    import json

    summary = json.loads((ATLAS / "ATLAS.json").read_text())
    assert summary["redactions"] >= 1, (
        "the benchmark panel includes dBET57, whose chemistry is PROTAC-DB's"
    )
    assert "dBET57" in summary.get("redacted_ligands", [])


def test_comparison_refuses_to_conclude_when_the_control_moves(tmp_path, monkeypatch):
    """A comparison whose control moved must not be read as evidence.

    The corrected campaign changes one variable. IKZF1 keeps its 15-mer in both
    and is the check that nothing else did: if its recovery shifts, the other
    differences cannot be attributed to the construct, and the report has to
    say so rather than reporting an improvement.
    """
    from nobble.validate import compare as compare_module

    def fake_recovery(campaign):
        if "corrected" in campaign.name:
            return {
                "corr01_GSPT1_CRBN": {"median_rmsd": 6.0, "poses": 10, "anchor_rmsd": 1.8},
                "corr04_IKZF1_CRBN": {"median_rmsd": 12.0, "poses": 10, "anchor_rmsd": 1.8},
            }
        return {
            "bench01_GSPT1_CRBN": {"median_rmsd": 29.0, "poses": 10, "anchor_rmsd": 1.8},
            "bench04_IKZF1_CRBN": {"median_rmsd": 5.4, "poses": 10, "anchor_rmsd": 1.8},
        }

    monkeypatch.setattr(compare_module, "_recovery_by_pair", fake_recovery)
    baseline = tmp_path / "benchmark_x"
    corrected = tmp_path / "corrected_x"
    baseline.mkdir()
    corrected.mkdir()

    report = compare_module.compare(baseline, corrected)
    # GSPT1 improved by 23 A, which looks like a triumph, and must not be
    # reported as one while the control has moved by 6.6 A.
    assert not report["control_held"]
    assert "NOT TRUSTWORTHY" in report["conclusion"]


def _atlas_string_values():
    """Every string value in the published atlas, with the file it came from."""
    def walk(node, path):
        if isinstance(node, str):
            yield path, node
        elif isinstance(node, dict):
            for key, value in node.items():
                yield from walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                yield from walk(value, f"{path}[{index}]")

    for path in sorted(ATLAS.rglob("*")):
        if not path.is_file() or path.suffix not in (".json", ".jsonl"):
            continue
        text = path.read_text(errors="replace")
        documents = []
        if path.suffix == ".jsonl":
            for line in text.splitlines():
                if line.strip():
                    try:
                        documents.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        else:
            try:
                documents.append(json.loads(text))
            except json.JSONDecodeError:
                continue
        for document in documents:
            yield from walk(document, path.name)


@pytest.mark.skipif(not ATLAS.exists(), reason="no published atlas")
def test_no_protacdb_structure_reaches_the_published_atlas():
    """Derived from the licensed dataset, not from a marker kept by hand.

    The check above looks for one 15-character fragment of one compound,
    written down when that compound was the only PROTAC in the panel. A
    sentinel maintained by hand stops covering what it was meant to cover
    the moment the panel changes, and says nothing when it does (F21).

    This asks the opposite question: does any string the atlas publishes
    appear in PROTAC-DB at all. It covers every one of the 15,502 curated
    structures rather than the one that happened to be noticed, and needs
    no updating when the panel grows.

    Compound *names* are deliberately not covered. dBET57 is published
    literature; what PROTAC-DB licenses is the curated structure.
    """
    from nobble.curate import binman_store as store

    try:
        forbidden = {
            row["smiles"].strip()
            for row in store.dataset("protacdb_protacs")
            if (row.get("smiles") or "").strip()
        }
    except Exception:  # noqa: BLE001
        pytest.skip("BINMAN store not readable here")

    assert len(forbidden) > 1000, "the PROTAC-DB table came back suspiciously small"

    leaked = [
        (where, value[:40])
        for where, value in _atlas_string_values()
        if value.strip() in forbidden
    ]
    assert not leaked, f"PROTAC-DB structures published at: {leaked[:5]}"


@pytest.mark.skipif(not ATLAS.exists(), reason="no published atlas")
def test_every_protacdb_sourced_record_is_redacted_and_says_so():
    """The mechanism's own invariant, not just its outcome.

    dBET57's published `smiles` is null, and it would also be null if the
    field had simply never been populated. Those two are not the same
    protection: one survives the field being filled in, the other does not.
    So this asserts the redaction actually ran, by requiring the note it
    leaves behind, for every record sourced from PROTAC-DB.
    """
    redacted = 0
    for path in sorted(ATLAS.rglob("*")):
        if not path.is_file() or path.suffix not in (".json", ".jsonl"):
            continue
        text = path.read_text(errors="replace")
        documents = []
        if path.suffix == ".jsonl":
            documents = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            documents = [json.loads(text)]

        def check(node, trail):
            nonlocal redacted
            if isinstance(node, dict):
                if str(node.get("source", "")) == "protacdb":
                    assert node.get("smiles") is None, \
                        f"{path.name}{trail} publishes PROTAC-DB chemistry"
                    assert "smiles_withheld" in node, \
                        (f"{path.name}{trail} has no smiles, but the redaction "
                         "never ran: the field was merely absent")
                    redacted += 1
                for key, value in node.items():
                    check(value, f"{trail}.{key}")
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    check(value, f"{trail}[{index}]")

        for document in documents:
            check(document, "")

    assert redacted, "no PROTAC-DB-sourced record in the atlas: nothing was checked"
