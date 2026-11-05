"""Boltz YAML generation (spec Phase 2).

Widens what BoltzMaker's generator emits, in the ways spec Phase 2 lists: a
ligand chain by CCD code, pocket and contact constraints, a `modifications`
block for HYP/SEP/TPO, an affinity block scoped to the ligand chain, and paired
binary/ternary emission.

Chain identifiers are assigned once and used consistently: receptor segments take
A, B, C in construct order, the peptide takes P and the ligand takes L. Pocket
constraints refer to receptor residues by their position **within the
construct**, which is not the canonical residue number and not the deposited
one. The three frames are related by:

    construct position = canonical residue - segment start + 1
    canonical residue  = deposited residue - frame offset

Both conversions are applied explicitly. Getting this wrong would condition the
ligand onto the wrong pocket while still producing a plausible-looking structure,
which is exactly the failure mode spec 4.7's conditioning-disagreement flag
exists to catch.
"""
from __future__ import annotations

from dataclasses import dataclass

from nobble import paths
from nobble.curate import constructs as C
from nobble.curate import numbering, structures
from nobble.curate import peptides as P
from nobble.execute import msa as msa_module

PEPTIDE_CHAIN = "P"
LIGAND_CHAIN = "L"
# A structural metal that belongs to the peptide, not to the glue mechanism.
COFACTOR_CHAIN = "Z"
RECEPTOR_CHAINS = "ABCDEFGH"
POCKET_MAX_DISTANCE = float(paths.thresholds()["geometry"]["pocket_max_distance_a"])
# Which receptor residues are listed as lining the pocket, as opposed to how
# far the ligand may sit from them. Was a bare 5.0 at the call site.
POCKET_CONTACT_CUTOFF = float(
    paths.thresholds()["geometry"]["pocket_contact_cutoff_a"]
)

# Which chains of each benchmark deposition hold the receptor, so the pocket can
# be measured rather than asserted. Read off the deposited assemblies.
RECEPTOR_CHAINS_BY_PDB = {
    "5HXB": {"CRBN": ("Z", "Q96SW2")},
    "5T35": {"VHL": ("D", "P40337")},
    "6BNB": {"CRBN": ("B", "Q96SW2")},
    "6H0F": {"CRBN": ("B", "Q96SW2")},
    "5FQD": {"CRBN": ("B", "Q96SW2")},
    "6Q0W": {"DCAF15": ("B", "Q66K64"), "DDB1": ("A", "Q16531")},
    "6TD3": {"DDB1": ("A", "Q16531")},
}


@dataclass
class PocketConstraint:
    chain: str
    positions: list[int]
    max_distance: float
    provenance: str

    def to_yaml_fragment(self) -> dict:
        return {
            "pocket": {
                "binder": LIGAND_CHAIN,
                "contacts": [[self.chain, position] for position in self.positions],
                "max_distance": self.max_distance,
            }
        }


def _segment_positions(construct: C.Construct) -> list[tuple[str, str, int, int]]:
    """(chain_id, accession, segment_start, segment_end) per receptor segment."""
    assigned = []
    for index, segment in enumerate(construct.segments):
        start, end = segment.range()
        assigned.append((RECEPTOR_CHAINS[index], segment.accession, start, end))
    return assigned


def derive_pocket(
    construct: C.Construct, pdb_id: str, ligand_ccd: str, e3_gene: str
) -> PocketConstraint | None:
    """Measure the glue pocket on the deposited receptor, mapped into the construct.

    Returns None when the pocket cannot be measured, in which case the job runs
    unconstrained only. An unmeasurable pocket is not a reason to guess one.
    """
    mapping = RECEPTOR_CHAINS_BY_PDB.get(pdb_id.upper(), {}).get(e3_gene)
    if not mapping or not ligand_ccd:
        return None
    chain, accession = mapping

    contacts = structures.contacts_to_ligand(
        pdb_id, ligand_ccd, chain, cutoff=POCKET_CONTACT_CUTOFF
    )
    if not contacts:
        return None
    try:
        frame = numbering.resolve_frame(pdb_id, chain, accession)
    except numbering.FrameUnresolved:
        return None

    positions: list[int] = []
    for chain_id, segment_accession, start, end in _segment_positions(construct):
        if segment_accession != accession:
            continue
        for contact in contacts:
            canonical_residue = frame.to_canonical(contact["seqid"])
            if start <= canonical_residue <= end:
                positions.append(canonical_residue - start + 1)
        if positions:
            return PocketConstraint(
                chain=chain_id,
                positions=sorted(set(positions)),
                max_distance=POCKET_MAX_DISTANCE,
                provenance=(
                    f"measured on {pdb_id} chain {chain} within 5 A of {ligand_ccd}; "
                    f"deposited numbering mapped to canonical via offset "
                    f"{frame.offset} then to construct positions via segment "
                    f"start {start}"
                ),
            )
    return None


