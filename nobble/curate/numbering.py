"""Map deposited structure numbering onto canonical UniProt numbering.

This module exists because of a finding that would otherwise have corrupted
every downstream number in NOBBLE. 5HXB numbers its GSPT1 chain 440 to 634, in
the frame of the 637-residue isoform. UniProt canonical P15170 is 499 residues,
and so is the AlphaFold model BINMAN's Degron Scan ran on. The offset is 138.

The consequence: the canonical GSPT1 degron glycine, which the literature and the
deposited contacts both place at 575, is residue **437** in the frame every
BINMAN table uses. Comparing the two frames directly makes a correct scan look
like a miss, and hardcoding either number makes the pipeline silently wrong on
the other.

Everything that crosses between a deposition and a BINMAN table goes through
here: degron ranges, peptide extraction, pose-recovery RMSD and PLIP
fingerprints.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from nobble import paths
from nobble.curate import structures

CACHE = paths.DATA / "cache" / "uniprot"
CACHE.mkdir(parents=True, exist_ok=True)
UNIPROT_URL = "https://rest.uniprot.org/uniprotkb/{acc}.json?fields=sequence"

# Shortest deposited fragment accepted as an unambiguous anchor. Thirty residues
# of an ordered domain is specific enough that a chance match in a 500-residue
# protein is not a practical concern; the ladder shortens it only when the
# deposition is itself short.
ANCHOR_LENGTHS = (30, 25, 20, 15, 12)

# How far into the deposited chain the anchor may start. Depositions routinely
# begin with a cloning or purification remnant that is absent from the canonical
# sequence: 6H0F's IKZF1 chain starts GGR where canonical Q13422 has SHT, and
# anchoring only at the N-terminus therefore fails on a perfectly ordinary
# structure. The anchor slides until it finds canonical sequence, and the
# smallest slide that anchors uniquely wins.
MAX_ANCHOR_SLIDE = 40

# Residues allowed to disagree between the deposited chain and the canonical
# sequence at the resolved offset, as a fraction of the aligned length. A
# deposition may carry an engineered point mutation or a modified residue; a
# frame that disagrees beyond this is not an offset problem but a different
# protein, and raising is the correct outcome.
MAX_MISMATCH_FRACTION = 0.1


@dataclass(frozen=True)
class Frame:
    """The relationship between one deposited chain and its canonical sequence."""

    pdb_id: str
    chain: str
    accession: str
    offset: int                 # canonical = deposited - offset
    deposited_start: int
    deposited_end: int
    canonical_start: int
    canonical_length: int
    anchor_length: int
    anchor_slide: int           # residues of deposited chain skipped as a tag
    mismatches: int             # residues disagreeing at the resolved offset
    aligned: int                # residues compared
    identical: bool             # offset of zero: the frames already agree

    def to_canonical(self, deposited_residue: int) -> int:
        return deposited_residue - self.offset

    def to_deposited(self, canonical_residue: int) -> int:
        return canonical_residue + self.offset

    def to_dict(self) -> dict:
        return {
            "pdb_id": self.pdb_id,
            "chain": self.chain,
            "accession": self.accession,
            "offset": self.offset,
            "deposited_range": [self.deposited_start, self.deposited_end],
            "canonical_start": self.canonical_start,
            "canonical_length": self.canonical_length,
            "anchor_length": self.anchor_length,
            "anchor_slide": self.anchor_slide,
            "mismatches": self.mismatches,
            "aligned": self.aligned,
            "frames_agree": self.identical,
        }


class FrameUnresolved(RuntimeError):
    """The deposited chain could not be anchored in the canonical sequence."""


@lru_cache(maxsize=512)
def canonical_sequence(accession: str) -> str:
    """Canonical UniProt sequence, cached to disk so a campaign needs no network."""
    cached = CACHE / f"{accession}.seq"
    if cached.exists():
        return cached.read_text().strip()
    request = urllib.request.Request(
        UNIPROT_URL.format(acc=accession), headers={"Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)
    sequence = payload["sequence"]["value"]
    cached.write_text(sequence)
    return sequence


def resolve_frame(pdb_id: str, chain: str, accession: str) -> Frame:
    """Anchor a deposited chain in its canonical sequence by exact substring match.

    Exact matching rather than alignment is deliberate: an offset is only
    meaningful when the deposited fragment is a contiguous, unmutated run of the
    canonical sequence. A deposition carrying point mutations will fail to anchor
    and raise, which is the correct outcome, because an offset derived from a
    gapped alignment would be applied to residues the gap invalidates.
    """
    summary = [item for item in structures.chain_summary(pdb_id) if item["chain"] == chain]
    if not summary:
        raise FrameUnresolved(f"{pdb_id} has no chain {chain}")
    observed = summary[0]
    deposited = observed["sequence"]
    if not deposited:
        raise FrameUnresolved(f"{pdb_id} chain {chain} holds no amino acids")

    canonical = canonical_sequence(accession)

    def agreement(offset: int) -> tuple[int, int]:
        """Count mismatches between the deposited chain and canonical at an offset."""
        mismatches = aligned = 0
        for position, residue in enumerate(deposited):
            canonical_index = observed["first_seqid"] + position - offset - 1
            if 0 <= canonical_index < len(canonical):
                aligned += 1
                if canonical[canonical_index] != residue:
                    mismatches += 1
        return mismatches, aligned

    for anchor_length in ANCHOR_LENGTHS:
        if len(deposited) < anchor_length:
            continue
        slide_limit = min(MAX_ANCHOR_SLIDE, len(deposited) - anchor_length) + 1
        for slide in range(slide_limit):
            anchor = deposited[slide:slide + anchor_length]
            position = canonical.find(anchor)
            if position < 0:
                continue
            if canonical.find(anchor, position + 1) >= 0:
                # Ambiguous at this length: the chain starts inside a repeat.
                continue
            offset = (observed["first_seqid"] + slide) - (position + 1)
            mismatches, aligned = agreement(offset)
            if aligned and mismatches / aligned > MAX_MISMATCH_FRACTION:
                continue
            return Frame(
                pdb_id=pdb_id.upper(),
                chain=chain,
                accession=accession,
                offset=offset,
                deposited_start=observed["first_seqid"],
                deposited_end=observed["last_seqid"],
                canonical_start=position + 1 - slide,
                canonical_length=len(canonical),
                anchor_length=anchor_length,
                anchor_slide=slide,
                mismatches=mismatches,
                aligned=aligned,
                identical=offset == 0,
            )

    raise FrameUnresolved(
        f"{pdb_id} chain {chain} could not be anchored in {accession}: the deposited "
        "sequence is not a contiguous run of the canonical one (expression tag, "
        "mutation or a different isoform)"
    )
