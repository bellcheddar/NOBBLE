"""Pose convergence and pose recovery (spec 4.4 and 5.1).

Two different questions, both answered by superposition:

- **Convergence** (spec 4.4): pairwise peptide backbone RMSD across the five
  seeds, after superposing on the receptor. Convergence tracks reality better
  than confidence for peptides, because a peptide landing in the same groove
  from five different noise seeds is saying something ipTM is not. It is also
  the measure that separates a genuinely unstable interface from one collapsed
  diffusion trajectory, which is precisely the ambiguity D-NOB-023 ran into.
- **Recovery** (spec 5.1): peptide backbone RMSD to the deposited crystal
  ternary, reported as a success-rate curve at 1, 2, 3 and 5 angstrom.

Superposition is always on the **receptor**, never on the peptide. Superposing
on the peptide would measure its internal conformation and discard where it sat,
which is the only thing being asked. The receptor frame is also what makes the
crystal comparison meaningful: the question is whether the degron landed in the
right place on the E3, not whether it has the right shape in isolation.
"""
from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass, field
from functools import lru_cache

from nobble import paths
from nobble.curate import constructs as C
from nobble.curate import numbering, structures
from nobble.numeric import finite, finite_values, median_of

# Receptor anchor RMSD above which the frame is called poor, which
# qualifies every peptide RMSD measured in it. Was a literal below.
FRAME_POOR_ANCHOR_A = float(paths.thresholds()["scoring"]["frame_poor_anchor_rmsd_a"])
# Mean pairwise RMSD at which the convergence score reaches zero.
CONVERGENCE_SCALE_A = float(paths.thresholds()["scoring"]["convergence_scale_a"])

BACKBONE = ("N", "CA", "C", "O")
PEPTIDE_CHAIN = "P"


@dataclass
class ConvergenceResult:
    pair_id: str
    condition: str
    seeds: list[int]
    pairwise_rmsd: list[float] = field(default_factory=list)
    mean_rmsd: float | None = None
    max_rmsd: float | None = None
    spread: float | None = None
    convergence_score: float | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RecoveryResult:
    pair_id: str
    pdb_id: str
    job_id: str
    seed: int
    rmsd: float | None = None
    atoms_compared: int = 0
    # How good the frame itself is. A peptide RMSD is only meaningful if the
    # receptor it was superposed on actually superposed: without these two
    # numbers beside it, a large RMSD cannot be told apart from a broken
    # alignment. On the first pair they read 436 atoms at 1.75 A, which is what
    # established that a 24.9 A peptide RMSD was a real result rather than a
    # mapping bug.
    receptor_anchor_atoms: int = 0
    receptor_rmsd: float | None = None
    # The residues actually compared, as one-letter codes, predicted against
    # deposited. Two numbers establish that the frame is good; these two
    # strings establish that it is the right frame. The receptor can superpose
    # at 1.75 A onto a correctly aligned receptor while the peptide window is
    # mapped onto a different stretch of the same deposited chain, and that
    # failure arrives as a confident RMSD against the wrong residues, which is
    # what this function's own docstring has always warned about without
    # checking (F103).
    peptide_predicted_sequence: str = ""
    peptide_deposited_sequence: str = ""
    # Fraction of the compared window carrying the same residue on both
    # sides. Recorded whether or not it passes, so a variant is visible
    # rather than merely tolerated.
    peptide_identity: float | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _receptor_chain_ids(construct_name: str) -> set[str]:
    return set("ABCDEFGH"[: len(C.by_name(construct_name).segments)])


def _load(path: str):
    import gemmi

    structure = gemmi.read_structure(str(path))
    structure.setup_entities()
    structure.remove_hydrogens()
    structure.remove_alternative_conformations()
    return structure


def _backbone_by_residue(structure, chain_ids: set[str]) -> dict[tuple[str, int, str], object]:
    """Backbone atoms keyed by (chain, seqid, atom name)."""
    atoms: dict[tuple[str, int, str], object] = {}
    for chain in structure[0]:
        if chain.name not in chain_ids:
            continue
        for residue in chain:
            for atom in residue:
                if atom.name in BACKBONE:
                    atoms[(chain.name, residue.seqid.num, atom.name)] = atom.pos
    return atoms


def _superpose(moving_anchor: list, fixed_anchor: list):
    """Kabsch superposition from two matched point lists.

    Returns gemmi's Transform, which maps a point in the moving frame onto the
    fixed frame. `superpose_positions` itself returns a SupResult wrapper, and
    its `.transform.apply` yields a Vec3 rather than a Position, which is why
    `_rmsd` computes the distance component-wise rather than calling `.dist`.
    """
    import gemmi

    if len(moving_anchor) < 3:
        return None
    return gemmi.superpose_positions(fixed_anchor, moving_anchor).transform


