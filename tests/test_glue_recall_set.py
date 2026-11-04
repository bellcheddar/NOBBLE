"""The Tier B recall set must contain glues (F133).

Spec 3.3 runs Tier B against "the glue recall sets" to ask whether any known
glue chemotype shows a Delta-ipTM signal against an unexploited ligase. The
first implementation selected BINMAN's `ccd_class = 'glue_candidate'`, whose
rule is `size_and_no_furniture_signal`: 7,676 CCDs that are merely large
enough not to be furniture. Ordered by ascending heavy atoms, so a limit took
the smallest. `glue_recall_set(15)` returned fifteen benzene derivatives.

Nothing caught it because nothing called it. These are the checks that would
have, and they are checks on the content of the set rather than on the query
that produces it: a definition of "known glue chemotype" that excludes
pomalidomide, or includes 3-nitrotoluene, is wrong whatever SQL it is spelled
with.
"""
from nobble.curate import ligands as L

# The campaign's own glues and degraders. Each is in a deposited ternary with
# an E3 ligase, which is the definition the recall set implements, so each
# must survive it.
CURATED = ("Y70", "LVY", "85C", "759", "EF6")

# Members of the old `glue_candidate` bucket, at the end of it the ascending
# heavy-atom order used to return first. None is a molecular glue.
FRAGMENTS = ("3NT", "0L1", "3HB", "2AE", "1ON")

# Furniture that really does sit between a ligase and its partner in a
# deposited structure, so it passes the bridge test and has to be excluded on
# other grounds: citrate and tetraethylene glycol by the furniture flag,
# inositol hexaphosphate by its native-cofactor evidence class.
FURNITURE = ("CIT", "PG4", "IHP")


def test_every_curated_glue_is_in_the_recall_set():
    codes = {ligand.ccd for ligand in L.glue_recall_set()}
    missing = [code for code in CURATED if code not in codes]
    assert not missing, (
        f"{missing} are glues this campaign runs against deposited ternaries "
        "and are absent from the set of known glue chemotypes"
    )


def test_the_recall_set_is_not_the_size_bucket():
    codes = {ligand.ccd for ligand in L.glue_recall_set()}
    present = [code for code in FRAGMENTS + FURNITURE if code in codes]
    assert not present, f"{present} are not molecular glues"


