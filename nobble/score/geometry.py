"""Geometry against the empirical bridge envelope (spec 4.1, the primary signal).

This is the strongest discriminator in the stack because it compares a
prediction to real interfaces rather than to a model's own confidence. BINMAN's
bridging filter is reused unchanged: it was built with gemmi and FreeSASA for
crystal structures and applies verbatim to a predicted ternary, because the
question it answers is the same one. A molecular glue bridging an E3 and a
substrate is, geometrically, exactly what BINMAN's atlas catalogues: a ligand
burying surface against two different polymer chains at once.

The output is not a pass or fail against a threshold. It is a percentile against
the distribution of 285,996 experimentally observed bridges in the atlas,
reported as `bridge_percentile`.
"""
from __future__ import annotations

import bisect
import sys
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

from nobble import paths
from nobble.curate import binman_store as store
from nobble.curate import constructs as C

# BINMAN's pipeline package is imported rather than copied (D-NOB-007).
if str(paths.BINMAN) not in sys.path:
    sys.path.insert(0, str(paths.BINMAN))

PEPTIDE_CHAIN = "P"
LIGAND_CHAIN = "L"

# Reject reasons that mean the bridge was not measured, as against measured
# and absent. BINMAN's filter returns its own reasons for a real negative
# ("single_chain:1_qualifying_of_1" means the glue buried surface against one
# chain rather than two, which is a finding). These four are assigned here,
# before any geometry runs, and say the input was unusable. The difference
# matters to bridge_formation_rate: counting an unmeasurable seed in the
# denominator reports a prediction that could not be assessed as one that
# failed to bridge.
MEASUREMENT_FAILURES = (
    "structure_missing",
    "binary_complex_has_no_bridge",
    "no_ligand_chain_in_output",
    "no_peptide_chain_in_output",
    # Assigned only by `score_deposition`, which runs the same filter on a
    # deposited assembly rather than a prediction. Both mean the crystal
    # could not be asked the question: a deposition whose glue was never
    # modelled is not a crystal in which the glue fails to bridge.
    "deposition_not_cached",
    "glue_not_modelled_in_deposition",
)


@dataclass
class BridgeScore:
    """Geometry of one predicted ternary, and where it sits against the atlas."""

    job_id: str
    structure: str
    found: bool
    dsasa_receptor: float | None = None
    dsasa_peptide: float | None = None
    dsasa_total: float | None = None
    contacts_receptor: int | None = None
    contacts_peptide: int | None = None
    bridging_balance: float | None = None
    buried_fraction: float | None = None
    heavy_atoms: int | None = None
    bridge_percentile: float | None = None
    percentile_basis: str | None = None
    reject_reason: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@lru_cache(maxsize=1)
def reference_distribution() -> dict[str, tuple[float, ...]]:
    """Sorted dSASA-total and buried-fraction values from the atlas.

    Every `status = 'ok'` bridge, which is the 285,996 spec 4.1 names. The
    filter is `status` and a non-null value and nothing else: no exclusion
    of symmetry-mediated contacts, of the `crystallisation_artefact`
    evidence class, or of furniture ligands. This said "only genuine
    two-chain bridges, so the percentile compares like with like", which
    described a filter that is not here and never was (F150).

    Leaving it unfiltered is right, because the spec names the population by
    its size and that size is the unfiltered one. It also barely matters,
    which was worth measuring rather than assuming. Against four populations,
    all bridges, non-symmetry only, artefacts excluded, and the glue and
    protac classes alone, the median dSASA runs from 767.9 to 805.0 and a
    predicted bridge's percentile moves by one to six points: 1,200 square
    angstroms scores 86.3 against all bridges and 92.7 against glue
    interfaces alone. So the primary signal is not an artefact of which
    bridges are counted.

    What it does change is the sentence a reader should attach to a high
    percentile. It means "a larger interface than most bridges the atlas has
    observed", incidental ones included, not "larger than most molecular
    glue interfaces". Those happen to be nearly the same claim here, and
    they are not the same claim.

    Held sorted so a percentile is a bisection rather than a scan.
    """
    rows = store.atlas_rows(
        "select dsasa_total, buried_fraction, bridging_balance from bridge "
        "where status = 'ok' and dsasa_total is not null"
    )
    return {
        "dsasa_total": tuple(sorted(row["dsasa_total"] for row in rows)),
        "buried_fraction": tuple(
            sorted(row["buried_fraction"] for row in rows if row["buried_fraction"] is not None)
        ),
        "bridging_balance": tuple(
            sorted(row["bridging_balance"] for row in rows if row["bridging_balance"] is not None)
        ),
    }


