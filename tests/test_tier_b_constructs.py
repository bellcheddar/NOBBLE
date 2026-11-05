"""The Tier B construct form, and the loader that checks a filled one (F163).

Tier B is selected, frozen, gate-passed and unrunnable: spec 1.1 names a
receptor construct for each Tier A ligase and spec 3.3 names none for any of
the fifteen it selects. `config/tier_b_constructs.toml` is that gap as a
form, and this module is the mechanism rather than the judgement.

The loader is tested against a *filled* table, synthesised here, because a
module that only ever runs against an empty form is the shape this project
keeps finding defects in: F134, F137, F141, F145 and F147 were all paths
nothing had executed.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _form(tmp_path: Path, body: str, monkeypatch) -> None:
    from nobble.curate import tier_b_constructs as module

    path = tmp_path / "tier_b_constructs.toml"
    path.write_text(textwrap.dedent(body))
    monkeypatch.setattr(module, "FORM", path)


def test_the_form_ships_empty_and_parses():
    import tomllib

    from nobble.curate import tier_b_constructs as module

    document = tomllib.loads(module.FORM.read_text())
    assert "constructs" in document, "the form has no constructs table"


def test_the_form_lists_a_candidate_for_every_tier_b_gene():
    """It is a form, so it has to say what the options are.

    Without the candidates it asks fifteen people-hours of InterPro lookups
    to answer a question that is otherwise an afternoon.
    """
    from nobble.curate import tier_b_constructs as module

    text = module.FORM.read_text()
    genes = module._tier_b_genes()
    assert genes, "no frozen Tier B selection to check against"
    missing = [gene for gene in genes if f"# {gene} (" not in text]
    assert not missing, f"the form lists no candidates for {missing}"
    assert text.count("IPR") >= len(genes), (
        "fewer InterPro candidates than ligases, so some have none listed"
    )


def test_an_empty_form_blocks_and_names_every_gene(tmp_path, monkeypatch):
    """The refusal, which is what the form does until someone fills it in.

    This used to call `report()` against the real form and rely on it being
    empty. It is not empty any more (D-NOB-072 filled it), so the test was
    asserting a property of the repository rather than of the code, and it
    failed the moment the gate it was written for was closed. Built as a
    fixture now, like every other test in this file.
    """
    from nobble.curate import tier_b_constructs as module

    _form(tmp_path, "[constructs]\n", monkeypatch)
    report = module.report()
    assert report["assemblable"] is False
    assert len(report["genes_without_a_construct"]) == report["tier_b_genes"]
    assert "blocked" in report["status"]


def test_the_real_form_is_filled_in():
    """The other side of the test above, now that it is a fixture: the form
    checked into the repository is the answered one."""
    from nobble.curate import tier_b_constructs as module

    report = module.report()
    assert report["status"] == "ready", report["status"]
    assert report["genes_without_a_construct"] == []


def test_a_filled_entry_loads_as_a_construct(tmp_path, monkeypatch):
    """CCNF's cyclin box, which is among the candidates the form lists."""
    from nobble.curate import tier_b_constructs as module

    _form(tmp_path, '''
        [constructs]
        [constructs.CCNF_CYCLIN]
        e3_gene = "CCNF"
        rationale = "the cyclin box is the substrate interface; the F-box binds SKP1"
        exception = false
        [[constructs.CCNF_CYCLIN.segments]]
        accession = "P41002"
        label = "Cyclin"
        interpro_entry = "IPR039361"
    ''', monkeypatch)
    loaded = module.load()
    assert set(loaded) == {"CCNF_CYCLIN"}
    construct = loaded["CCNF_CYCLIN"]
    assert construct.e3_gene == "CCNF"
    assert len(construct.segments) == 1
    assert construct.segments[0].interpro_entry == "IPR039361"
    assert construct.residue_count() > 0
    assert module.problems() == []


def test_a_rationale_is_required(tmp_path, monkeypatch):
    """The one thing the file exists to record."""
    from nobble.curate import tier_b_constructs as module

    _form(tmp_path, '''
        [constructs]
        [constructs.CCNF_CYCLIN]
        e3_gene = "CCNF"
        [[constructs.CCNF_CYCLIN.segments]]
        accession = "P41002"
        interpro_entry = "IPR039361"
    ''', monkeypatch)
    problems = module.problems()
    assert any("rationale" in row["problem"] for row in problems), problems


def test_an_oversized_construct_needs_a_declared_exception(tmp_path, monkeypatch):
    """TRIP12's HECT span is 1,783 residues, far past the tier-1 cap."""
    from nobble.curate import tier_b_constructs as module

    body = '''
        [constructs]
        [constructs.TRIP12_HECT]
        e3_gene = "TRIP12"
        rationale = "the HECT domain"
        exception = {exception}
        [[constructs.TRIP12_HECT.segments]]
        accession = "Q14669"
        interpro_entry = "IPR045322"
    '''
    _form(tmp_path, body.format(exception="false"), monkeypatch)
    problems = module.problems()
    assert any("cap" in row["problem"] for row in problems), problems

    _form(tmp_path, body.format(exception="true"), monkeypatch)
    assert module.problems() == [], (
        "a declared exception is what spec 1.1 provides for VHL and DCAF15"
    )


def test_an_entry_naming_a_domain_the_protein_lacks_is_a_problem(
        tmp_path, monkeypatch):
    """A typo in an accession or an entry has to fail here, not at Boltz."""
    from nobble.curate import tier_b_constructs as module

    _form(tmp_path, '''
        [constructs]
        [constructs.CCNF_WRONG]
        e3_gene = "CCNF"
        rationale = "a domain this protein does not carry"
        [[constructs.CCNF_WRONG.segments]]
        accession = "P41002"
        interpro_entry = "IPR000000"
    ''', monkeypatch)
    problems = module.problems()
    assert problems and any("KeyError" in row["problem"]
                            or "not annotated" in row["problem"]
                            for row in problems), problems


def test_a_filled_form_reports_ready(tmp_path, monkeypatch):
    """So the refusal cannot become permanent: one entry per gene and the
    report says ready rather than blocked."""
    from nobble.curate import tier_b_constructs as module

    monkeypatch.setattr(module, "_tier_b_genes", lambda: ["CCNF"])
    _form(tmp_path, '''
        [constructs]
        [constructs.CCNF_CYCLIN]
        e3_gene = "CCNF"
        rationale = "the cyclin box is the substrate interface"
        [[constructs.CCNF_CYCLIN.segments]]
        accession = "P41002"
        interpro_entry = "IPR039361"
    ''', monkeypatch)
    report = module.report()
    assert report["assemblable"] is True, report
    assert report["status"] == "ready"
