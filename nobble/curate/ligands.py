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


def glue_recall_set(limit: int | None = None) -> list[Ligand]:
    """Glues with a resolvable CCD, for the Tier B recall arm (spec 3.3).

    Tier B is run against known glue chemotypes rather than bespoke chemistry:
    the question is whether any established chemotype shows a Delta-ipTM signal
    against an unexploited ligase. Restricted to the glue-candidate class and to
    ligands with a known heavy-atom count, so token budgeting is exact.
    """
    rows = store.atlas_rows(
        "select ccd_id from ligand where status = 'ok' and ccd_class = 'glue_candidate' "
        "and heavy_atoms is not null and is_furniture = 0 "
        "order by heavy_atoms asc"
    )
    ligands = [by_ccd(row["ccd_id"], source="glue_recall_set") for row in rows]
    return ligands[:limit] if limit else ligands
