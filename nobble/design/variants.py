"""Generate variants of a parent degron (DESIGN_ARM.md).

Deterministic and dependency-free. Every variant records the parent it came
from and the single change that made it, because the arm's headline number
is a difference from the parent and a variant that cannot name its parent
cannot be scored at all.

The parent is always a peptide with an experimental label. Nothing here
invents a sequence from nothing: the question is which positions a known
degron depends on, not whether a random 15-mer happens to bind.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

# The 20 proteinogenic residues, in a fixed order so a saturation scan is
# reproducible rather than dict-ordered.
RESIDUES = "ACDEFGHIKLMNPQRSTVWY"

# Alanine is the scanning residue because it deletes a side chain past the
# beta carbon without changing the backbone's preferences. Glycine is the
# substitute when the position is already alanine: it removes the last
# carbon rather than reporting "no change" for a position that was never
# tested.
SCAN_RESIDUE = "A"
SCAN_RESIDUE_IF_ALREADY_ALA = "G"

# Chemistry groups, for separating "needs a residue of this kind" from
# "needs exactly this residue". Conventional groupings, not a substitution
# matrix: the arm reports which group a change crossed, it does not score
# the change.
GROUPS = {
    "hydrophobic": set("AVLIMC"),
    "aromatic": set("FWY"),
    "polar": set("STNQ"),
    "positive": set("KRH"),
    "negative": set("DE"),
    "special": set("GP"),
}


def group_of(residue: str) -> str:
    for name, members in GROUPS.items():
        if residue in members:
            return name
    return "unknown"


@dataclass
class Variant:
    variant_id: str
    sequence: str
    parent_peptide_id: str
    parent_sequence: str
    generator: str
    position: int                 # 1-based, as a biologist reads it
    wild_type: str
    mutant: str
    substitution: str             # e.g. "K7A"
    crosses_group: bool
    from_group: str
    to_group: str
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        record = {
            "variant_id": self.variant_id,
            "sequence": self.sequence,
            "parent_peptide_id": self.parent_peptide_id,
            "parent_sequence": self.parent_sequence,
            "generator": self.generator,
            "position": self.position,
            "wild_type": self.wild_type,
            "mutant": self.mutant,
            "substitution": self.substitution,
            "crosses_group": self.crosses_group,
            "from_group": self.from_group,
            "to_group": self.to_group,
            "notes": self.notes,
            "length": len(self.sequence),
        }
        return record


def _variant_id(parent_id: str, substitution: str) -> str:
    digest = hashlib.sha1(f"{parent_id}:{substitution}".encode()).hexdigest()[:10]
    return f"design_{digest}"


def _make(parent_id: str, parent_sequence: str, position: int, mutant: str,
          generator: str) -> Variant:
    index = position - 1
    wild_type = parent_sequence[index]
    sequence = parent_sequence[:index] + mutant + parent_sequence[index + 1:]
    substitution = f"{wild_type}{position}{mutant}"
    from_group = group_of(wild_type)
    to_group = group_of(mutant)
    return Variant(
        variant_id=_variant_id(parent_id, substitution),
        sequence=sequence,
        parent_peptide_id=parent_id,
        parent_sequence=parent_sequence,
        generator=generator,
        position=position,
        wild_type=wild_type,
        mutant=mutant,
        substitution=substitution,
        crosses_group=from_group != to_group,
        from_group=from_group,
        to_group=to_group,
    )


def alanine_scan(parent_id: str, sequence: str) -> list[Variant]:
    """One variant per position, each residue replaced by alanine.

    A position already carrying alanine is scanned to glycine instead.
    Emitting it unchanged would put a variant identical to its parent into
    the queue, which costs 15 jobs to learn nothing, and would read on the
    chart as "this position does not matter" when it was never tested.
    """
    variants = []
    for position, residue in enumerate(sequence, start=1):
        mutant = (SCAN_RESIDUE_IF_ALREADY_ALA if residue == SCAN_RESIDUE
                  else SCAN_RESIDUE)
        variant = _make(parent_id, sequence, position, mutant, "alanine_scan")
        if residue == SCAN_RESIDUE:
            variant.notes.append(
                "position was already alanine: scanned to glycine, which "
                "removes the remaining side chain rather than reporting an "
                "untested position as unchanged"
            )
        variants.append(variant)
    return variants


def saturate(parent_id: str, sequence: str, positions: list[int]) -> list[Variant]:
    """All 19 substitutions at the given positions.

    Takes positions explicitly rather than scanning everything: saturating a
    15-mer at every position is 285 variants and 4,275 jobs, which no
    campaign budget absorbs. The alanine scan is what chooses the positions.
    """
    variants = []
    for position in sorted(set(positions)):
        if not 1 <= position <= len(sequence):
            raise ValueError(
                f"position {position} is outside the peptide (1 to {len(sequence)})"
            )
        wild_type = sequence[position - 1]
        for mutant in RESIDUES:
            if mutant == wild_type:
                continue
            variants.append(_make(parent_id, sequence, position, mutant, "saturation"))
    return variants


def generate(parent_id: str, sequence: str, generator: str = "alanine_scan",
             positions: list[int] | None = None) -> dict:
    """Entry point. Returns the variants plus the cost of running them."""
    if not sequence or any(residue not in RESIDUES for residue in sequence):
        raise ValueError(f"sequence contains a non-standard residue: {sequence!r}")

    if generator == "alanine_scan":
        variants = alanine_scan(parent_id, sequence)
    elif generator == "saturation":
        if not positions:
            raise ValueError(
                "saturation needs explicit positions: saturating every position "
                "of a 15-mer is 285 variants and no budget runs that blind"
            )
        variants = saturate(parent_id, sequence, positions)
    else:
        raise ValueError(f"unknown generator: {generator}")

    return {
        "parent_peptide_id": parent_id,
        "parent_sequence": sequence,
        "generator": generator,
        "variants": [variant.to_dict() for variant in variants],
        "count": len(variants),
        "note": (
            "Each variant is one pair and costs what any pair costs. The "
            "parent must be run under identical conditions in the same "
            "campaign: design lift is a difference of differences, so any "
            "asymmetry between parent and variant becomes signal."
        ),
    }
