"""Phase 1 gate: does BINMAN's Degron Scan independently recover the two
reference degrons from structure, with no hardcoded residue range?

Spec 3.1 makes this a blocker: "If the Degron Scan does not recover the GSPT1
domain II hairpin independently, that is a Phase 1 blocker and a bug in the
scan, not a reason to hardcode."

The test takes no residue number as input. For each reference pair it:

1. measures which substrate residues contact the glue in the deposited ternary;
2. picks the contacting residue the degron is defined by (the most buried
   glycine, since both reference degrons are glycine degrons);
3. converts that deposited residue into canonical numbering via
   nobble.curate.numbering, which is the step that makes the comparison valid;
4. asks whether any degron the scan reported for that protein spans it.

Step 3 is the whole reason this file is more than three lines: run without it,
the GSPT1 check fails on a correct scan. See nobble/curate/numbering.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from nobble.curate import binman_store as store
from nobble.curate import numbering, structures
from nobble import paths

CONTACT_CUTOFF = float(paths.thresholds()["geometry"]["degron_scan_contact_cutoff_a"])


@dataclass
class ReferenceDegron:
    """A degron whose location is read out of a deposited ternary, not declared."""

    label: str
    pdb_id: str
    substrate_acc: str
    substrate_chain: str
    ligand_ccd: str
    description: str


# The two the spec names. Chains and ligand CCDs come from the resolver and the
# deposited assembly; no residue number appears here.
REFERENCES = (
    ReferenceDegron(
        "GSPT1 domain II hairpin", "5HXB", "P15170", "X", "85C",
        "Glycine-tipped beta-hairpin in GSPT1 domain II, engaged by CC-885",
    ),
    ReferenceDegron(
        "IKZF1 ZF2", "6H0F", "Q13422", "C", "Y70",
        "IKZF1 zinc finger 2 degron, engaged by an IMiD in the CRBN tri-tryptophan pocket",
    ),
)


@dataclass
class GateResult:
    reference: ReferenceDegron
    contact_residues_deposited: list[int] = field(default_factory=list)
    degron_residue_deposited: int | None = None
    degron_residue_canonical: int | None = None
    degron_amino_acid: str | None = None
    frame_offset: int | None = None
    scan_degrons: list[dict] = field(default_factory=list)
    matched_degron: dict | None = None
    recovered: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "label": self.reference.label,
            "pdb_id": self.reference.pdb_id,
            "accession": self.reference.substrate_acc,
            "contact_residues_deposited": self.contact_residues_deposited,
            "degron_residue_deposited": self.degron_residue_deposited,
            "degron_residue_canonical": self.degron_residue_canonical,
            "degron_amino_acid": self.degron_amino_acid,
            "frame_offset": self.frame_offset,
            "scan_degron_count": len(self.scan_degrons),
            "matched_degron": self.matched_degron,
            "recovered": self.recovered,
            "notes": self.notes,
        }


def _scan_degrons(accession: str) -> list[dict]:
    """Degrons BINMAN's scan reported for this protein, canonical numbering."""
    return store.atlas_rows(
        "select start_res, end_res, tip_res, tip_aa, turn_length, mean_plddt, "
        "       tip_rel_sasa, degron_geometry_score, motif_family, is_known_neosubstrate "
        "from degron where uniprot_acc = ? and status = 'ok' "
        "order by degron_geometry_score desc",
        (accession,),
    )


def check(reference: ReferenceDegron) -> GateResult:
    result = GateResult(reference=reference)

    contacts = structures.contacts_to_ligand(
        reference.pdb_id, reference.ligand_ccd, reference.substrate_chain, CONTACT_CUTOFF
    )
    if not contacts:
        result.notes.append(
            f"no {reference.ligand_ccd} contacts on chain {reference.substrate_chain} "
            f"within {CONTACT_CUTOFF} A"
        )
        return result
    result.contact_residues_deposited = sorted(item["seqid"] for item in contacts)

    # Both reference degrons are glycine degrons: the defining residue is the
    # glycine that packs closest to the glue. Falling back to the closest
    # contact at all keeps the test meaningful for a non-glycine degron class.
    glycines = [item for item in contacts if item["one_letter"] == "G"]
    chosen = (glycines or contacts)[0]
    if not glycines:
        result.notes.append("no glycine among the glue contacts: used the closest contact")
    result.degron_residue_deposited = chosen["seqid"]
    result.degron_amino_acid = chosen["one_letter"]

    try:
        frame = numbering.resolve_frame(
            reference.pdb_id, reference.substrate_chain, reference.substrate_acc
        )
    except numbering.FrameUnresolved as error:
        result.notes.append(f"numbering frame unresolved: {error}")
        return result

    result.frame_offset = frame.offset
    result.degron_residue_canonical = frame.to_canonical(chosen["seqid"])
    if frame.offset:
        result.notes.append(
            f"deposited numbering runs {frame.offset} ahead of canonical "
            f"{reference.substrate_acc}: deposited {chosen['seqid']} is canonical "
            f"{result.degron_residue_canonical}. Comparing the frames directly would "
            "report a false miss."
        )

    result.scan_degrons = _scan_degrons(reference.substrate_acc)
    target = result.degron_residue_canonical
    for degron in result.scan_degrons:
        if degron["start_res"] <= target <= degron["end_res"]:
            result.matched_degron = degron
            result.recovered = True
            if degron["tip_res"] == target:
                result.notes.append(
                    f"scan tip residue is exactly the deposited degron residue "
                    f"({target}{result.degron_amino_acid})"
                )
            else:
                result.notes.append(
                    f"deposited degron residue {target} lies inside scan degron "
                    f"{degron['start_res']}-{degron['end_res']} (tip {degron['tip_res']})"
                )
            break
    if not result.recovered:
        result.notes.append(
            f"no reported degron spans canonical residue {target}: this is a scan bug "
            "per spec 3.1, not a reason to hardcode"
        )
    return result


def run() -> dict:
    results = [check(reference) for reference in REFERENCES]
    return {
        "references": [item.to_dict() for item in results],
        "recovered": sum(1 for item in results if item.recovered),
        "total": len(results),
        "passes": all(item.recovered for item in results),
    }
