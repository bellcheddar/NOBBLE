"""Ligand chain encoding (spec 2.2).

CCD codes are preferred over SMILES: Boltz resolves a CCD code against its own
component dictionary, which fixes the chemistry exactly, whereas a SMILES string
is re-perceived per run. Where no CCD match exists the job falls back to SMILES
and is flagged in the manifest so the difference is visible in the results table
rather than buried.

Boltz 2.2.x caps the affinity head at 128 heavy atoms. Several PROTACs exceed it.
A ligand over the cap still runs its structure prediction: only the affinity
readout is unavailable, and that is recorded as `affinity_unavailable` rather
than failing the job.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache

from nobble import paths
from nobble.curate import binman_store as store


@dataclass
class Ligand:
    """A small molecule as it will be submitted to Boltz."""

    key: str
    encoding: str                 # "ccd" or "smiles"
    ccd: str | None
    smiles: str | None
    name: str | None
    heavy_atoms: int | None
    ccd_class: str | None
    is_furniture: bool
    affinity_available: bool
    modality: str                 # "glue" or "protac"
    source: str
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@lru_cache(maxsize=1)
def _ccd_index() -> dict[str, dict]:
    """BINMAN's ligand table, keyed by CCD code."""
    return {
        row["ccd_id"]: row
        for row in store.atlas_rows(
            "select ccd_id, name, formula, mw, heavy_atoms, smiles, ccd_class, "
            "       is_furniture from ligand where status = 'ok'"
        )
    }


@lru_cache(maxsize=1)
def _name_index() -> dict[str, str]:
    """Lower-cased ligand name to CCD code, for resolving a named compound."""
    index: dict[str, str] = {}
    for code, row in _ccd_index().items():
        name = (row.get("name") or "").strip().lower()
        if name:
            index.setdefault(name, code)
    return index


def by_ccd(code: str, modality: str = "glue", source: str = "deposited") -> Ligand:
    """Build a ligand from a CCD code, carrying whatever BINMAN knows about it."""
    cap = int(paths.thresholds()["manifest"]["affinity_heavy_atom_cap"])
    row = _ccd_index().get(code.upper(), {})
    heavy = row.get("heavy_atoms")
    notes: list[str] = []

    if not row:
        notes.append(
            "CCD code not present in BINMAN's ligand table: Boltz will still "
            "resolve it against its own component dictionary, but heavy-atom "
            "count and class are unknown here"
        )
    affinity = heavy is not None and heavy <= cap
    if heavy is not None and heavy > cap:
        notes.append(
            f"affinity_unavailable: {heavy} heavy atoms exceeds the {cap}-atom "
            "affinity-head cap. Structure prediction runs normally"
        )
    elif heavy is None:
        notes.append("affinity_unavailable: heavy-atom count unknown, so the cap cannot be checked")

    return Ligand(
        key=code.upper(),
        encoding="ccd",
        ccd=code.upper(),
        smiles=row.get("smiles"),
        name=row.get("name"),
        heavy_atoms=heavy,
        ccd_class=row.get("ccd_class"),
        is_furniture=bool(row.get("is_furniture")),
        affinity_available=affinity,
        modality=modality,
        source=source,
        notes=notes,
    )


def by_name(name: str, modality: str = "glue", source: str = "named") -> Ligand | None:
    """Resolve a compound name to a CCD code via BINMAN's ligand names."""
    code = _name_index().get(name.strip().lower())
    if code:
        ligand = by_ccd(code, modality=modality, source=source)
        ligand.notes.append(f"resolved from the name {name!r}")
        return ligand
    return None


def by_smiles(
    smiles: str, key: str, name: str | None = None,
    modality: str = "glue", source: str = "smiles_fallback",
) -> Ligand:
    """Fallback encoding, flagged so the manifest shows which jobs used it."""
    from rdkit import Chem

    heavy = None
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is not None:
        heavy = molecule.GetNumHeavyAtoms()

    cap = int(paths.thresholds()["manifest"]["affinity_heavy_atom_cap"])
    notes = ["no CCD match: encoded as SMILES and flagged (spec 2.2)"]
    if molecule is None:
        notes.append("rdkit could not parse the SMILES: job will fail validation")
    elif heavy is not None and heavy > cap:
        notes.append(f"affinity_unavailable: {heavy} heavy atoms exceeds the {cap}-atom cap")

    return Ligand(
        key=key,
        encoding="smiles",
        ccd=None,
        smiles=smiles,
        name=name,
        heavy_atoms=heavy,
        ccd_class=None,
        is_furniture=False,
        affinity_available=heavy is not None and heavy <= cap,
        modality=modality,
        source=source,
        notes=notes,
    )


