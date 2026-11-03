"""Mean pLDDT from BINMAN's cached AlphaFold models.

BINMAN's ligase table carries no pLDDT column, but spec 3.3 filters Tier B on
one, so it is computed here from the cached model rather than approximated.
"""
from __future__ import annotations

from functools import lru_cache

import gemmi

from nobble import paths

AFDB_CACHE = paths.BINMAN_CACHE / "afdb"

# Width of the window scored as a proxy for "the substrate-binding domain".
# Spec 3.3 asks for the mean pLDDT of that domain, but Tier B ligases are
# unproven and have no assigned substrate-binding domain, so there is no range to
# average over. A whole-model mean is the wrong substitute: a 1,200-residue RING
# protein with one tightly folded domain and long disordered linkers scores badly
# on a whole-model mean while having exactly the well-ordered pocket the tier is
# looking for. The best contiguous window of this width is the closest honest
# proxy, and the window is reported alongside the value so the choice is visible.
DOMAIN_WINDOW = 200


def model_path(accession: str):
    return AFDB_CACHE / f"afdb_cif_{accession}.bin"


def has_model(accession: str) -> bool:
    return model_path(accession).exists()


@lru_cache(maxsize=2048)
def plddt_profile(accession: str) -> tuple[float, ...]:
    """Per-residue pLDDT, taken from the B-factor column of the AlphaFold model.

    The format is passed explicitly because BINMAN's fetcher stores every cached
    body under a .bin suffix, and gemmi infers format from the extension: left to
    infer, it raises "Unknown format" on a perfectly good mmCIF. Caught silently
    once already, which turned 20,279 usable models into a uniform "no model"
    answer, so the read is allowed to raise here and the caller records it.
    """
    path = model_path(accession)
    if not path.exists():
        return ()
    structure = gemmi.read_structure(str(path), format=gemmi.CoorFormat.Mmcif)
    values = []
    for chain in structure[0]:
        for residue in chain:
            atoms = [atom for atom in residue if atom.name == "CA"] or list(residue)
            if atoms:
                values.append(atoms[0].b_iso)
    return tuple(values)


def summary(accession: str) -> dict:
    """Whole-model and best-window mean pLDDT, with the window reported."""
    try:
        profile = plddt_profile(accession)
    except Exception as problem:            # noqa: BLE001
        return {
            "accession": accession,
            "residues": 0,
            "mean_plddt": None,
            "best_window_mean_plddt": None,
            "best_window": None,
            "status": f"unreadable: {type(problem).__name__}",
        }
    if not profile:
        return {
            "accession": accession,
            "residues": 0,
            "mean_plddt": None,
            "best_window_mean_plddt": None,
            "best_window": None,
            "status": "no_model",
        }

    whole = sum(profile) / len(profile)
    if len(profile) <= DOMAIN_WINDOW:
        best_mean, best_start = whole, 1
    else:
        running = sum(profile[:DOMAIN_WINDOW])
        best_total, best_start = running, 1
        for index in range(DOMAIN_WINDOW, len(profile)):
            running += profile[index] - profile[index - DOMAIN_WINDOW]
            if running > best_total:
                best_total, best_start = running, index - DOMAIN_WINDOW + 2
        best_mean = best_total / DOMAIN_WINDOW

    return {
        "accession": accession,
        "residues": len(profile),
        "mean_plddt": round(whole, 2),
        "best_window_mean_plddt": round(best_mean, 2),
        "best_window": [best_start, min(best_start + DOMAIN_WINDOW - 1, len(profile))],
        "status": "ok",
    }


@lru_cache(maxsize=4096)
def model_sequence(accession: str) -> str:
    """Canonical sequence read from the cached AlphaFold model.

    AlphaFold DB models the canonical UniProt sequence, so the model is a local,
    offline source for the same string the UniProt REST endpoint returns. Used
    where a campaign needs thousands of sequences and must not depend on a
    network round trip per accession.
    """
    import gemmi as _gemmi

    path = model_path(accession)
    if not path.exists():
        return ""
    try:
        structure = _gemmi.read_structure(str(path), format=_gemmi.CoorFormat.Mmcif)
    except Exception:                          # noqa: BLE001
        return ""
    for chain in structure[0]:
        residues = [residue.name for residue in chain]
        if residues:
            return _gemmi.one_letter_code(residues).upper()
    return ""