def _rmsd(moving: list, fixed: list, transform) -> float | None:
    """Backbone RMSD, or None when it cannot be measured.

    `gemmi.Position` accepts a NaN coordinate, and one NaN anywhere in the
    sum makes the result NaN. That NaN then passed the `is not None`
    filters downstream and reached `sorted`, where it corrupts not only the
    median but the minimum and maximum, because every comparison against it
    is false. A pair's best, median and worst recovery are all published on
    the Benchmark tab (F78).
    """
    import math

    if not moving or len(moving) != len(fixed):
        return None
    total = 0.0
    for source, target in zip(moving, fixed):
        moved = transform.apply(source) if transform is not None else source
        total += (
            (moved.x - target.x) ** 2
            + (moved.y - target.y) ** 2
            + (moved.z - target.z) ** 2
        )
    value = math.sqrt(total / len(moving))
    # Unmeasurable rather than zero or infinite: a coordinate that is not a
    # number cannot produce a distance, and returning None puts this on the
    # same footing as a superposition with too few anchor atoms.
    return value if math.isfinite(value) else None


def peptide_rmsd_between(job_a: dict, job_b: dict) -> float | None:
    """Peptide backbone RMSD between two predictions, in the receptor frame."""
    if not job_a.get("structure") or not job_b.get("structure"):
        return None
    chain_ids = _receptor_chain_ids(job_a["construct"])
    first, second = _load(job_a["structure"]), _load(job_b["structure"])

    receptor_a = _backbone_by_residue(first, chain_ids)
    receptor_b = _backbone_by_residue(second, chain_ids)
    shared = sorted(set(receptor_a) & set(receptor_b))
    transform = _superpose(
        [receptor_b[key] for key in shared], [receptor_a[key] for key in shared]
    )
    if transform is None:
        return None

    peptide_a = _backbone_by_residue(first, {PEPTIDE_CHAIN})
    peptide_b = _backbone_by_residue(second, {PEPTIDE_CHAIN})
    keys = sorted(set(peptide_a) & set(peptide_b))
    if not keys:
        return None
    return _rmsd(
        [peptide_b[key] for key in keys], [peptide_a[key] for key in keys], transform
    )


def convergence(pair_jobs: list[dict], condition: str = "ternary") -> ConvergenceResult:
    """Pairwise peptide RMSD across seeds within one condition (spec 4.4)."""
    selected = [
        job for job in pair_jobs
        if job.get("complex_type") == ("ternary" if condition.startswith("ternary") else condition)
    ]
    if condition == "ternary_conditioned":
        selected = [job for job in selected if job.get("conditioning") == "conditioned"]
    elif condition == "ternary_unconstrained":
        selected = [job for job in selected if job.get("conditioning") == "unconstrained"]

    result = ConvergenceResult(
        pair_id=pair_jobs[0]["pair_id"] if pair_jobs else "",
        condition=condition,
        seeds=sorted(job["seed"] for job in selected),
    )
    if len(selected) < 2:
        result.notes.append(f"{len(selected)} structure(s): convergence needs at least two")
        return result

    values = []
    for first, second in itertools.combinations(selected, 2):
        value = peptide_rmsd_between(first, second)
        # `finite` rather than `is not None`: `_rmsd` refuses a non-finite
        # result since F78, so this is a local guarantee rather than a
        # dependence on that one staying in place (F87).
        if finite(value):
            values.append(round(value, 3))
    if not values:
        result.notes.append("no comparable pose pairs")
        return result

    result.pairwise_rmsd = values
    result.mean_rmsd = round(sum(values) / len(values), 3)
    result.max_rmsd = round(max(values), 3)
    result.spread = round(max(values) - min(values), 3)
    # A bounded score so the composite can use it: 1.0 at zero RMSD, falling
    # to 0 at the configured scale, which is roughly the point at which two
    # poses are in different places rather than the same place imprecisely.
    #
    # The scale was a bare 10.0 in this expression. It decides a published
    # component of the composite, and the cutoff sweep looks in comparisons,
    # module constants, default arguments and templates, not in arithmetic:
    # the fifth place, as in F80 (F87).
    result.convergence_score = round(
        max(0.0, 1.0 - (result.mean_rmsd / CONVERGENCE_SCALE_A)), 4)
    return result