# The glue or degrader of each benchmark member, by the CCD actually present in
# its deposited ternary (read from the structure, not declared).
BENCHMARK_LIGANDS = {
    1: ("85C", "glue"),      # CC-885
    2: ("759", "protac"),    # MZ1
    3: (None, "protac"),     # dBET: absent from assembly 1 of 6BNB
    4: ("Y70", "glue"),      # S-pomalidomide
    5: ("LVY", "glue"),      # S-lenalidomide
    6: ("EF6", "glue"),      # indisulam
    7: ("RC8", "glue"),      # CR-8
}


def _protacdb_smiles(name_fragment: str) -> tuple[str, str] | None:
    """First PROTAC-DB row whose name contains `name_fragment`, as (name, SMILES)."""
    for row in store.dataset("protacdb_protacs"):
        name = str(row.get("name") or "")
        if name_fragment.lower() in name.lower() and (row.get("smiles") or "").strip():
            return name, row["smiles"].strip()
    return None


def benchmark_ligands() -> dict[int, Ligand | None]:
    """The glue or degrader of each benchmark member.

    Members whose ligand is present in the deposited assembly use its CCD code,
    which is the exact chemistry that was refined into the density. Member 3 is
    the exception: 6BNB's assembly 1 carries no PROTAC at all (only a structural
    zinc), so its dBET is encoded from PROTAC-DB's SMILES and flagged. That is
    the fallback spec 2.2 provides for, and the flag is what keeps the
    difference visible in the results table.
    """
    resolved: dict[int, Ligand | None] = {}
    for index, (code, modality) in BENCHMARK_LIGANDS.items():
        if code is not None:
            resolved[index] = by_ccd(code, modality=modality, source="deposited_ternary")
            continue
        # No CCD in the deposition: fall back to the curated SMILES.
        found = _protacdb_smiles("dBET57") or _protacdb_smiles("dBET")
        if not found:
            resolved[index] = None
            continue
        name, smiles = found
        ligand = by_smiles(
            smiles, key=name.replace(" ", "_"), name=name,
            modality=modality, source="protacdb",
        )
        ligand.notes.append(
            "6BNB assembly 1 contains no PROTAC, so the degrader could not be "
            "taken from the deposition"
        )
        resolved[index] = ligand
    return resolved


def _recall_rows() -> list[dict]:
    """CCDs observed bridging a triaged E3 ligase, most-deposited first.

    Three conditions, each from a different table, and all three are needed:

    - `edge.edge_type = 'bridged_by'` with a triaged ligase on one side: the
      compound was seen between this ligase and another chain in a deposited
      structure. This is what makes it a glue *against a ligase* rather than
      a glue in general.
    - a bridge of the same CCD classed `molecular_glue` or `protac` by
      BINMAN, not symmetry-mediated: the bridge is the kind of contact the
      campaign is about, rather than a native cofactor sitting in a cleft or
      a lattice contact.
    - `ligand.is_furniture = 0`: citrate and tetraethylene glycol both appear
      between a ligase and its partner, and both are the crystallographer's
      doing.

    Dropping any one of them lets furniture in. Without the furniture flag the
    set gains citrate, PEG and N-heptanoyl-N-hydroxy-beta-alanine; without the
    evidence class it gains inositol hexaphosphate, which bridges KBTBD4 and
    RNF113A as a native cofactor.
    """
    return store.atlas_rows(
        "select e.ccd_id, count(distinct e.pdb_id) deposited_in, "
        "       group_concat(distinct coalesce(l1.gene, l2.gene)) ligases "
        "from edge e "
        "left join ligase l1 on l1.uniprot_acc = e.source_acc "
        "left join ligase l2 on l2.uniprot_acc = e.target_acc "
        "join ligand g on g.ccd_id = e.ccd_id and g.status = 'ok' "
        "     and g.is_furniture = 0 "
        "where e.status = 'ok' and e.edge_type = 'bridged_by' "
        "  and e.ccd_id is not null "
        "  and (l1.gene is not null or l2.gene is not null) "
        "  and exists (select 1 from bridge b where b.ccd_id = e.ccd_id "
        "              and b.status = 'ok' and b.symmetry_mediated = 0 "
        "              and b.evidence_class in ('molecular_glue', 'protac')) "
        "group by 1 order by deposited_in desc, e.ccd_id"
    )


