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


# The dBET57 SMILES from PROTAC-DB, the one benchmark ligand with no CCD
# entry and so the only published record whose chemistry is theirs.
PROTACDB_MARKER = "CC1=C(C)C2=C(S1)"


def _protacdb_leaks(bundle) -> tuple[list[str], int]:
    """Published records carrying PROTAC-DB chemistry, and how many were read.

    Returns the count as well as the offenders so a caller can tell an
    empty bundle from a clean one. The two used to be indistinguishable.
    """
    from pathlib import Path as _Path

    leaked, examined = [], 0
    for path in _Path(bundle).rglob("*"):
        if path.is_file() and path.suffix in (".json", ".jsonl"):
            examined += 1
            if PROTACDB_MARKER in path.read_text(errors="replace"):
                leaked.append(str(path))
    return leaked, examined


@pytest.mark.skipif(not ATLAS.exists(), reason="no published atlas")
def test_published_atlas_withholds_protacdb_chemistry():
    """Publishing to a public site is redistribution, exactly as a repo is.

    The loop used to be the whole test, and every assertion was inside it,
    so an absent or empty atlas passed by examining nothing. The count of
    files actually read is asserted first: a licensing guarantee that holds
    vacuously is not a guarantee (F72).
    """
    leaked, examined = _protacdb_leaks(ATLAS)
    assert not leaked, leaked
    assert examined > 0, (
        "no published record was examined, so this test proves nothing about "
        "whether PROTAC-DB chemistry travels"
    )


def test_the_leak_check_notices_an_empty_bundle(tmp_path):
    """The negative control. Weakening the guard above to `>= 0` passed,
    because the real atlas has files either way: the only way to tell a
    working guard from a broken one is to hand it a bundle with nothing in
    it (F65, F72)."""
    leaked, examined = _protacdb_leaks(tmp_path)
    assert leaked == [] and examined == 0


def test_the_leak_check_finds_a_planted_marker(tmp_path):
    """And the other control: a bundle that does carry the chemistry must
    be reported, or the sweep above is only counting files."""
    (tmp_path / "campaign.json").write_text(
        '{"smiles": "CC1=C(C)C2=C(S1)N(C)C(=O)N2"}')
    leaked, examined = _protacdb_leaks(tmp_path)
    assert examined == 1
    assert len(leaked) == 1


def _published_smiles_exist() -> bool:
    """Does the bundle publish a `smiles` field anywhere?

    The two redaction tests below both assumed it does, which was true of the
    100-pair benchmark bundle. Asked once, here, so they cannot drift apart.
    """
    import json as json_module

    for path in sorted(ATLAS.rglob("*")):
        if not path.is_file() or path.suffix not in (".json", ".jsonl"):
            continue
        text = path.read_text(errors="replace")
        try:
            if path.suffix == ".jsonl":
                documents = [json_module.loads(line)
                             for line in text.splitlines() if line.strip()]
            else:
                documents = [json_module.loads(text)]
        except json_module.JSONDecodeError:
            continue

        def walk(node) -> bool:
            if isinstance(node, dict):
                if isinstance(node.get("smiles"), str) and node["smiles"].strip():
                    return True
                return any(walk(value) for value in node.values())
            if isinstance(node, list):
                return any(walk(item) for item in node)
            return False

        if any(walk(document) for document in documents):
            return True
    return False


def test_the_published_atlas_says_what_it_withheld():
    """And the positive half: the record whose chemistry was withheld is
    named, so an atlas that withheld nothing is distinguishable from one
    whose detection stopped firing."""
    import json

    summary = json.loads((ATLAS / "ATLAS.json").read_text())
    # Preconditioned on the bundle publishing chemistry at all, which the
    # 100-pair benchmark bundle did and the 158-pair campaign bundle does
    # not: its ligands are published by CCD code only. Redaction nulls a
    # `smiles` field, so with no such field there is nothing to redact and
    # `redactions: 0` is the true answer rather than a detection that stopped
    # firing. The guarantee then holds by the stronger route, and
    # `tests/test_protacdb_verification_verifies.py` is what checks it: every
    # published SMILES compared against PROTAC-DB's own table (F218).
    if not _published_smiles_exist():
        pytest.skip(
            "the published bundle contains no `smiles` field anywhere, so "
            "nothing needed redacting: ligands are published by CCD code "
            f"only. ATLAS.json reports redactions={summary['redactions']}"
        )
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

    if not redacted:
        pytest.skip(
            "no record in the published bundle is sourced from PROTAC-DB, so "
            "this check had nothing to check. True for the 158-pair campaign: "
            "it draws on the benchmark panel and the Sievers screen, and "
            "publishes no `smiles` field at all. The guarantee is checked "
            "against PROTAC-DB's own table in "
            "tests/test_protacdb_verification_verifies.py (F218)"
        )