@lru_cache(maxsize=1)
def _benchmark_peptide_index() -> dict:
    """Peptide identifier to its canonical span, for campaigns emitted before
    the span was carried on the job record itself."""
    from nobble.curate import peptides as peptide_module

    return {
        item.peptide_id: (item.accession, item.start_res, item.end_res)
        for item in peptide_module.benchmark_peptides()
    }


def _peptide_start_from_library(peptide_id: str | None) -> int | None:
    if not peptide_id:
        return None
    entry = _benchmark_peptide_index().get(peptide_id)
    return entry[1] if entry else None


IDENTITY_FLOOR = float(paths.thresholds()["scoring"]["recovery_identity_floor"])


def _one_letter(residue_name: str) -> str:
    """One-letter code for a residue name, or "?" when gemmi does not know it.

    "?" rather than a blank or a guess: it has to compare unequal to a real
    code so that an unrecognised residue on either side fails the identity
    check instead of passing it silently.
    """
    if not residue_name:
        return "?"
    import gemmi

    code = gemmi.find_tabulated_residue(residue_name)
    letter = (code.one_letter_code or "").upper() if code else ""
    return letter if letter.isalpha() else "?"


def recovery_against_crystal(
    job: dict, pdb_id: str, substrate_chain: str, substrate_accession: str,
    receptor_chain: str, receptor_accession: str,
) -> RecoveryResult:
    """Peptide backbone RMSD to the deposited ternary (spec 5.1).

    Both numbering frames are crossed explicitly. The predicted peptide is
    numbered 1..N within its own chain; its canonical residues come from where
    the window was cut; and the deposited chain may sit in a different frame
    again, which for GSPT1 is 138 residues away (D-NOB-012). Getting this wrong
    produces a confident RMSD against the wrong residues.
    """
    result = RecoveryResult(
        pair_id=job["pair_id"], pdb_id=pdb_id, job_id=job["job_id"], seed=job["seed"]
    )
    if not job.get("structure"):
        result.notes.append("no predicted structure")
        return result

    predicted = _load(job["structure"])
    deposited = structures.read_assembly(pdb_id)

    # Receptor frame: map the construct's residues onto the deposition.
    construct = C.by_name(job["construct"])
    segment_index = next(
        (index for index, segment in enumerate(construct.segments)
         if segment.accession == receptor_accession), None
    )
    if segment_index is None:
        result.notes.append(f"{receptor_accession} is not a segment of {construct.name}")
        return result
    segment_start, _segment_end = construct.segments[segment_index].range()
    predicted_receptor_chain = "ABCDEFGH"[segment_index]

    try:
        receptor_frame = numbering.resolve_frame(
            pdb_id, receptor_chain, receptor_accession
        )
        substrate_frame = numbering.resolve_frame(
            pdb_id, substrate_chain, substrate_accession
        )
    except numbering.FrameUnresolved as error:
        result.notes.append(f"frame unresolved: {error}")
        return result

    # Anchor on the receptor: predicted construct position -> canonical ->
    # deposited numbering.
    deposited_atoms: dict[tuple[int, str], object] = {}
    for chain in deposited[0]:
        if chain.name != receptor_chain:
            continue
        for residue in chain:
            for atom in residue:
                if atom.name in BACKBONE:
                    deposited_atoms[(residue.seqid.num, atom.name)] = atom.pos

    moving, fixed = [], []
    for chain in predicted[0]:
        if chain.name != predicted_receptor_chain:
            continue
        for residue in chain:
            canonical = segment_start + residue.seqid.num - 1
            deposited_number = receptor_frame.to_deposited(canonical)
            for atom in residue:
                if atom.name not in BACKBONE:
                    continue
                target = deposited_atoms.get((deposited_number, atom.name))
                if target is not None:
                    moving.append(atom.pos)
                    fixed.append(target)

    transform = _superpose(moving, fixed)
    if transform is None:
        result.notes.append(
            f"receptor anchor too small: {len(moving)} matched backbone atoms"
        )
        return result
    result.receptor_anchor_atoms = len(moving)
    anchor_rmsd = _rmsd(moving, fixed, transform)
    result.receptor_rmsd = round(anchor_rmsd, 3) if anchor_rmsd is not None else None
    if result.receptor_rmsd is not None and result.receptor_rmsd > FRAME_POOR_ANCHOR_A:
        result.notes.append(
            f"receptor superposed at only {result.receptor_rmsd} A: the frame is "
            "poor, so the peptide RMSD below is not a reliable measure of pose "
            "recovery"
        )

    # Compare the peptide, in the same frame.
    deposited_peptide: dict[tuple[int, str], object] = {}
    for chain in deposited[0]:
        if chain.name != substrate_chain:
            continue
        for residue in chain:
            for atom in residue:
                if atom.name in BACKBONE:
                    deposited_peptide[(residue.seqid.num, atom.name)] = atom.pos

    peptide_start = job.get("peptide_start_res") or _peptide_start_from_library(
        job.get("peptide_id")
    )
    if peptide_start is None:
        result.notes.append(
            "peptide canonical start not recorded on the job and not resolvable "
            "from the peptide library: cannot align the predicted window to the "
            "deposited chain"
        )
        return result

    # Residue names on the deposited side, for the identity check below.
    deposited_names: dict[int, str] = {}
    for chain in deposited[0]:
        if chain.name != substrate_chain:
            continue
        for residue in chain:
            deposited_names[residue.seqid.num] = residue.name

    peptide_moving, peptide_fixed = [], []
    predicted_codes, deposited_codes = [], []
    for chain in predicted[0]:
        if chain.name != PEPTIDE_CHAIN:
            continue
        for residue in chain:
            canonical = peptide_start + residue.seqid.num - 1
            deposited_number = substrate_frame.to_deposited(canonical)
            matched_here = False
            for atom in residue:
                if atom.name not in BACKBONE:
                    continue
                target = deposited_peptide.get((deposited_number, atom.name))
                if target is not None:
                    peptide_moving.append(atom.pos)
                    peptide_fixed.append(target)
                    matched_here = True
            if matched_here:
                predicted_codes.append(_one_letter(residue.name))
                deposited_codes.append(
                    _one_letter(deposited_names.get(deposited_number, "")))

    if not peptide_moving:
        result.notes.append(
            "no overlapping peptide backbone atoms between the prediction and "
            "the deposition after frame mapping"
        )
        return result

    result.peptide_predicted_sequence = "".join(predicted_codes)
    result.peptide_deposited_sequence = "".join(deposited_codes)
    agreeing = sum(1 for predicted_code, deposited_code
                   in zip(predicted_codes, deposited_codes)
                   if predicted_code == deposited_code)
    result.peptide_identity = (
        round(agreeing / len(predicted_codes), 4) if predicted_codes else None
    )
    differing = [
        index + 1 for index, (predicted_code, deposited_code)
        in enumerate(zip(predicted_codes, deposited_codes))
        if predicted_code != deposited_code
    ]
    if differing and result.peptide_identity is not None \
            and result.peptide_identity >= IDENTITY_FLOOR:
        # Aligned, and not identical. Ordinary sequence variation between the
        # canonical isoform and the crystallised construct: 6TD3 carries an R
        # where Q9NYV4 has a K. Reported, not refused, because discarding a
        # 294-residue measurement over one conservative substitution loses a
        # real result to a check meant to catch misalignment.
        result.notes.append(
            f"{len(differing)} residue(s) differ between the prediction and "
            f"{pdb_id} chain {substrate_chain} at window position(s) "
            f"{differing[:8]}, identity {result.peptide_identity}: taken as "
            "sequence variation rather than a frame error, and the RMSD is "
            "reported"
        )
    if result.peptide_identity is not None and result.peptide_identity < IDENTITY_FLOOR:
        # A refusal, not a note. Nothing downstream reads `notes`, and an RMSD
        # against the wrong residues is confident, stable across seeds and
        # indistinguishable from a real result: ten seeds agreeing to within
        # an angstrom of each other and sitting 45 A from the reference is
        # exactly what a window mapped onto the wrong stretch looks like
        # (F81's lesson, applied here).
        result.notes.append(
            f"only {result.peptide_identity} of the compared window carries "
            f"the same residue in the prediction and in {pdb_id} chain "
            f"{substrate_chain}, below the {IDENTITY_FLOOR} floor: "
            f"{result.peptide_predicted_sequence[:60]} against "
            f"{result.peptide_deposited_sequence[:60]}. The frame mapping for "
            f"{substrate_accession} is wrong, so no RMSD is reported"
        )
        result.atoms_compared = len(peptide_moving)
        return result

    result.rmsd = round(_rmsd(peptide_moving, peptide_fixed, transform) or 0.0, 3)
    result.atoms_compared = len(peptide_moving)
    return result