def percentile_of(value: float, key: str = "dsasa_total") -> float:
    """Percentile of a value against the atlas distribution, 0 to 100."""
    reference = reference_distribution()[key]
    if not reference:
        return float("nan")
    position = bisect.bisect_left(reference, value)
    return round(100.0 * position / len(reference), 2)


def _atom_groups(structure_path: Path, construct_name: str):
    """Build BINMAN AtomGroups for the receptor, the peptide and the ligand.

    Receptor segments are merged into one group: spec 4.1 asks for dSASA against
    "both chains", meaning the two sides of the bridge, and for a multi-segment
    receptor such as the VCB trimer the relevant side is the receptor as a whole
    rather than each of its chains separately.
    """
    import gemmi

    from pipeline.geometry import AtomGroup  # noqa: PLC0415

    structure = gemmi.read_structure(str(structure_path))
    structure.setup_entities()
    structure.remove_hydrogens()

    receptor_chain_ids = set("ABCDEFGH"[: len(C.by_name(construct_name).segments)])
    receptor = AtomGroup(label="receptor")
    peptide = AtomGroup(label="peptide")
    ligand = AtomGroup(label="ligand")

    for chain in structure[0]:
        if chain.name in receptor_chain_ids:
            target = receptor
        elif chain.name == PEPTIDE_CHAIN:
            target = peptide
        elif chain.name == LIGAND_CHAIN:
            target = ligand
        else:
            continue
        for residue in chain:
            key = f"{residue.name} {residue.seqid.num}"
            for atom in residue:
                if atom.element.name == "H":
                    continue
                target.add(
                    atom.pos.x, atom.pos.y, atom.pos.z,
                    atom.element.name, key, atom.name,
                )
    return receptor, peptide, ligand


def score_structure(job: dict) -> BridgeScore:
    """Run BINMAN's bridging filter on one predicted ternary."""
    structure_path = job.get("structure")
    result = BridgeScore(
        job_id=job["job_id"], structure=str(structure_path), found=False
    )
    if not structure_path or not Path(structure_path).exists():
        result.reject_reason = "structure_missing"
        return result
    if job.get("complex_type") != "ternary":
        result.reject_reason = "binary_complex_has_no_bridge"
        result.notes.append(
            "a binary complex has no ligand, so there is no bridge to measure: "
            "geometry for the binary arm is the peptide-receptor interface, "
            "reported separately"
        )
        return result

    receptor, peptide, ligand = _atom_groups(Path(structure_path), job["construct"])
    return bridge_from_groups(
        job_id=job["job_id"], source=str(structure_path), receptor=receptor,
        partner=peptide, ligand=ligand,
        ligand_key=job.get("ligand_key") or "LIG",
    )


def bridge_from_groups(
    *, job_id: str, source: str, receptor, partner, ligand, ligand_key: str,
) -> BridgeScore:
    """Run BINMAN's bridging filter on three prepared atom groups.

    The only place the filter is called. `score_structure` supplies groups
    read out of a predicted mmCIF and `score_deposition` supplies them out of
    a deposited assembly, and both reach `find_bridges` through this one call
    with the same glue waiver and the same percentile basis. A crystal control
    routed through a second spelling of this would be testing that spelling
    rather than the detector the campaign ran (F154).
    """
    from pipeline.geometry import SasaCalculator, find_bridges  # noqa: PLC0415

    result = BridgeScore(job_id=job_id, structure=source, found=False)
    if len(ligand) == 0:
        result.reject_reason = "no_ligand_chain_in_output"
        return result
    if len(partner) == 0:
        result.reject_reason = "no_peptide_chain_in_output"
        return result

    bridges, halves, reject = find_bridges(
        ligand,
        ligand_key,
        [
            ("receptor", "receptor", receptor, False),
            (PEPTIDE_CHAIN, "peptide", partner, False),
        ],
        sasa=SasaCalculator(),
        # The ligand is a known glue or degrader by construction, so the atlas's
        # size floor for unknown heteroatoms is waived: spec 2.1 lists these
        # compounds as curated glue chemistry, not as incidental heteroatoms.
        is_glue_candidate=True,
    )

    if not bridges:
        result.reject_reason = reject or "no_bridge_found"
        if halves:
            best = max(halves, key=lambda item: item.dsasa)
            result.notes.append(
                f"best single half-interface: {best.chain_label} dSASA "
                f"{best.dsasa:.1f} A^2 with {best.contacts} contacts, below the "
                "bridging criteria"
            )
        return result

    bridge = max(bridges, key=lambda item: item.dsasa_total)
    receptor_first = bridge.chain_a == "receptor"
    result.found = True
    result.dsasa_receptor = bridge.dsasa_a if receptor_first else bridge.dsasa_b
    result.dsasa_peptide = bridge.dsasa_b if receptor_first else bridge.dsasa_a
    result.dsasa_total = bridge.dsasa_total
    result.contacts_receptor = bridge.contacts_a if receptor_first else bridge.contacts_b
    result.contacts_peptide = bridge.contacts_b if receptor_first else bridge.contacts_a
    result.bridging_balance = bridge.bridging_balance
    result.buried_fraction = bridge.buried_fraction
    result.heavy_atoms = bridge.heavy_atoms
    result.bridge_percentile = percentile_of(bridge.dsasa_total, "dsasa_total")
    result.percentile_basis = (
        f"dsasa_total against {len(reference_distribution()['dsasa_total'])} "
        "experimentally observed bridges in BINMAN's atlas"
    )
    return result


