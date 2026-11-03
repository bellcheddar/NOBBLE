"""Receptor construct definitions (spec 1.1 and Phase 1).

Each construct names the InterPro entry that defines its substrate-binding
domain; the residue range comes from InterPro at build time. Nothing here
hardcodes a residue number.

Two receptors are declared structural exceptions to the 400-token tier-1 cap,
for the reasons spec 1.1 gives:

- VHL does not fold in isolation and requires ElonginB and ElonginC, so the
  receptor is the VCB trimer. A VHL-only model is physically wrong whatever its
  confidence metrics say.
- DCAF15 does not engage RBM39 without DDB1 and DDA1, so the receptor is the
  DCAF15 / DDB1 / DDA1 assembly with DDB1's BPB propeller dropped.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from nobble import paths
from nobble.curate import interpro, numbering


@dataclass(frozen=True)
class Segment:
    """One polypeptide segment of a construct, defined by an InterPro entry."""

    accession: str                  # UniProt
    label: str
    interpro_entry: str | None      # None means the whole canonical sequence
    note: str = ""

    def range(self) -> tuple[int, int]:
        if self.interpro_entry is None:
            return 1, len(numbering.canonical_sequence(self.accession))
        record = interpro.domain_by_accession(self.accession, self.interpro_entry)
        return record["start"], record["end"]

    def sequence(self) -> str:
        start, end = self.range()
        return numbering.canonical_sequence(self.accession)[start - 1 : end]


@dataclass(frozen=True)
class Construct:
    """A receptor as it will be submitted to Boltz: one or more segments."""

    name: str
    e3_gene: str
    segments: tuple[Segment, ...]
    exception: bool = False
    rationale: str = ""

    def sequences(self) -> list[str]:
        return [segment.sequence() for segment in self.segments]

    def residue_count(self) -> int:
        return sum(len(sequence) for sequence in self.sequences())

    def describe(self) -> dict:
        parts = []
        for segment in self.segments:
            start, end = segment.range()
            parts.append(
                {
                    "accession": segment.accession,
                    "label": segment.label,
                    "interpro_entry": segment.interpro_entry,
                    "start": start,
                    "end": end,
                    "length": end - start + 1,
                    "note": segment.note,
                }
            )
        return {
            "name": self.name,
            "e3_gene": self.e3_gene,
            "segments": parts,
            "residue_count": self.residue_count(),
            "declared_exception": self.exception,
            "rationale": self.rationale,
        }


# UniProt accessions for the obligate partners, named once.
ELONGIN_B = "Q15370"
ELONGIN_C = "Q15369"
DDA1 = "Q9BW61"
DDB1 = "Q16531"

# InterPro entries that define each substrate-binding domain.
CULT_DOMAIN = "IPR034750"          # CRBN, 318-426: the thalidomide-binding domain
VHL_BETA_ALPHA = "IPR022772"       # VHL, 64-203: beta-domain plus VHL box
DCAF15_N = "IPR032734"             # DCAF15 N-terminal WD40-repeat region
DCAF15_C = "IPR047319"             # DCAF15 C-terminal domain
DDB1_BPA = "IPR018846"             # DDB1 first beta-propeller
DDB1_BPC = "IPR004871"             # DDB1 C-terminal propeller
KEAP1_KELCH = "IPR015915"          # Kelch-type beta-propeller, 309-624
# Spec 1.1 calls this "FEM1B TPR". InterPro annotates no TPR repeat on Q9UK73:
# FEM1B recognises its C-degron substrates through ankyrin repeats, and the
# N-terminal ANK region is the substrate-binding domain. Recorded as D-NOB-014.
FEM1B_ANK = "IPR036770"            # Ankyrin repeat-containing superfamily, 5-301

CONSTRUCTS: dict[str, Construct] = {
    "CRBN_CULT": Construct(
        name="CRBN_CULT",
        e3_gene="CRBN",
        segments=(
            Segment("Q96SW2", "CULT domain", CULT_DOMAIN,
                    "The thalidomide-binding domain: the IMiD pocket and the "
                    "neosubstrate degron site are both in it"),
        ),
        rationale="Substrate-binding domain alone, per spec 1.1",
    ),
    "VHL_VCB": Construct(
        name="VHL_VCB",
        e3_gene="VHL",
        segments=(
            Segment("P40337", "VHL beta-domain and VHL box", VHL_BETA_ALPHA),
            Segment(ELONGIN_B, "ElonginB", None, "Obligate partner: full chain"),
            Segment(ELONGIN_C, "ElonginC", None, "Obligate partner: full chain"),
        ),
        exception=True,
        rationale="VHL does not fold in isolation: it requires ElonginB and "
                  "ElonginC for stability, so a VHL-only receptor is physically "
                  "wrong regardless of its confidence metrics (spec 1.1)",
    ),
    "DCAF15_DDB1_DDA1": Construct(
        name="DCAF15_DDB1_DDA1",
        e3_gene="DCAF15",
        segments=(
            Segment("Q66K64", "DCAF15 N-terminal domain", DCAF15_N),
            Segment("Q66K64", "DCAF15 C-terminal domain", DCAF15_C),
            Segment(DDB1, "DDB1 BPA", DDB1_BPA, "BPB dropped to control token count"),
            Segment(DDB1, "DDB1 BPC", DDB1_BPC, "BPB dropped to control token count"),
            Segment(DDA1, "DDA1", None, "Obligate partner: full chain"),
        ),
        exception=True,
        rationale="DCAF15 does not engage RBM39 without DDB1 and DDA1 (spec 1.1). "
                  "DDB1's BPB propeller is dropped, which is the truncation spec "
                  "1.1 names",
    ),
    "DDB1_BPC": Construct(
        name="DDB1_BPC",
        e3_gene="DDB1",
        segments=(
            Segment(DDB1, "DDB1 BPC", DDB1_BPC,
                    "The only propeller CR-8 touches: measured at 907-947 in 6TD3, "
                    "with no BPA or BPB contact inside 5 A"),
        ),
        rationale="Benchmark member 7 (cyclin K / CR-8) has no substrate receptor "
                  "at all: the glue acts on DDB1 directly. BPA and BPB are dropped "
                  "because neither contacts the glue, which brings the job under "
                  "the tier-1 cap with no exception needed (D-NOB-013)",
    ),
    "KEAP1_KELCH": Construct(
        name="KEAP1_KELCH",
        e3_gene="KEAP1",
        segments=(Segment("Q14145", "Kelch beta-propeller", KEAP1_KELCH),),
        rationale="Substrate-binding domain alone, per spec 1.1",
    ),
    "FEM1B_ANK": Construct(
        name="FEM1B_ANK",
        e3_gene="FEM1B",
        segments=(
            Segment("Q9UK73", "Ankyrin repeats, N-terminal region", FEM1B_ANK,
                    "Spec 1.1 names a TPR domain; InterPro annotates ankyrin "
                    "repeats and no TPR on Q9UK73 (D-NOB-014)"),
        ),
        rationale="Substrate-binding domain alone, per spec 1.1",
    ),
}


def token_estimate(construct: Construct, peptide_length: int, ligand_heavy_atoms: int) -> int:
    """Boltz token count for a job: one per polymer residue, one per ligand heavy atom."""
    return construct.residue_count() + peptide_length + ligand_heavy_atoms


def budget_report(peptide_length: int = 15, ligand_heavy_atoms: int = 30) -> list[dict]:
    """Measured token count per construct against the tier-1 cap.

    The cap is read from config, and a construct over it is only acceptable if it
    is one of the two declared exceptions.
    """
    cap = paths.thresholds()["manifest"]["token_cap_tier1"]
    report = []
    for construct in CONSTRUCTS.values():
        try:
            tokens = token_estimate(construct, peptide_length, ligand_heavy_atoms)
            residues = construct.residue_count()
            error = None
        except Exception as problem:          # noqa: BLE001
            tokens = residues = None
            error = f"{type(problem).__name__}: {problem}"
        report.append(
            {
                "name": construct.name,
                "e3_gene": construct.e3_gene,
                "residues": residues,
                "tokens": tokens,
                "cap": cap,
                "within_cap": None if tokens is None else tokens <= cap,
                "declared_exception": construct.exception,
                "acceptable": None if tokens is None else (tokens <= cap or construct.exception),
                "error": error,
            }
        )
    return report