def success_rate_curve(values: list[float], breakpoints=None) -> dict:
    """Fraction of poses within each RMSD breakpoint (spec 5.1).

    Breakpoints come from `thresholds.toml`, not from this signature. The
    project rule is that no cutoff is hard-coded in Python, and this one had
    been sitting in the default argument while the configured value went
    unread: changing the config would have changed nothing.
    """
    if breakpoints is None:
        breakpoints = tuple(
            paths.thresholds()["scoring"].get("rmsd_breakpoints", (1.0, 2.0, 3.0, 5.0))
        )
    present = finite_values(values)
    if not present:
        return {f"within_{point}A": None for point in breakpoints} | {"n": 0}
    curve = {
        f"within_{point}A": round(
            sum(1 for value in present if value <= point) / len(present), 4
        )
        for point in breakpoints
    }
    curve["n"] = len(present)
    curve["median_rmsd"] = round(median_of(present), 3)
    return curve


# Minimum heavy-atom distance below which the peptide counts as docked onto the
# receptor at all. This is a presence check, not an interface quality measure:
# spec 4.1 scores interface quality against the atlas, and this only separates
# "the peptide is on the protein" from "the peptide is in solvent".
DOCKED_CONTACT_CUTOFF = float(paths.thresholds()["geometry"]["docked_contact_cutoff_a"])