def groups_from_deposition(
    pdb_id: str, receptor_chain: str | None, substrate_chain: str,
    ligand_ccd: str, ligand_seqid: int | None = None,
):
    """Atom groups for the two sides of a deposited bridge and its glue.

    The deposited counterpart of `_atom_groups`. A prediction writes the
    receptor as chains A onwards, the substrate as P and the glue as L, so
    that function can read the roles off the chain names; a deposition names
    its chains however the depositors did, and the glue is a heteroatom
    residue inside one of the protein chains rather than a chain of its own.
    The roles therefore come from the caller, which is why
    `nobble/validate/layers.py` already records a receptor and a substrate
    chain per benchmark deposition.

    Only the two named chains are read. An assembly often carries more (DDB1
    beside CRBN, ElonginB and ElonginC beside VHL), and the question here is
    whether the glue bridges the two chains the campaign's prediction joins,
    not whether it buries surface against the crystal as a whole. Widening
    the receptor side to every other protein chain is a different measurement
    and `tools/bridge_on_crystals.py --whole-assembly` makes it.
    """
    import gemmi

    from pipeline.geometry import AtomGroup  # noqa: PLC0415

    from nobble.curate import structures  # noqa: PLC0415

    structure = structures.read_assembly(pdb_id)
    receptor = AtomGroup(label="receptor")
    substrate = AtomGroup(label="peptide")
    ligand = AtomGroup(label="ligand")

    for chain in structure[0]:
        for residue in chain:
            if residue.name == ligand_ccd and (
                    ligand_seqid is None or residue.seqid.num == ligand_seqid):
                target = ligand
            elif not structures.is_amino_acid(residue):
                continue
            elif chain.name == substrate_chain:
                target = substrate
            elif receptor_chain is None or chain.name == receptor_chain:
                # None means every protein chain that is not the substrate,
                # which is the --whole-assembly reading.
                target = receptor
            else:
                continue
            key = f"{residue.name} {residue.seqid.num}"
            for atom in residue:
                if atom.element == gemmi.Element("H"):
                    continue
                target.add(atom.pos.x, atom.pos.y, atom.pos.z,
                           atom.element.name, key, atom.name)
    return receptor, substrate, ligand


def score_deposition(
    pdb_id: str, receptor_chain: str | None, substrate_chain: str,
    ligand_ccd: str | None, ligand_seqid: int | None = None,
) -> BridgeScore:
    """The bridging filter on a deposited ternary, as a positive control.

    `tests/test_geometry_real_bridge.py` exercises the filter's success path
    on a prediction the campaign itself scored as bridging, which is a
    regression test: it asks whether the filter still agrees with its own
    earlier verdict. It cannot say whether the filter is right, because the
    label it checks against came from the filter.

    This asks the independent question. Every benchmark deposition is a glue
    or degrader ternary by the terms of its own title, so the glue bridges
    the two proteins as a matter of experimental record, and a deposition the
    filter does not call bridging is a false negative of the instrument. The
    numbers come back on the same scale as a prediction's, through the same
    `bridge_from_groups`, so the crystal's dSASA and percentile are directly
    comparable with the campaign's.

    A deposition whose glue was never modelled is refused rather than scored.
    6BNB is titled "DDB1-CRBN-BRD4(BD1) complex bound to dBET57 PROTAC" and
    its coordinates contain no dBET57: the only heteroatom in the assembly is
    a zinc. That is a missing measurement, not a crystal in which a PROTAC
    fails to bridge, and the two must not land in the same count (F293).
    """
    from nobble.curate import structures  # noqa: PLC0415

    job_id = f"{pdb_id}:{receptor_chain or 'every-other-chain'}+{substrate_chain}"
    if not structures.is_cached(pdb_id):
        result = BridgeScore(job_id=job_id, structure=str(
            structures.assembly_path(pdb_id)), found=False)
        result.reject_reason = "deposition_not_cached"
        return result

    source = str(structures.assembly_path(pdb_id))
    if not ligand_ccd:
        result = BridgeScore(job_id=job_id, structure=source, found=False)
        result.reject_reason = "glue_not_modelled_in_deposition"
        result.notes.append(
            f"{pdb_id} carries no heteroatom large enough to be a glue, so "
            "there is no bridge in the coordinates to find")
        return result

    receptor, substrate, ligand = groups_from_deposition(
        pdb_id, receptor_chain, substrate_chain, ligand_ccd, ligand_seqid)
    if len(ligand) == 0:
        result = BridgeScore(job_id=job_id, structure=source, found=False)
        result.reject_reason = "glue_not_modelled_in_deposition"
        result.notes.append(
            f"{ligand_ccd} is named for {pdb_id} but no residue of that name "
            "is in the assembly")
        return result

    result = bridge_from_groups(
        job_id=job_id, source=source, receptor=receptor, partner=substrate,
        ligand=ligand, ligand_key=ligand_ccd)
    result.notes.append(
        f"deposited: {ligand_ccd} against {pdb_id} chain {receptor_chain} "
        f"(receptor) and chain {substrate_chain} (substrate)")
    return result


