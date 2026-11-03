"""Read deposited structures from BINMAN's RCSB assembly cache.

All seven benchmark depositions are already cached by BINMAN, so pose recovery
and the degron gate need no network access.
"""
from __future__ import annotations

import gzip
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path

import gemmi

from nobble import paths

ASSEMBLY_CACHE = paths.BINMAN_CACHE / "rcsb_assemblies"
WATER = {"HOH", "DOD", "WAT"}


def assembly_path(pdb_id: str) -> Path:
    return ASSEMBLY_CACHE / f"{pdb_id.upper()}-assembly1.cif.gz"


def is_cached(pdb_id: str) -> bool:
    return assembly_path(pdb_id).exists()


def is_amino_acid(residue: gemmi.Residue) -> bool:
    info = gemmi.find_tabulated_residue(residue.name)
    return bool(info and info.is_amino_acid())


def is_water(residue: gemmi.Residue) -> bool:
    return residue.name in WATER


@lru_cache(maxsize=16)
def read_assembly(pdb_id: str) -> gemmi.Structure:
    """Load a cached biological assembly. Cached per process: these are large."""
    path = assembly_path(pdb_id)
    if not path.exists():
        raise FileNotFoundError(
            f"{pdb_id} not in BINMAN's assembly cache at {path}. "
            "Fetch it into that cache rather than adding a second cache here."
        )
    with gzip.open(path, "rb") as source, tempfile.NamedTemporaryFile(
        suffix=".cif", delete=False
    ) as sink:
        shutil.copyfileobj(source, sink)
        temporary = Path(sink.name)
    try:
        structure = gemmi.read_structure(str(temporary))
        structure.setup_entities()
        structure.remove_alternative_conformations()
        return structure
    finally:
        temporary.unlink(missing_ok=True)


def chain_summary(pdb_id: str) -> list[dict]:
    """Per-chain residue counts, one-letter sequence and heteroatom inventory."""
    structure = read_assembly(pdb_id)
    summary = []
    for chain in structure[0]:
        residues = [residue for residue in chain if is_amino_acid(residue)]
        heteroatoms = sorted(
            {residue.name for residue in chain if not is_amino_acid(residue) and not is_water(residue)}
        )
        summary.append(
            {
                "chain": chain.name,
                "residues": len(residues),
                "sequence": gemmi.one_letter_code([residue.name for residue in residues]),
                "first_seqid": residues[0].seqid.num if residues else None,
                "last_seqid": residues[-1].seqid.num if residues else None,
                "heteroatoms": heteroatoms,
            }
        )
    return summary


def ligand_chains(pdb_id: str, min_atoms: int = 12) -> list[dict]:
    """Heteroatom residues large enough to be a glue or degrader, not a buffer salt."""
    structure = read_assembly(pdb_id)
    found = []
    for chain in structure[0]:
        for residue in chain:
            if is_amino_acid(residue) or is_water(residue):
                continue
            if len(residue) < min_atoms:
                continue
            found.append(
                {
                    "chain": chain.name,
                    "ccd": residue.name,
                    "seqid": residue.seqid.num,
                    "heavy_atoms": sum(1 for atom in residue if atom.element.name != "H"),
                }
            )
    return sorted(found, key=lambda item: -item["heavy_atoms"])


def contacts_to_ligand(
    pdb_id: str, ligand_ccd: str, protein_chain: str, cutoff: float = 5.0
) -> list[dict]:
    """Residues of one protein chain within `cutoff` of a named ligand.

    Used by the degron gate: the degron is the part of the substrate that packs
    against the glue and the receptor pocket, which is a measurement rather than
    an assertion about residue numbering.
    """
    structure = read_assembly(pdb_id)
    ligand_atoms = [
        atom.pos
        for chain in structure[0]
        for residue in chain
        if residue.name == ligand_ccd
        for atom in residue
        if atom.element.name != "H"
    ]
    if not ligand_atoms:
        return []

    hits = []
    for chain in structure[0]:
        if chain.name != protein_chain:
            continue
        for residue in chain:
            if not is_amino_acid(residue):
                continue
            best = min(
                (position.dist(atom.pos) for atom in residue if atom.element.name != "H"
                 for position in ligand_atoms),
                default=None,
            )
            if best is not None and best <= cutoff:
                hits.append(
                    {
                        "seqid": residue.seqid.num,
                        "name": residue.name,
                        "one_letter": gemmi.find_tabulated_residue(residue.name).one_letter_code.upper(),
                        "min_distance": round(best, 2),
                    }
                )
    return sorted(hits, key=lambda item: item["min_distance"])
