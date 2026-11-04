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
MAX_MISMATCH_FRACTION = float(paths.thresholds()["numbering"]["max_mismatch_fraction"])


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
    """Anchor a deposited chain in its canonical sequence and return the offset.

    The comparison is per-residue by deposited number, not by position in a
    concatenated string. Receptor chains routinely have unmodelled internal
    loops: 5HXB's CRBN chain, 5FQD's CRBN chain, 6Q0W's DCAF15 chain and 6TD3's
    DDB1 chain all do. Treating their observed residues as one contiguous run
    makes every residue after the first gap disagree with the canonical
    sequence, and an earlier version of this function rejected all four of them
    as "not a contiguous run" while their numbering in fact already matched
    canonical exactly (offset 0).

    Candidate offsets come from exact k-mer matches on contiguous runs; each is
    then scored against every observed residue, and the best-agreeing offset
    wins. A chain whose best offset still disagrees beyond
    MAX_MISMATCH_FRACTION raises, which is correct: that is a different protein
    or a heavily engineered construct, not an offset problem.
    """
    observed = structures.chain_residues(pdb_id, chain)
    if not observed:
        raise FrameUnresolved(f"{pdb_id} chain {chain} holds no amino acids")

    canonical = canonical_sequence(accession)
    if not canonical:
        raise FrameUnresolved(f"no canonical sequence for {accession}")

    by_seqid = dict(observed)
    first_seqid = observed[0][0]
    last_seqid = observed[-1][0]

    def agreement(offset: int) -> tuple[int, int]:
        """Mismatches and comparisons for one candidate offset, gap-aware."""
        mismatches = aligned = 0
        for seqid, code in observed:
            index = seqid - offset - 1
            if 0 <= index < len(canonical):
                aligned += 1
                if canonical[index] != code:
                    mismatches += 1
        return mismatches, aligned

    # Candidate offsets from exact k-mer matches over contiguous runs.
    candidates: dict[int, None] = {}
    runs: list[list[tuple[int, str]]] = [[observed[0]]]
    for entry in observed[1:]:
        if entry[0] == runs[-1][-1][0] + 1:
            runs[-1].append(entry)
        else:
            runs.append([entry])

    for anchor_length in ANCHOR_LENGTHS:
        for run in sorted(runs, key=len, reverse=True):
            if len(run) < anchor_length:
                continue
            for slide in range(0, min(MAX_ANCHOR_SLIDE, len(run) - anchor_length) + 1):
                window = run[slide : slide + anchor_length]
                anchor = "".join(code for _seqid, code in window)
                position = canonical.find(anchor)
                while position >= 0:
                    candidates.setdefault(window[0][0] - (position + 1), None)
                    position = canonical.find(anchor, position + 1)
            if candidates:
                break
        if candidates:
            break

    # Offset zero is always worth testing: most depositions already agree.
    candidates.setdefault(0, None)

    best: tuple[float, int, int, int] | None = None
    for offset in candidates:
        mismatches, aligned = agreement(offset)
        if not aligned:
            continue
        rate = mismatches / aligned
        # Prefer the lowest mismatch rate, then the most residues aligned, then
        # the smallest absolute offset, so a tie resolves to the simplest frame.
        score = (rate, -aligned, abs(offset))
        if best is None or score < (best[0], -best[2], abs(best[1])):
            best = (rate, offset, aligned, mismatches)

    if best is None:
        raise FrameUnresolved(
            f"{pdb_id} chain {chain}: no candidate offset aligned any residue of {accession}"
        )

    rate, offset, aligned, mismatches = best
    if rate > MAX_MISMATCH_FRACTION:
        raise FrameUnresolved(
            f"{pdb_id} chain {chain} does not match {accession} at any offset: best "
            f"offset {offset} disagrees on {mismatches} of {aligned} observed residues "
            f"({rate:.0%}), above the {MAX_MISMATCH_FRACTION:.0%} tolerance"
        )

    canonical_start = first_seqid - offset
    return Frame(
        pdb_id=pdb_id.upper(),
        chain=chain,
        accession=accession,
        offset=offset,
        deposited_start=first_seqid,
        deposited_end=last_seqid,
        canonical_start=canonical_start,
        canonical_length=len(canonical),
        anchor_length=min(ANCHOR_LENGTHS),
        anchor_slide=0,
        mismatches=mismatches,
        aligned=aligned,
        identical=offset == 0,
    )