def test_the_recall_set_is_glue_sized():
    """Not a cutoff: a comparison against the glues the campaign curates.

    The old bucket's first members had ten heavy atoms each. The smallest
    thing the campaign itself calls a glue is lenalidomide at nineteen, so a
    set whose median falls below that is not a set of glues.
    """
    ligands = L.glue_recall_set()
    sizes = sorted(item.heavy_atoms for item in ligands if item.heavy_atoms)
    median = sizes[len(sizes) // 2]
    curated = [item.heavy_atoms for item in
               (L.by_ccd(code) for code in CURATED) if item.heavy_atoms]
    assert median >= min(curated), (
        f"median {median} heavy atoms is below lenalidomide at {min(curated)}, "
        "so the set is fragments rather than glues"
    )


def test_a_limit_counts_chemotypes_and_keeps_the_controls_first():
    """The spec asks about chemotypes, so a limit of five means five of them.

    And the five are the curated glues, because `_recall_order` prefers them.
    A recall arm truncated to its first few compounds should start from the
    chemotypes whose answer is already known.
    """
    few = L.glue_recall_set(limit=len(CURATED))
    assert len(few) == len(CURATED)
    assert {item.ccd for item in few} == set(CURATED)


def test_chemotypes_are_distinct():
    ligands = L.glue_recall_set()
    index = L._ccd_index()
    scaffolds = [
        L._chemotype((index.get(item.ccd) or {}).get("smiles"))
        for item in ligands
    ]
    derived = [s for s in scaffolds if s is not None]
    assert len(derived) == len(set(derived)), (
        "two CCDs in the set share a Murcko scaffold, so the set counts one "
        "chemotype twice"
    )


def test_lenalidomide_wins_its_scaffold_against_the_alphabet():
    """The regression that made the preference rule necessary.

    LVY and A1IWG share a scaffold at one deposition each. Sorting by code
    alone puts A1IWG first and drops lenalidomide. Checked on the real pair
    rather than a fixture, because the pair is the point.
    """
    order = [row["ccd_id"] for row in L._recall_order()]
    assert "LVY" in order and "A1IWG" in order
    assert order.index("LVY") < order.index("A1IWG")


def test_the_order_does_not_depend_on_the_database(monkeypatch):
    rows = [
        {"ccd_id": "AAA1", "deposited_in": 1, "ligases": "CRBN"},
        {"ccd_id": "Y70", "deposited_in": 1, "ligases": "CRBN"},
        {"ccd_id": "ZZZ9", "deposited_in": 9, "ligases": "VHL"},
    ]
    for order in (rows, list(reversed(rows)), [rows[1], rows[2], rows[0]]):
        monkeypatch.setattr(L, "_recall_rows", lambda order=order: list(order))
        codes = [row["ccd_id"] for row in L._recall_order()]
        assert codes == ["Y70", "ZZZ9", "AAA1"], codes


def test_no_scaffold_means_no_deduplication_and_a_note(monkeypatch):
    """Without RDKit the set is longer, not wrong, and says which entries
    could not be deduplicated."""
    monkeypatch.setattr(L, "_chemotype", lambda smiles: None)
    ligands = L.glue_recall_set(limit=3)
    assert len(ligands) == 3
    for item in ligands:
        assert any("not deduplicated" in note for note in item.notes), item.notes


def test_every_entry_records_the_evidence_it_was_selected_on():
    for item in L.glue_recall_set(limit=10):
        assert any("observed bridging" in note for note in item.notes), item.notes
        assert item.source == "glue_recall_set"


# Molecular glues of something that is not an E3 ligase. Rapamycin and FK506
# are the textbook examples of the mechanism, the fluoroquinolones bridge
# gyrase and DNA, and etoposide bridges topoisomerase and DNA. Every one is a
# known glue and none has been observed on a ligase, so every one belongs
# outside a set whose question is about ligases.
GLUES_OF_OTHER_THINGS = ("RAP", "FK5", "FSC", "MFX", "LFX", "CPF", "EVP")


def test_the_set_is_glues_of_a_ligase_not_glues_in_general():
    """The condition this pins is the join to BINMAN's ligase table.

    Dropping it takes the set from 130 CCDs to 1,248. None of the other
    checks here notice: the curated glues are still present, the fragments
    are still absent, the chemotypes are still distinct, and the median is
    still glue-sized, because what arrives is a thousand real glues of the
    wrong proteins. Measured after a mutation sweep found no test failing
    with the join removed.
    """
    codes = {ligand.ccd for ligand in L.glue_recall_set()}
    present = [code for code in GLUES_OF_OTHER_THINGS if code in codes]
    assert not present, (
        f"{present} are glues of proteins that are not E3 ligases, so the "
        "set is no longer scoped to the question spec 3.3 asks"
    )


def test_those_compounds_are_excluded_by_the_join_and_not_by_luck():
    """The other half of the check above.

    Asserting that seven codes are absent proves nothing unless they would
    otherwise be present: the same assertion passes against an empty set, or
    against one that excludes them for some unrelated reason.
    """
    from nobble.curate import binman_store as store
    # The same query `_recall_rows` runs with the ligase join removed, and
    # narrowed to these seven codes. Narrowed because the unrestricted form
    # returns 1,248 rows and took 35 seconds of the suite to prove a point
    # about seven of them.
    placeholders = ", ".join("?" for _ in GLUES_OF_OTHER_THINGS)
    rows = store.atlas_rows(
        "select e.ccd_id from edge e "
        "join ligand g on g.ccd_id = e.ccd_id and g.status = 'ok' "
        "     and g.is_furniture = 0 "
        "where e.status = 'ok' and e.edge_type = 'bridged_by' "
        f"  and e.ccd_id in ({placeholders}) "
        "  and exists (select 1 from bridge b where b.ccd_id = e.ccd_id "
        "              and b.status = 'ok' and b.symmetry_mediated = 0 "
        "              and b.evidence_class in ('molecular_glue', 'protac')) "
        "group by 1",
        tuple(GLUES_OF_OTHER_THINGS),
    )
    unjoined = {row["ccd_id"] for row in rows}
    missing = [code for code in GLUES_OF_OTHER_THINGS if code not in unjoined]
    assert not missing, (
        f"{missing} are no longer in the set the ligase join filters, so the "
        "test above would pass whether the join were there or not"
    )
