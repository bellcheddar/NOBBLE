"""Lysine reach measurements (spec 4.2), reported as measurements and not as a fit.

Spec 4.2 says to "apply BINMAN's reach-window fit (already calibrated against 976
observed diGly sites)". That premise does not hold, and this module is written
around what BINMAN actually measured rather than what the spec assumed.

BINMAN attempted the fit and it failed, on its own evidence and by its own
decision. Its `config/thresholds.toml` carries `fitted = false` with the
measurements that justify it, and its FINDINGS.md records the same: on 369
assayed lysines in 43 induced ternary complexes, the three Cb-Cb reach
boundaries reach AUC **0.4223, 0.4770 and 0.4595**, and relative SASA reaches
0.5020. Those are at or below chance, and the Cb-Cb direction is slightly
inverted: ubiquitylated lysines sit *farther* from the ligand than unmodified
ones (median 18.73 against 14.89 angstrom).

BINMAN's explanation is mechanistic rather than technical, and it is the reason
this is unlikely to be fixable by refitting: the ligand site is where a substrate
is recruited, and not where ubiquitin is transferred. The E2 that does the
transferring sits elsewhere on the cullin scaffold, tens of angstrom away and
not present in the trimmed construct at all.

So NOBBLE computes the geometry, which is real, and reports it as descriptive
columns with an explicit `status`. It does not emit a `lysine_reach_fit` score
that implies a validated window, and the About page states the AUCs. See
D-NOB-024.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field

from nobble import paths

# BINMAN's measured discrimination for this signal, carried here so the number
# travels with the code that would otherwise imply it had been validated.
BINMAN_REACH_AUC = {
    "cb_cb_distance": 0.4223,
    "nz_centroid_distance": 0.4770,
    "nz_rel_sasa": 0.4595,
    "nz_rel_sasa_within_protein": 0.5020,
    "n_lysines": 369,
    "n_ternary_entries": 43,
    "ubiquitylated_median_cb_cb": 18.73,
    "unmodified_median_cb_cb": 14.89,
    "source": "BINMAN data/interim/degradability_reach.json and D-068",
}

STATUS_NOT_VALIDATED = (
    "not_validated: BINMAN's reach window is deliberately unfitted "
    "(fitted = false). Cb-Cb AUC 0.42 to 0.48 on 369 assayed lysines, at or "
    "below chance and slightly inverted. Geometry is reported as a measurement, "
    "not as a validated predictor."
)


@dataclass
class LysineReach:
    """Where the peptide's lysines sit relative to the glue and the interface."""

    job_id: str
    peptide_lysines: int
    lysine_detail: list[dict] = field(default_factory=list)
    nearest_lysine_to_ligand: float | None = None
    mean_lysine_rel_sasa: float | None = None
    exposed_lysines: int = 0
    status: str = STATUS_NOT_VALIDATED
    reach_auc_reference: dict = field(default_factory=lambda: dict(BINMAN_REACH_AUC))
    # Deliberately absent: a single `lysine_reach_fit` score. See the module
    # docstring and D-NOB-024.
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# Theoretical maximum solvent accessibility for lysine, Angstrom^2
# (Tien et al., PLoS ONE 2013, 8(11):e80635), the same reference BINMAN uses.
LYSINE_MAX_ASA = 236.0
EXPOSED_REL_SASA = float(paths.thresholds()["lysine"]["exposed_rel_sasa"])


def measure(job: dict) -> LysineReach:
    """Measure lysine geometry in one predicted complex."""
    import freesasa
    import gemmi

    from nobble.score.poses import PEPTIDE_CHAIN, _load, _receptor_chain_ids

    result = LysineReach(job_id=job["job_id"], peptide_lysines=0)
    if not job.get("structure"):
        result.notes.append("no predicted structure")
        return result

    structure = _load(job["structure"])
    receptor_ids = _receptor_chain_ids(job["construct"])

    ligand_positions = []
    for chain in structure[0]:
        if chain.name != "L":
            continue
        for residue in chain:
            for atom in residue:
                if atom.element.name != "H":
                    ligand_positions.append(atom.pos)

    # SASA of the whole complex, so exposure is measured in context rather than
    # on an isolated peptide, where every residue looks exposed.
    radii, coords, labels = [], [], []
    for chain in structure[0]:
        if chain.name not in receptor_ids and chain.name not in {PEPTIDE_CHAIN, "L"}:
            continue
        for residue in chain:
            for atom in residue:
                if atom.element.name == "H":
                    continue
                coords.extend((atom.pos.x, atom.pos.y, atom.pos.z))
                radii.append(
                    {"C": 1.7, "N": 1.55, "O": 1.52, "S": 1.8, "P": 1.8}.get(
                        atom.element.name.upper(), 1.7
                    )
                )
                labels.append((chain.name, residue.seqid.num, residue.name, atom.name))

    if not radii:
        result.notes.append("no heavy atoms parsed")
        return result

    sasa = freesasa.calcCoord(coords, radii)
    per_residue: dict[tuple[str, int, str], float] = {}
    for index, label in enumerate(labels):
        key = (label[0], label[1], label[2])
        per_residue[key] = per_residue.get(key, 0.0) + sasa.atomArea(index)

    nz_positions: dict[int, object] = {}
    for chain in structure[0]:
        if chain.name != PEPTIDE_CHAIN:
            continue
        for residue in chain:
            if residue.name != "LYS":
                continue
            result.peptide_lysines += 1
            for atom in residue:
                if atom.name == "NZ":
                    nz_positions[residue.seqid.num] = atom.pos

    for chain in structure[0]:
        if chain.name != PEPTIDE_CHAIN:
            continue
        for residue in chain:
            if residue.name != "LYS":
                continue
            area = per_residue.get((chain.name, residue.seqid.num, residue.name), 0.0)
            relative = round(area / LYSINE_MAX_ASA, 4)
            nz = nz_positions.get(residue.seqid.num)
            distance = None
            if nz is not None and ligand_positions:
                distance = round(
                    min(
                        math.sqrt(
                            (nz.x - other.x) ** 2
                            + (nz.y - other.y) ** 2
                            + (nz.z - other.z) ** 2
                        )
                        for other in ligand_positions
                    ),
                    2,
                )
            result.lysine_detail.append(
                {
                    "peptide_position": residue.seqid.num,
                    "nz_rel_sasa": relative,
                    "nz_to_ligand_min_distance": distance,
                    "exposed": relative >= EXPOSED_REL_SASA,
                }
            )

    if result.lysine_detail:
        exposures = [item["nz_rel_sasa"] for item in result.lysine_detail]
        result.mean_lysine_rel_sasa = round(sum(exposures) / len(exposures), 4)
        result.exposed_lysines = sum(1 for item in result.lysine_detail if item["exposed"])
        distances = [
            item["nz_to_ligand_min_distance"] for item in result.lysine_detail
            if item["nz_to_ligand_min_distance"] is not None
        ]
        if distances:
            result.nearest_lysine_to_ligand = min(distances)
    else:
        result.notes.append(
            "the peptide carries no lysine. Spec 4.2 would call that a "
            "disqualifying result; it is recorded as a measurement, because the "
            "window that would justify disqualifying it does not discriminate"
        )
    return result