# The glues and degraders this campaign already runs. They are the positive
# controls of the recall set: a definition of "known glue chemotype" that
# excludes pomalidomide or MZ1 is wrong whatever else it contains. Used to
# choose which CCD represents a scaffold, not to add anything: each of these
# earns its place in `_recall_rows` on the same evidence as the rest.
CURATED_GLUES = frozenset(
    code for code, _ in BENCHMARK_LIGANDS.values() if code is not None
)


def _recall_order() -> list[dict]:
    """The recall rows, in the order scaffold representatives are chosen.

    A curated glue first, then the most-deposited, then the code. The last of
    those three is arbitrary and is there only so the set does not depend on
    the order the database returns rows in.
    """
    return sorted(
        _recall_rows(),
        key=lambda row: (
            row["ccd_id"] not in CURATED_GLUES,
            -(row["deposited_in"] or 0),
            row["ccd_id"],
        ),
    )


def _chemotype(smiles: str | None) -> str | None:
    """Bemis-Murcko scaffold, or None if it cannot be derived.

    RDKit is present in the curation environment and absent from the droplet,
    so this degrades to None rather than raising: a caller that cannot
    deduplicate gets every CCD and is told so, which is a longer list rather
    than a wrong one.
    """
    if not smiles:
        return None
    try:
        from rdkit import Chem, RDLogger
        from rdkit.Chem.Scaffolds import MurckoScaffold
    except ImportError:
        return None
    RDLogger.DisableLog("rdApp.*")
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        return None
    try:
        scaffold = MurckoScaffold.GetScaffoldForMol(molecule)
    except Exception:                                       # noqa: BLE001
        return None
    # An acyclic compound has an empty Murcko scaffold. Keyed by its own
    # code rather than by "", so a dozen unrelated acyclic compounds do not
    # collapse into one chemotype.
    return Chem.MolToSmiles(scaffold) or None


def glue_recall_set(limit: int | None = None) -> list[Ligand]:
    """Known glue chemotypes, for the Tier B recall arm (spec 3.3).

    Spec 3.3 runs Tier B against "the glue recall sets" and asks whether any
    known glue chemotype shows a Delta-ipTM signal against an unexploited
    ligase. That question needs compounds that are known to glue. It names
    MGDB, MolGlueDB and MGTbind, none of which BINMAN's atlas holds, so the
    set is derived from the evidence the rest of this project already runs
    on: a compound observed bridging a triaged E3 ligase in a deposited
    structure, classed as a glue or a degrader rather than as a cofactor or a
    lattice contact. 130 CCDs across CRBN, VHL, KBTBD4, DCAF16 and RNF113A.
    All five of the benchmark panel's curated glues are in it, which is the
    check that the definition is not merely plausible.

    What this replaced was wrong in a way worth recording (F133). It selected
    `ccd_class = 'glue_candidate'`, whose rule is
    `size_and_no_furniture_signal`: a negative definition meaning "big enough
    not to be furniture, and nothing says it is furniture". 7,676 CCDs
    qualify, among them 3-nitrotoluene and adipic acid, and the ordering was
    `heavy_atoms asc`, so any limit took the smallest and least glue-like
    end of a bucket that was never glue-specific. `glue_recall_set(15)`
    returned fifteen benzene derivatives of ten heavy atoms each.

    `limit` counts chemotypes, not molecules, because the spec's question is
    about chemotypes: pomalidomide, EF2 and F4U share one phthalimide-
    glutarimide scaffold and answer the question once between them. Without
    RDKit no scaffold can be derived, and then every CCD is its own chemotype
    and says so.

    Which CCD represents a scaffold is decided by `_recall_order`, and it has
    to be, because deposited counts tie and the tie-break then picks by code.
    Lenalidomide shares its scaffold with A1IWG at one deposition each, A1IWG
    sorts first alphabetically, and the first version of this dropped
    lenalidomide out of a set of known glue chemotypes. A positive control
    leaving the set quietly is the defect; the deduplication is correct.
    """
    index = _ccd_index()
    seen: set[str] = set()
    ligands: list[Ligand] = []
    for row in _recall_order():
        code = row["ccd_id"]
        chemotype = _chemotype((index.get(code) or {}).get("smiles"))
        if chemotype is not None:
            if chemotype in seen:
                continue
            seen.add(chemotype)
        ligand = by_ccd(code, source="glue_recall_set")
        ligand.notes.append(
            f"observed bridging {row['ligases']} in "
            f"{row['deposited_in']} deposited structure(s)"
        )
        if chemotype is None:
            ligand.notes.append(
                "no Murcko scaffold available, so this CCD was not "
                "deduplicated against the rest of the set"
            )
        ligands.append(ligand)
        if limit is not None and len(ligands) >= limit:
            break
    return ligands