def peptide_modifications(peptide) -> list[dict]:
    """The `modifications` block for a degron class that requires a PTM (spec 2.3).

    Positions are 1-based within the peptide chain, which is what Boltz expects.
    Every eligible residue of the required type is modified: a DSGxxS motif has
    two serines and phosphorylating one of them is not the degron.
    """
    requirement = peptide.required_modification
    if not requirement:
        return []
    # SEP/TPO is a choice keyed on the residue, so resolve per position.
    resolved = []
    for index, residue in enumerate(peptide.sequence, start=1):
        if residue not in requirement["residue"]:
            continue
        ccd = requirement["ccd"]
        if ccd == "SEP/TPO":
            ccd = "SEP" if residue == "S" else "TPO"
        resolved.append({"position": index, "ccd": ccd})
    return resolved


def build_yaml(job, peptide, ligand, pocket: PocketConstraint | None) -> dict:
    """The YAML document for one job, as a plain dict."""
    construct = C.by_name(job.construct)
    sequences: list[dict] = []

    for chain_id, _accession, _start, _end in _segment_positions(construct):
        index = RECEPTOR_CHAINS.index(chain_id)
        segment = construct.segments[index]
        sequence = segment.sequence()
        entry = {"id": chain_id, "sequence": sequence}
        # Spec 1.3: the cached file, never a server call.
        entry["msa"] = (
            str(msa_module.a3m_path(sequence))
            if msa_module.is_cached(sequence)
            else msa_module.EMPTY
        )
        sequences.append({"protein": entry})

    peptide_entry = {
        "id": PEPTIDE_CHAIN,
        "sequence": peptide.sequence,
        # Peptide chains get no MSA (spec 1.3).
        "msa": msa_module.EMPTY,
    }
    modifications = peptide_modifications(peptide)
    if modifications:
        peptide_entry["modifications"] = modifications
    sequences.append({"protein": peptide_entry})

    # A C2H2 zinc finger needs its ion in BOTH arms or neither. Delta-ipTM is
    # the ternary ipTM minus the binary one, so a cofactor present in only the
    # ternary arm would fold the peptide differently between them and the
    # difference would report "the glue changed the interface" for what was
    # really "the peptide folded this time". Same class of error as mixing
    # sampling tiers into one minimum (D-NOB-032), one level up.
    zinc = P.requires_structural_zinc(peptide)
    if zinc["required"]:
        sequences.append({"ligand": {"id": COFACTOR_CHAIN, "ccd": zinc["ccd"]}})

    document: dict = {"version": 1, "sequences": sequences}

    if job.complex_type == "ternary" and ligand is not None:
        ligand_entry: dict = {"id": LIGAND_CHAIN}
        if ligand.encoding == "ccd":
            ligand_entry["ccd"] = ligand.ccd
        else:
            ligand_entry["smiles"] = ligand.smiles
        sequences.append({"ligand": ligand_entry})

        if job.conditioning == "conditioned" and pocket is not None:
            document["constraints"] = [pocket.to_yaml_fragment()]

        # Spec 4.7 and D-NOB-005: affinity is recorded for the small-molecule
        # chain only, and never for a peptide. Requested only when the ligand is
        # inside the heavy-atom cap.
        if ligand.affinity_available:
            document["properties"] = [{"affinity": {"binder": LIGAND_CHAIN}}]

    return document


def to_yaml_text(document: dict) -> str:
    """Serialise without a YAML dependency in the curation environment."""
    import yaml

    return yaml.safe_dump(document, sort_keys=False, default_flow_style=False)
