"""Benchmark panel resolver (spec 3.1).

The seven panel members are declared by UniProt accession and ligand name only.
Every PDB identifier, chain identifier and receptor stoichiometry is resolved
from the curated data at build time, because hardcoded accessions rot and are a
known source of silent error (spec 3.1).

Two findings from the real data shape this module, both recorded as D-NOB-009:

1. MGTbind encodes multi-protein receptors as underscore-joined composite
   accessions (DDB1_CRBN, ELOB_ELOC_VHL, DDB1_DCAF15_DDA1). Matching accessions
   by equality returns nothing for any panel member whose receptor is a complex,
   so matching is by token set membership. This also recovers the VCB and DCAF15
   stoichiometry exceptions of spec 1.1 from the deposited structures rather
   than by assertion.
2. MGTbind is a glue database and carries no PROTACs at all, so the two BRD4
   bivalent arms resolve from PROTAC-DB, which spec 2.1 names as the bivalent
   source and which carries PDB identifiers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

from nobble.curate import binman_store as store

ACCESSION = re.compile(r"[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}")


@dataclass(frozen=True)
class PanelMember:
    """A declared benchmark pair, before resolution."""

    index: int
    substrate_gene: str
    substrate_acc: str
    substrate_region: str
    e3_gene: str
    e3_acc: str
    ligand: str
    modality: str
    role: str
    source: str  # "mgtbind" for glues, "protacdb" for bivalents


@dataclass
class ResolvedMember:
    """A panel member resolved against deposited structures."""

    member: PanelMember
    pdb_ids: list[str] = field(default_factory=list)
    preferred_pdb: str | None = None
    receptor_components: list[str] = field(default_factory=list)
    receptor_chains: list[str] = field(default_factory=list)
    substrate_chains: list[str] = field(default_factory=list)
    ligand_resolved: str | None = None
    candidate_count: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def resolved(self) -> bool:
        return self.preferred_pdb is not None

    def to_dict(self) -> dict:
        record = asdict(self)
        record["member"] = asdict(self.member)
        record["resolved"] = self.resolved
        return record


# Spec 3.1, table of seven. Accessions are the substrate and E3 identities, which
# are facts about the proteins rather than about any one deposition.
PANEL: tuple[PanelMember, ...] = (
    PanelMember(
        1, "GSPT1", "P15170", "G-loop beta-hairpin, domain II", "CRBN", "Q96SW2",
        "CC-885", "glue",
        "Canonical glycine-degron glue benchmark. The highest-value single test in the panel",
        "mgtbind",
    ),
    PanelMember(
        2, "BRD4", "O60885", "BD2", "VHL", "P40337",
        "MZ1", "protac",
        "Canonical bivalent ternary benchmark. Tests that the pipeline handles a "
        "linked degrader correctly rather than treating it as a glue",
        "protacdb",
    ),
    PanelMember(
        3, "BRD4", "O60885", "BD1", "CRBN", "Q96SW2",
        "dBET", "protac",
        "Second BRD4 arm, different E3, tests E3 swap on the same substrate",
        "protacdb",
    ),
    PanelMember(
        4, "IKZF1", "Q13422", "ZF2", "CRBN", "Q96SW2",
        "lenalidomide", "glue",
        "Founding IMiD neosubstrate observation",
        "mgtbind",
    ),
    PanelMember(
        5, "CSNK1A1", "P48729", "kinase domain", "CRBN", "Q96SW2",
        "lenalidomide", "glue",
        "Same glue, different neosubstrate: tests specificity, not just recall",
        "mgtbind",
    ),
    PanelMember(
        6, "RBM39", "Q14498", "RRM2", "DCAF15", "Q66K64",
        "indisulam", "glue",
        "Aryl sulfonamide arm, exercises the DCAF15 token exception",
        "mgtbind",
    ),
    PanelMember(
        7, "CCNK", "O75909", "full", "DDB1", "Q16531",
        "CR-8", "glue",
        "Glue acting without a substrate receptor at all",
        "mgtbind",
    ),
)

# Ligand name synonyms seen in the curated sources. Resolution prefers an exact
# spec-named match and falls back to any deposited ternary for the pair, which is
# logged as a note rather than silently accepted.
LIGAND_SYNONYMS = {
    "CC-885": ("cc-885", "cc885"),
    "MZ1": ("mz1",),
    "dBET": ("dbet6", "dbet57", "dbet23", "dbet55", "dbet70", "dbet1", "dbet"),
    "lenalidomide": ("lenalidomide", "s-lenalidomide", "r-lenalidomide"),
    "indisulam": ("indisulam", "e7070"),
    "CR-8": ("cr-8", "cr8"),
}


def _accession_tokens(value: str | None) -> set[str]:
    """Split a possibly composite MGTbind accession into its UniProt tokens."""
    if not value:
        return set()
    return {token for token in str(value).split("_") if token}


def _name_tokens(value: str | None) -> list[str]:
    if not value:
        return []
    return [token for token in str(value).split("_") if token]


def _ligand_matches(name: str | None, target: str) -> bool:
    if not name:
        return False
    lowered = str(name).strip().lower()
    for synonym in LIGAND_SYNONYMS.get(target, (target.lower(),)):
        if synonym in lowered:
            return True
    return False


def _resolve_from_mgtbind(member: PanelMember) -> ResolvedMember:
    complexes = store.dataset("mgtbind_complexes")
    compounds = {row["id"]: row for row in store.dataset("mgtbind_compounds_raw")}
    result = ResolvedMember(member=member)

    candidates = []
    for row in complexes:
        tokens = _accession_tokens(row.get("protein_a_uniprot_id")) | _accession_tokens(
            row.get("protein_b_uniprot_id")
        )
        if member.substrate_acc in tokens and member.e3_acc in tokens:
            candidates.append(row)
    result.candidate_count = len(candidates)

    deposited = [row for row in candidates if (row.get("pdb_id") or "").strip()]
    if not deposited:
        result.notes.append(
            f"{len(candidates)} curated complexes for the pair, none with a deposited structure"
        )
        return result

    # Prefer a deposition carrying the spec-named ligand.
    named = [
        row for row in deposited
        if _ligand_matches((compounds.get(row.get("compound_id")) or {}).get("name"), member.ligand)
    ]
    chosen_pool = named or deposited
    if not named:
        result.notes.append(
            f"no deposition carries {member.ligand}; resolved against the pair's other ternaries"
        )

    result.pdb_ids = sorted({row["pdb_id"].strip().upper() for row in chosen_pool})
    chosen = sorted(chosen_pool, key=lambda row: row["pdb_id"])[0]
    result.preferred_pdb = chosen["pdb_id"].strip().upper()
    result.ligand_resolved = (compounds.get(chosen.get("compound_id")) or {}).get("name")

    # Which side of the row is the E3 receptor, and which the substrate.
    a_tokens = _accession_tokens(chosen.get("protein_a_uniprot_id"))
    if member.e3_acc in a_tokens:
        e3_side, substrate_side = "a", "b"
    else:
        e3_side, substrate_side = "b", "a"

    result.receptor_components = _name_tokens(chosen.get(f"protein_{e3_side}_name"))
    result.receptor_chains = _name_tokens(chosen.get(f"protein_{e3_side}_chain_id"))
    result.substrate_chains = _name_tokens(chosen.get(f"protein_{substrate_side}_chain_id"))

    if len(result.receptor_components) > 1:
        result.notes.append(
            "receptor is a complex in the deposited structure: "
            + "+".join(result.receptor_components)
        )
    return result


def _resolve_from_protacdb(member: PanelMember) -> ResolvedMember:
    protacs = store.dataset("protacdb_protacs")
    result = ResolvedMember(member=member)

    candidates = [
        row for row in protacs
        if member.substrate_acc in _accession_tokens(row.get("target_uniprot"))
        and member.e3_gene.upper() in str(row.get("e3_ligase", "")).upper()
    ]
    result.candidate_count = len(candidates)

    deposited = [
        row for row in candidates
        if (row.get("pdb_id") or "").strip() or (row.get("pdb_ids") or "").strip()
    ]
    named = [row for row in deposited if _ligand_matches(row.get("name"), member.ligand)]
    chosen_pool = named or deposited
    if not chosen_pool:
        result.notes.append(
            f"{len(candidates)} PROTAC-DB rows for the pair, none with a deposited structure"
        )
        return result
    if not named:
        result.notes.append(
            f"no PROTAC-DB row names {member.ligand}; resolved against the pair's other ternaries"
        )

    identifiers: set[str] = set()
    for row in chosen_pool:
        for field_name in ("pdb_id", "pdb_ids"):
            for token in str(row.get(field_name) or "").replace(";", ",").split(","):
                token = token.strip().upper()
                if len(token) == 4:
                    identifiers.add(token)
    result.pdb_ids = sorted(identifiers)
    if not result.pdb_ids:
        result.notes.append("PROTAC-DB rows carried no parsable four-character PDB identifier")
        return result

    # Prefer a row whose stated region matches the declared one (BD1 against BD2).
    region = member.substrate_region.upper()
    region_rows = [row for row in chosen_pool if region in str(row.get("target", "")).upper()]
    preferred_rows = region_rows or chosen_pool
    if region_rows:
        result.notes.append(f"deposition selected on the declared {member.substrate_region} region")

    for row in sorted(preferred_rows, key=lambda r: str(r.get("name") or "")):
        for field_name in ("pdb_id", "pdb_ids"):
            token = str(row.get(field_name) or "").split(",")[0].strip().upper()
            if len(token) == 4:
                result.preferred_pdb = token
                result.ligand_resolved = row.get("name")
                break
        if result.preferred_pdb:
            break

    # PROTAC-DB does not record chains or stoichiometry: spec 1.1 fixes the VHL
    # receptor as the VCB trimer regardless, and chains come from the mmCIF when
    # the structure is fetched in Phase 3.
    if member.e3_gene == "VHL":
        result.receptor_components = ["VHL", "ELOB", "ELOC"]
        result.notes.append(
            "VHL receptor is the VCB trimer by spec 1.1: VHL does not fold in isolation"
        )
    else:
        result.receptor_components = [member.e3_gene]
    result.notes.append("chains resolved from the mmCIF at structure-fetch time, not from PROTAC-DB")
    return result


def resolve_panel() -> list[ResolvedMember]:
    """Resolve all seven declared panel members. Never raises on an individual miss."""
    resolved = []
    for member in PANEL:
        if member.source == "protacdb":
            resolved.append(_resolve_from_protacdb(member))
        else:
            resolved.append(_resolve_from_mgtbind(member))
    return resolved


def gate_report(resolved: list[ResolvedMember]) -> dict:
    """Phase 1 gate: all seven resolve to deposited structures."""
    unresolved = [item.member.index for item in resolved if not item.resolved]
    return {
        "total": len(resolved),
        "resolved": sum(1 for item in resolved if item.resolved),
        "unresolved_indices": unresolved,
        "passes": not unresolved,
    }