# Heavy-atom cutoff for a residue-residue contact. 4.5 angstrom is the usual
# convention for a packing contact: close enough to be an interaction, loose
# enough to include a water-mediated approach that the prediction has no water
# for.
CONTACT_CUTOFF = float(paths.thresholds()["geometry"]["contact_cutoff_a"])


def contact_map(job: dict) -> dict:
    """Peptide residue against receptor residue, as spec Phase 4 asks for.

    PLIP answers a different question. It is a protein-ligand tool, so it
    reports glue-to-receptor and glue-to-peptide contacts and has nothing to
    say about where the peptide touches the receptor, which is the interface
    Delta-ipTM is about. That map is computed here from the predicted
    structure instead, and the PLIP types are layered on separately where they
    overlap.

    Computed at scoring time, not in the application: the droplet serves a
    precomputed slice and does no geometry at request time.
    """
    import gemmi

    from nobble.curate import constructs as C

    structure_path = job.get("structure")
    result = {
        "job_id": job.get("job_id"),
        "cutoff": CONTACT_CUTOFF,
        "receptor_residues": [],
        "peptide_residues": [],
        "contacts": [],
        "status": "pending",
    }
    if not structure_path or not Path(structure_path).exists():
        result["status"] = "no_structure"
        return result

    structure = gemmi.read_structure(str(structure_path))
    structure.setup_entities()
    structure.remove_hydrogens()

    construct = C.by_name_or_none(job.get("construct"))
    if construct is None:
        result["status"] = "unknown_construct"
        return result
    receptor_ids = set("ABCDEFGH"[: len(construct.segments)])

    receptor, peptide = [], []
    for chain in structure[0]:
        target = (receptor if chain.name in receptor_ids
                  else peptide if chain.name == "P" else None)
        if target is None:
            continue
        for residue in chain:
            atoms = [atom.pos for atom in residue if atom.element.name != "H"]
            if atoms:
                target.append((f"{residue.name}{residue.seqid.num}", atoms))

    if not receptor or not peptide:
        result["status"] = "missing_chain"
        return result

    # Grid the receptor so this stays linear rather than quadratic over a
    # 1,184-residue construct.
    cell = CONTACT_CUTOFF
    grid: dict[tuple, list] = {}
    for index, (_label, atoms) in enumerate(receptor):
        for position in atoms:
            key = (int(position.x // cell), int(position.y // cell), int(position.z // cell))
            grid.setdefault(key, []).append((index, position))

    pairs: dict[tuple[int, int], float] = {}
    for peptide_index, (_label, atoms) in enumerate(peptide):
        for position in atoms:
            base = (int(position.x // cell), int(position.y // cell), int(position.z // cell))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for receptor_index, other in grid.get(
                            (base[0] + dx, base[1] + dy, base[2] + dz), ()
                        ):
                            distance = position.dist(other)
                            if distance > CONTACT_CUTOFF:
                                continue
                            key = (peptide_index, receptor_index)
                            if key not in pairs or distance < pairs[key]:
                                pairs[key] = distance

    # Only the receptor residues that touch anything: a 1,184-residue axis of
    # which four are in contact is not a readable map.
    touched = sorted({receptor_index for _p, receptor_index in pairs})
    receptor_index_of = {old: new for new, old in enumerate(touched)}

    result["receptor_residues"] = [receptor[index][0] for index in touched]
    result["peptide_residues"] = [label for label, _atoms in peptide]
    result["contacts"] = [
        {
            "peptide": peptide_index,
            "receptor": receptor_index_of[receptor_index],
            "distance": round(distance, 2),
        }
        for (peptide_index, receptor_index), distance in sorted(pairs.items())
    ]
    result["status"] = "ok"
    result["contact_count"] = len(result["contacts"])
    return result