@dataclass
class DockingCheck:
    """Is the peptide on the receptor at all, in this prediction?

    Added after the first benchmark pair made it necessary. Its five conditioned
    ternary seeds gave receptor-peptide ipTM of 0.885, 0.877, 0.806, 0.082 and
    0.911, and the 0.082 seed turned out to have left the peptide **81 angstrom
    from the receptor centroid**, floating free in solvent, against 19 angstrom
    for a docked seed. So that ipTM was not a numerical artefact: it was correct,
    and the trajectory had simply failed to dock the peptide.

    That distinction matters for every number downstream. An undocked pose should
    not contribute to a mean interface score, a pose RMSD against it is
    meaningless, and counting it as a low-confidence interface rather than a
    failed run misreads what happened. It is also a different failure from a
    peptide that docks but which the glue does not bridge, which is what seeds 2
    and 3 of the same pair did.
    """

    job_id: str
    docked: bool
    contact_atoms: int
    min_distance: float | None
    centroid_distance: float | None
    peptide_atoms: int

    def to_dict(self) -> dict:
        return asdict(self)


def docking_check(job: dict) -> DockingCheck:
    """Whether the predicted peptide touches the receptor at all."""
    import math

    structure = _load(job["structure"])
    chain_ids = _receptor_chain_ids(job["construct"])

    receptor_positions = []
    peptide_positions = []
    for chain in structure[0]:
        target = (
            receptor_positions if chain.name in chain_ids
            else peptide_positions if chain.name == PEPTIDE_CHAIN
            else None
        )
        if target is None:
            continue
        for residue in chain:
            for atom in residue:
                if atom.element.name != "H":
                    target.append(atom.pos)

    if not receptor_positions or not peptide_positions:
        return DockingCheck(job["job_id"], False, 0, None, None, len(peptide_positions))

    def centroid(positions):
        return (
            sum(item.x for item in positions) / len(positions),
            sum(item.y for item in positions) / len(positions),
            sum(item.z for item in positions) / len(positions),
        )

    receptor_centre, peptide_centre = centroid(receptor_positions), centroid(peptide_positions)
    centroid_distance = math.sqrt(
        sum((receptor_centre[index] - peptide_centre[index]) ** 2 for index in range(3))
    )

    # Grid the receptor so this stays linear rather than quadratic.
    cell = DOCKED_CONTACT_CUTOFF
    grid: dict[tuple[int, int, int], list] = {}
    for position in receptor_positions:
        key = (int(position.x // cell), int(position.y // cell), int(position.z // cell))
        grid.setdefault(key, []).append(position)

    contact_atoms = 0
    minimum = None
    for position in peptide_positions:
        base = (int(position.x // cell), int(position.y // cell), int(position.z // cell))
        touched = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for other in grid.get((base[0] + dx, base[1] + dy, base[2] + dz), ()):
                        distance = math.sqrt(
                            (position.x - other.x) ** 2
                            + (position.y - other.y) ** 2
                            + (position.z - other.z) ** 2
                        )
                        if minimum is None or distance < minimum:
                            minimum = distance
                        if distance <= DOCKED_CONTACT_CUTOFF:
                            touched = True
        if touched:
            contact_atoms += 1

    return DockingCheck(
        job_id=job["job_id"],
        docked=contact_atoms > 0,
        contact_atoms=contact_atoms,
        min_distance=round(minimum, 2) if minimum is not None else None,
        centroid_distance=round(centroid_distance, 1),
        peptide_atoms=len(peptide_positions),
    )
