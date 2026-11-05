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

from dataclasses import dataclass

from nobble import paths
from nobble.curate import interpro, numbering


@dataclass(frozen=True)
class Segment:
    """One polypeptide segment of a construct, defined by an InterPro entry."""

    accession: str                  # UniProt
    label: str
    interpro_entry: str | None      # None means the whole canonical sequence
    note: str = ""
    # Which annotation of that entry, counted from the N-terminus, when the
    # entry appears more than once on the protein. FEM1B carries the ankyrin
    # superfamily twice and the lookup alone cannot say which region binds
    # the substrate (F41). Left None for an unambiguous entry, and the lookup
    # refuses rather than guessing if one ever becomes ambiguous.
    interpro_occurrence: int | None = None

    def range(self) -> tuple[int, int]:
        if self.interpro_entry is None:
            return 1, len(numbering.canonical_sequence(self.accession))
        record = interpro.domain_by_accession(
            self.accession, self.interpro_entry, self.interpro_occurrence
        )
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

    def substrate_receptor_chains(self) -> tuple[int, ...]:
        """Chain indices belonging to the substrate-recognition protein.

        A construct is several chains in the YAML and one of them, or a few,
        is the protein the degron actually binds. DCAF15 is submitted as two
        segments, an N-terminal and a C-terminal domain, with DDB1's two beta
        propellers and DDA1 behind them: five chains, of which the substrate
        sees two.

        Identified by accession rather than by label, because the labels are
        domain names and do not all carry the gene: CRBN_CULT's only segment
        is labelled "CULT domain". The substrate receptor is the protein the
        construct is named for and is submitted first, which
        `tests/test_iptm_chains.py` holds to.
        """
        first = self.segments[0].accession
        return tuple(
            index for index, segment in enumerate(self.segments)
            if segment.accession == first
        )

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
                    "repeats and no TPR on Q9UK73 (D-NOB-014). The superfamily "
                    "is annotated twice, 5-301 and 424-610; the N-terminal "
                    "region is the substrate-binding one, declared here rather "
                    "than taken from InterPro's ordering (F41)",
                    interpro_occurrence=0),
        ),
        rationale="Substrate-binding domain alone, per spec 1.1",
    ),
}


def by_name(name: str) -> Construct:
    """A receptor construct by name, from either tier's registry.

    `CONSTRUCTS` above holds spec 1.1's six Tier A receptors, written in
    Python because they are part of the spec. Spec 3.3's Tier B receptors
    are named in `config/tier_b_constructs.toml` instead, because which
    domain of a ligase binds its substrate is a judgement someone has to
    make and a form is where a judgement gets recorded (F163).

    Two registries, one lookup. `campaign.py` indexed `CONSTRUCTS` directly,
    so the eleven Tier B constructs were recorded, validated and unreachable:
    the assembler could not have found one if it had asked. Widened here
    rather than given a second lookup at the call site, which is D-NOB-007's
    rule and F181's lesson both (F210).

    Tier A wins a name collision, and there is none today: the six Tier A
    keys and the eleven Tier B keys are disjoint, which a test asserts
    rather than this function assuming.
    """
    if name in CONSTRUCTS:
        return CONSTRUCTS[name]
    # Imported here, not at module scope: tier_b_constructs imports this
    # module for Construct and Segment, so a top-level import is a cycle.
    from nobble.curate import tier_b_constructs

    tier_b = tier_b_constructs.load()
    if name in tier_b:
        return tier_b[name]
    raise KeyError(
        f"no receptor construct named {name!r}. Tier A: "
        f"{sorted(CONSTRUCTS)}. Tier B, from "
        f"config/tier_b_constructs.toml: {sorted(tier_b)}"
    )


def by_name_or_none(name: str | None) -> Construct | None:
    """`by_name`, or None for a missing or unknown name.

    For the one caller that treats an unknown construct as a status rather
    than an error: `score/geometry.py` reports `unknown_construct` and
    carries on, because a geometry row that cannot name its receptor chains
    is a row to skip rather than a reason to abandon a scoring run.
    """
    if not name:
        return None
    try:
        return by_name(name)
    except KeyError:
        return None


def all_constructs() -> dict[str, Construct]:
    """Every receptor construct, Tier A and Tier B.

    For callers that need the whole set rather than one by name: the
    declared-exception set below, and `msa.required_sequences`.

    Not `budget_report`, deliberately. That feeds the About page's
    construct table through `about.json`, and widening it put eleven Tier B
    rows onto a published page as a side effect of a refactor. It is spec
    1.1's cap report for the six receptors the spec names; Tier B has its
    own in `tier_b_constructs.report()`. The atlas drift check caught it,
    which is what that check is for.
    """
    from nobble.curate import tier_b_constructs

    return {**tier_b_constructs.load(), **CONSTRUCTS}


def declared_exceptions() -> set[str]:
    """Constructs allowed past the tier-1 token cap.

    One definition. This set was built twice, by `manifest.validate` and by
    `tools/preflight.py`, from identical comprehensions over `CONSTRUCTS`
    alone, so declaring a Tier B construct an exception changed nothing in
    either: DCAF8L1_WD40 was marked `exception = true` in the form and the
    manifest still reported ten token_cap_exceeded errors, because the set
    it was checked against only ever held Tier A names.

    Two copies of one rule is F181, and a rule that spans one of two
    registries is F210. This is both, so it is both fixes (F211).
    """
    return {name for name, item in all_constructs().items() if item.exception}


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
