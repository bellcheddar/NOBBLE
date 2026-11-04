"""Peptide library construction (spec 3.4).

Five sources of positives and one of negatives, each tagged with its provenance
so the results table can facet on where a peptide came from:

- curated degrons: UbiBrowser literature substrates, tiled across the degron
  region BINMAN's structural scan reports for that substrate, plus flanks
- Sievers zinc fingers: the degraded set and the matched non-degraded set, taken
  as whole zinc-finger domains rather than tiles
- C-degrons: generated per the Koren 2018 class rules for the relevant E3
- benchmark degrons: the seven panel members, located from their deposited
  ternaries
- negatives: a composition-matched scramble of every positive, plus the Sievers
  non-degraded set

The matched negatives are the point of the exercise. A scramble holds amino-acid
composition and length constant and destroys order, so a Delta-ipTM separation
between a degron and its own scramble cannot be a composition artefact.

Spec 3.4 asks for the degron region "+/- 20 residues" from UbiBrowser's
annotation. UbiBrowser's literature export carries only (E3 gene, substrate
gene) pairs with no coordinates, and Degronopedia, which would have carried
them, was never acquired (D-NOB-010). The region therefore comes from BINMAN's
own Degron Scan for that substrate, which is the only degron coordinate source
available and is the same one the Phase 1 gate validated against two deposited
structures. Recorded as D-NOB-018.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import asdict, dataclass, field
from functools import lru_cache

from nobble import paths
from nobble.curate import binman_store as store
from nobble.curate import numbering, plddt

FOLDED_DOMAIN_EXCEPTION_MIN_LENGTH = int(
    paths.thresholds()["manifest"]["folded_domain_exception_min_length"]
)

# Post-translational modifications that are non-negotiable for a degron class
# (spec 2.3). A peptide of one of these classes submitted without its
# modification is a manifest error, not a low-scoring result.
REQUIRED_MODIFICATIONS = {
    "vhl_hif1a": {"residue": "P", "ccd": "HYP", "note": "hydroxyproline"},
    "btrcp_dsgxxs": {"residue": "S", "ccd": "SEP", "note": "phosphoserine"},
    "fbxw7_cpd": {"residue": "ST", "ccd": "SEP/TPO", "note": "phosphoserine or phosphothreonine"},
}

# C-degron classes from Koren et al. 2018 (Cell 173:1622) and the structural work
# that followed it. Each is a C-terminal pattern and the E3 that reads it. These
# are motif definitions from the literature, not thresholds, which is why they
# live in code with their citation rather than in config/thresholds.toml.
C_DEGRON_CLASSES = (
    {"name": "gly_gly", "e3": "KLHDC2", "suffix": "GG",
     "note": "C-terminal diglycine, read by the CRL2-KLHDC2 receptor"},
    {"name": "arg_gly", "e3": "KLHDC3", "suffix": "RG",
     "note": "C-terminal Arg-Gly, read by KLHDC3"},
    {"name": "lys_gly", "e3": "KLHDC3", "suffix": "KG",
     "note": "C-terminal Lys-Gly, read by KLHDC3"},
    {"name": "arg", "e3": "FEM1B", "suffix": "R",
     "note": "C-terminal arginine, the Arg/C-degron read by FEM1A, FEM1B and FEM1C"},
    {"name": "glu_glu", "e3": "TRPC4AP", "suffix": "EE",
     "note": "C-terminal di-glutamate, read by the TRPC4AP receptor"},
    {"name": "pro_gly", "e3": "KLHDC10", "suffix": "PG",
     "note": "C-terminal Pro-Gly, read by KLHDC10"},
)

AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")


@dataclass
class Peptide:
    """One peptide chain as it will be submitted to Boltz."""

    peptide_id: str
    sequence: str
    source: str                   # curated_degron | sievers_zf | c_degron | benchmark | scramble
    label: str | None             # degraded | not_degraded | unknown
    accession: str | None
    gene: str | None
    start_res: int | None
    end_res: int | None
    degron_class: str | None = None
    e3_hint: str | None = None
    parent_peptide_id: str | None = None
    required_modification: dict | None = None
    # Whether this window is a linear epitope or a slice of a folded domain.
    # See domain_context and D-NOB-027.
    domain_context: dict | None = None
    # Which IMiDs the Sievers screen tested and which were significant for
    # this zinc finger, kept structured rather than only prose in `notes`:
    # the arm's drug assignment reads it, and parsing it back out of a
    # sentence would be a silent dependency on the sentence's wording.
    screen_drugs: dict | None = None
    # An explicit cofactor decision that overrides inference from the
    # sequence. Design variants carry their parent's, because a scan that
    # mutates a coordinating residue would otherwise silently drop the ion
    # and report its absence as the substitution's effect (D-NOB-038).
    cofactor: dict | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self.sequence)

    def to_dict(self) -> dict:
        record = asdict(self)
        record["length"] = self.length
        return record


def _peptide_id(source: str, sequence: str, extra: str = "") -> str:
    digest = hashlib.sha1(f"{source}|{sequence}|{extra}".encode()).hexdigest()[:10]
    return f"{source}_{digest}"


def _clean(sequence: str) -> str:
    """Uppercase and drop anything that is not one of the twenty."""
    return "".join(residue for residue in sequence.upper() if residue in AMINO_ACIDS)


def canonical(accession: str) -> str:
    """Canonical sequence for an accession, offline first.

    BINMAN's AlphaFold cache holds 20,279 models and AlphaFold DB models the
    canonical UniProt sequence, so the cache answers for free what would
    otherwise be one UniProt request per accession. Falls back to the REST
    endpoint (itself disk-cached) only when there is no model, which keeps
    library construction from turning into thousands of network calls.
    """
    sequence = plddt.model_sequence(accession)
    if sequence:
        return _clean(sequence)
    try:
        return _clean(numbering.canonical_sequence(accession))
    except Exception:                          # noqa: BLE001
        return ""


@lru_cache(maxsize=1)
def _gene_to_accession() -> dict[str, str]:
    """Gene symbol to UniProt accession, from BINMAN's own tables."""
    mapping: dict[str, str] = {}
    for table in ("degron", "ligase"):
        for row in store.atlas_rows(
            f"select distinct gene, uniprot_acc from {table} where gene is not null and gene != ''"
        ):
            mapping.setdefault(row["gene"].upper(), row["uniprot_acc"])
    return mapping


def _entry_name_to_gene(entry_name: str) -> str:
    """UbiBrowser uses UniProt entry names such as AHR_HUMAN."""
    return entry_name.split("_")[0].upper()


def tile(sequence: str, length: int, step: int) -> list[tuple[int, str]]:
    """Overlapping windows as (1-based offset within sequence, window)."""
    if len(sequence) <= length:
        return [(1, sequence)] if sequence else []
    return [
        (start + 1, sequence[start : start + length])
        for start in range(0, len(sequence) - length + 1, step)
    ]


def curated_degron_peptides(limit_substrates: int | None = None) -> list[Peptide]:
    """UbiBrowser literature substrates, tiled across their scanned degron regions."""
    settings = paths.thresholds()["peptide"]
    length = int(settings["tile_length"])
    step = int(settings["tile_step"])
    flank = int(settings["degron_flank"])

    pairs = store.dataset("ubibrowser_literature_e3")
    mapping = _gene_to_accession()

    # One substrate can be targeted by several E3s: keep the E3s as a hint set.
    substrates: dict[str, set[str]] = {}
    for row in pairs:
        substrate = _entry_name_to_gene(row["substrate_gene"])
        e3 = _entry_name_to_gene(row["e3_gene"])
        substrates.setdefault(substrate, set()).add(e3)

    peptides: list[Peptide] = []
    processed = 0
    for gene in sorted(substrates):
        accession = mapping.get(gene)
        if not accession:
            continue
        degrons = store.atlas_rows(
            "select start_res, end_res, tip_res, motif_family, degron_geometry_score "
            "from degron where uniprot_acc = ? and status = 'ok' "
            "order by degron_geometry_score desc limit 3",
            (accession,),
        )
        if not degrons:
            continue
        sequence = canonical(accession)
        if not sequence:
            continue

        for degron in degrons:
            start = max(1, degron["start_res"] - flank)
            end = min(len(sequence), degron["end_res"] + flank)
            region = sequence[start - 1 : end]
            for offset, window in tile(_clean(region), length, step):
                absolute = start + offset - 1
                peptides.append(
                    Peptide(
                        peptide_id=_peptide_id("curated", window, f"{accession}:{absolute}"),
                        sequence=window,
                        source="curated_degron",
                        label="unknown",
                        accession=accession,
                        gene=gene,
                        start_res=absolute,
                        end_res=absolute + len(window) - 1,
                        degron_class=degron["motif_family"],
                        e3_hint=",".join(sorted(substrates[gene])),
                        notes=[
                            f"tiled across scanned degron {degron['start_res']}-"
                            f"{degron['end_res']} plus {flank} flanking residues"
                        ],
                    )
                )
        processed += 1
        if limit_substrates and processed >= limit_substrates:
            break
    return peptides


def sievers_peptides() -> list[Peptide]:
    """The Sievers screen: matched degraded and non-degraded zinc fingers.

    These are taken whole rather than tiled: a zinc finger is a folding unit and
    a 15-residue window through one is neither the degron nor a domain.
    """
    peptides = []
    for row in store.dataset("sievers_zf_screen"):
        sequence = _clean(row["aa_sequence"])
        if not sequence:
            continue
        degraded = str(row.get("degraded", "")).strip()
        label = {"1": "degraded", "0": "not_degraded"}.get(degraded, "unknown")
        peptides.append(
            Peptide(
                peptide_id=_peptide_id(
                    "sievers", sequence, f"{row['uniprot']}:{row['zf_start']}"
                ),
                sequence=sequence,
                source="sievers_zf",
                label=label,
                accession=row["uniprot"],
                gene=row["gene"],
                start_res=int(row["zf_start"]) if row["zf_start"] else None,
                end_res=int(row["zf_stop"]) if row["zf_stop"] else None,
                degron_class="zinc_finger",
                e3_hint="CRBN",
                screen_drugs={
                    "tested": [d.strip() for d in
                               str(row.get("drugs_tested", "")).split(";") if d.strip()],
                    "significant": [d.strip() for d in
                                    str(row.get("drugs_significant", "")).split(";")
                                    if d.strip()],
                    "min_fdr": row.get("min_fdr"),
                },
                notes=[
                    f"IMiD screen: drugs tested {row.get('drugs_tested', '')}; "
                    f"significant {row.get('drugs_significant', '') or 'none'}; "
                    f"min FDR {row.get('min_fdr', '')}"
                ],
            )
        )
    return peptides


def c_degron_peptides(limit: int | None = None) -> list[Peptide]:
    """C-terminal degrons generated per the Koren 2018 class rules.

    Scanned over the substrates BINMAN already has canonical sequences cached
    for, so this adds no network traffic to a campaign.
    """
    settings = paths.thresholds()["peptide"]
    length = int(settings["tile_length"])

    accessions = [
        row["uniprot_acc"]
        for row in store.atlas_rows(
            "select distinct uniprot_acc from degron where status = 'ok'"
        )
    ]
    peptides: list[Peptide] = []
    for accession in accessions:
        sequence = canonical(accession)
        if len(sequence) < length:
            continue
        for rule in C_DEGRON_CLASSES:
            if not sequence.endswith(rule["suffix"]):
                continue
            window = sequence[-length:]
            start = len(sequence) - length + 1
            peptides.append(
                Peptide(
                    peptide_id=_peptide_id("cdegron", window, rule["name"]),
                    sequence=window,
                    source="c_degron",
                    label="unknown",
                    accession=accession,
                    gene=None,
                    start_res=start,
                    end_res=len(sequence),
                    degron_class=f"c_degron_{rule['name']}",
                    e3_hint=rule["e3"],
                    notes=[rule["note"], "Koren et al. 2018, Cell 173:1622"],
                )
            )
            if limit and len(peptides) >= limit:
                return peptides
    return peptides


def composition_matched_scramble(peptide: Peptide, seed: int) -> Peptide:
    """One scramble per positive: same composition and length, order destroyed.

    The seed is derived from the parent peptide identifier, so the scramble is
    reproducible across runs and across machines without storing it.
    """
    residues = list(peptide.sequence)
    generator = random.Random(f"{peptide.peptide_id}:{seed}")
    # Reject the identity permutation, and anything that happens to reproduce the
    # parent: a scramble equal to its parent is not a negative control.
    for _ in range(64):
        generator.shuffle(residues)
        candidate = "".join(residues)
        if candidate != peptide.sequence:
            break
    else:
        candidate = "".join(reversed(peptide.sequence))

    return Peptide(
        peptide_id=_peptide_id("scramble", candidate, peptide.peptide_id),
        sequence=candidate,
        source="scramble",
        label="negative_control",
        accession=peptide.accession,
        gene=peptide.gene,
        start_res=None,
        end_res=None,
        degron_class=f"scramble_of_{peptide.degron_class}",
        e3_hint=peptide.e3_hint,
        parent_peptide_id=peptide.peptide_id,
        notes=["composition-matched scramble: same residues and length, order destroyed"],
    )


def annotate_required_modifications(peptides: list[Peptide]) -> list[Peptide]:
    """Attach the modification a degron class cannot be submitted without (spec 2.3)."""
    for peptide in peptides:
        hint = (peptide.e3_hint or "").upper()
        degron_class = (peptide.degron_class or "").lower()
        requirement = None
        if "VHL" in hint or "hif" in degron_class:
            requirement = REQUIRED_MODIFICATIONS["vhl_hif1a"]
        elif "BTRC" in hint or "dsg" in degron_class:
            requirement = REQUIRED_MODIFICATIONS["btrcp_dsgxxs"]
        elif "FBXW7" in hint or "cpd" in degron_class:
            requirement = REQUIRED_MODIFICATIONS["fbxw7_cpd"]
        if requirement and any(
            residue in peptide.sequence for residue in requirement["residue"]
        ):
            peptide.required_modification = dict(requirement)
    return peptides


def build(limit_substrates: int | None = None, include_scrambles: bool = True) -> dict:
    """Assemble the full candidate library before diversity reduction."""
    positives: list[Peptide] = []
    positives.extend(benchmark_peptides())
    positives.extend(curated_degron_peptides(limit_substrates=limit_substrates))
    # The matched subset rather than all 5,663: see sievers_matched_set.
    positives.extend(sievers_matched_set()["peptides"])
    positives.extend(c_degron_peptides())
    positives = annotate_required_modifications(positives)
    positives = annotate_domain_context(positives)

    negatives: list[Peptide] = []
    if include_scrambles:
        per_positive = int(paths.thresholds()["peptide"]["scrambles_per_positive"])
        for peptide in positives:
            if peptide.source == "sievers_zf" and peptide.label == "not_degraded":
                # Already a matched experimental negative: a scramble of it adds
                # nothing and doubles the budget.
                continue
            for index in range(per_positive):
                negatives.append(composition_matched_scramble(peptide, index))

    library = positives + negatives
    # Deduplicate on sequence while keeping the first (richest) provenance.
    seen: dict[str, Peptide] = {}
    for peptide in library:
        seen.setdefault(peptide.sequence, peptide)
    unique = list(seen.values())

    by_source: dict[str, int] = {}
    by_label: dict[str, int] = {}
    for peptide in unique:
        by_source[peptide.source] = by_source.get(peptide.source, 0) + 1
        by_label[peptide.label or "none"] = by_label.get(peptide.label or "none", 0) + 1

    return {
        "peptides": unique,
        "total_before_dedup": len(library),
        "total": len(unique),
        "by_source": by_source,
        "by_label": by_label,
        "requiring_modification": sum(
            1 for peptide in unique if peptide.required_modification
        ),
    }


def _composition(sequence: str) -> dict[str, float]:
    if not sequence:
        return {}
    total = len(sequence)
    counts: dict[str, int] = {}
    for residue in sequence:
        counts[residue] = counts.get(residue, 0) + 1
    return {residue: count / total for residue, count in counts.items()}


def _composition_distance(left: str, right: str) -> float:
    """Manhattan distance between two amino-acid composition vectors."""
    first, second = _composition(left), _composition(right)
    residues = set(first) | set(second)
    return sum(abs(first.get(residue, 0.0) - second.get(residue, 0.0)) for residue in residues)


# The three IMiDs BINMAN's ligand table carries a CCD code for. CC-122
# (avadomide) and CC-220 (iberdomide) appear in the Sievers screen but have no
# CCD, and no SMILES for them is curated here.
IMID_CCD = {"POM": "Y70", "LEN": "LVY", "THAL": "EF2"}

# Spec 4.18 states the falsifiable prediction over "lenalidomide or
# pomalidomide", so the arm is scoped to those two. Pomalidomide is tried
# first because it is significant for 23 of the 32 degraded zinc fingers
# against lenalidomide's 8. Thalidomide has a CCD (EF2) and is deliberately
# not in this list: every thalidomide-significant row in the screen is also
# pomalidomide-significant, so including it would change no assignment while
# widening the claim past what the spec predicts.
IMID_PREFERENCE = ("POM", "LEN")


def sievers_drug_for(peptide: "Peptide") -> dict:
    """Which IMiD a degraded zinc finger should be co-folded with.

    The screen tests five IMiDs and reports which were significant per zinc
    finger, and the answer differs between them: running the whole arm under
    one drug would label a zinc finger "degraded" in a complex containing a
    drug the screen says does not degrade it. That inverts the very label the
    ROC is built on, so the drug is chosen per peptide and each matched
    control inherits its positive's drug, keeping the comparison within-drug.
    """
    significant = list((peptide.screen_drugs or {}).get("significant", []))
    chosen = next((drug for drug in IMID_PREFERENCE if drug in significant), None)
    if chosen is None:
        return {
            "drug": None,
            "ccd": None,
            "significant": significant,
            "status": (
                "unroutable: significant only for IMiDs with no CCD code "
                "(CC-122, CC-220). Spec 4.18 scopes the prediction to "
                "lenalidomide or pomalidomide, so this zinc finger falls "
                "outside the arm rather than being run under a drug the "
                "screen says does not degrade it."
            ),
        }
    return {"drug": chosen, "ccd": IMID_CCD[chosen], "significant": significant,
            "status": "routed"}


def _significant_drugs(row: dict) -> list[str]:
    return [d.strip() for d in str(row.get("drugs_significant", "")).split(";") if d.strip()]


def sievers_matched_set(negatives_per_positive: int = 4) -> dict:
    """The Sievers arm, sized for the campaign while keeping its matching.

    The screen is strongly imbalanced: 32 zinc fingers are degraded and 5,631 are
    not. That imbalance is the real result (IMiD-sensitive zinc fingers are rare),
    but a campaign budget of a few hundred pairs cannot run 5,663 peptides, and
    the whole value of this set is that its negatives came out of the same screen
    as its positives.

    So every one of the 32 positives is kept, and each is paired with the
    `negatives_per_positive` non-degraded zinc fingers closest to it in length and
    amino-acid composition. Matching rather than diversity selection is deliberate
    here: for this arm a control is useful because it resembles its positive,
    which is the opposite of what diversity selection optimises for. Spec 3.4's
    diversity reduction still applies to the rest of the library.
    """
    everything = sievers_peptides()
    all_positives = [peptide for peptide in everything if peptide.label == "degraded"]
    pool = [peptide for peptide in everything if peptide.label == "not_degraded"]

    # Drop the positives whose only significant IMiD has no CCD code, before
    # matching rather than after: a dropped positive must not consume the
    # controls that a kept positive would otherwise be matched against.
    positives = []
    dropped = []
    for peptide in all_positives:
        routing = sievers_drug_for(peptide)
        if routing["ccd"] is None:
            dropped.append({"peptide_id": peptide.peptide_id, "gene": peptide.gene,
                            "significant": routing["significant"],
                            "reason": routing["status"]})
            continue
        peptide.screen_drugs = dict(peptide.screen_drugs or {})
        peptide.screen_drugs["assigned_drug"] = routing["drug"]
        peptide.screen_drugs["assigned_ccd"] = routing["ccd"]
        positives.append(peptide)

    chosen: dict[str, Peptide] = {}
    pairings = []
    for positive in positives:
        scored = sorted(
            pool,
            key=lambda candidate: (
                abs(candidate.length - positive.length),
                _composition_distance(candidate.sequence, positive.sequence),
            ),
        )
        partners = []
        for candidate in scored:
            if candidate.peptide_id in chosen:
                continue
            chosen[candidate.peptide_id] = candidate
            candidate.notes.append(f"matched control for {positive.gene} ({positive.peptide_id})")
            candidate.parent_peptide_id = positive.peptide_id
            # The control inherits its positive's drug, so the comparison the
            # ROC makes is within-drug. A control co-folded with a different
            # IMiD than its positive would differ in two things at once.
            candidate.screen_drugs = dict(candidate.screen_drugs or {})
            candidate.screen_drugs["assigned_drug"] = positive.screen_drugs["assigned_drug"]
            candidate.screen_drugs["assigned_ccd"] = positive.screen_drugs["assigned_ccd"]
            candidate.screen_drugs["inherited_from"] = positive.peptide_id
            partners.append(candidate.peptide_id)
            if len(partners) >= negatives_per_positive:
                break
        pairings.append(
            {
                "positive": positive.peptide_id,
                "gene": positive.gene,
                "length": positive.length,
                "controls": partners,
            }
        )

    selected = positives + list(chosen.values())
    drug_counts: dict[str, int] = {}
    for peptide in selected:
        ccd = (peptide.screen_drugs or {}).get("assigned_ccd")
        if ccd:
            drug_counts[ccd] = drug_counts.get(ccd, 0) + 1
    return {
        "peptides": selected,
        "positives": len(positives),
        "controls": len(chosen),
        "pool_size": len(pool),
        "negatives_per_positive": negatives_per_positive,
        "pairings": pairings,
        "dropped_positives": dropped,
        "drug_assignment": drug_counts,
        "note": (
            f"{len(all_positives)} degraded zinc fingers in the screen, "
            f"{len(positives)} kept. The {len(dropped)} dropped are significant "
            "only for CC-122 or CC-220, which have no CCD code in BINMAN's "
            "ligand table. Spec 4.18 scopes the prediction to lenalidomide or "
            "pomalidomide, so running them under pomalidomide regardless would "
            "put a zinc finger the screen calls undegraded by that drug on the "
            "positive side of the ROC."
        ),
    }


# The substrate chain and glue CCD of each resolved benchmark deposition, and the
# accession the peptide is drawn from. Member 7 draws from CDK12 rather than
# cyclin K: CR-8 makes no contact with cyclin K in 6TD3 and 18 with CDK12, so the
# interface Delta-ipTM is meant to measure is the one CDK12 forms (D-NOB-016).
BENCHMARK_CHAINS = (
    {"index": 1, "pdb_id": "5HXB", "chain": "X", "ligand": "85C",
     "accession": "P15170", "gene": "GSPT1", "e3": "CRBN"},
    {"index": 2, "pdb_id": "5T35", "chain": "A", "ligand": "759",
     "accession": "O60885", "gene": "BRD4", "e3": "VHL"},
    {"index": 3, "pdb_id": "6BNB", "chain": "C", "ligand": None,
     "accession": "O60885", "gene": "BRD4", "e3": "CRBN"},
    {"index": 4, "pdb_id": "6H0F", "chain": "C", "ligand": "Y70",
     "accession": "Q13422", "gene": "IKZF1", "e3": "CRBN"},
    {"index": 5, "pdb_id": "5FQD", "chain": "C", "ligand": "LVY",
     "accession": "P48729", "gene": "CSNK1A1", "e3": "CRBN"},
    {"index": 6, "pdb_id": "6Q0W", "chain": "D", "ligand": "EF6",
     "accession": "Q14498", "gene": "RBM39", "e3": "DCAF15"},
    {"index": 7, "pdb_id": "6TD3", "chain": "B", "ligand": "RC8",
     "accession": "Q9NYV4", "gene": "CDK12", "e3": "DDB1"},
)


def benchmark_peptides() -> list[Peptide]:
    """One peptide per panel member, centred on its measured degron residue.

    The degron residue is read out of the deposited ternary (the substrate
    residue closest to the glue, preferring a glycine for the glycine-degron
    classes), converted into canonical numbering, and a window of the configured
    tile length is cut around it. No residue number is declared anywhere.

    Member 3 (BRD4 BD1 / CRBN / dBET) has no ligand in assembly 1 of 6BNB, so its
    window is centred on the midpoint of the observed chain and the peptide is
    flagged. Its Delta-ipTM still runs; only the crystal-derived centring is
    unavailable.
    """
    from nobble.curate import structures

    length = int(paths.thresholds()["peptide"]["tile_length"])
    half = length // 2
    peptides: list[Peptide] = []

    for member in BENCHMARK_CHAINS:
        notes = [f"benchmark panel member {member['index']}"]
        sequence_full = canonical(member["accession"])
        if not sequence_full:
            continue

        centre = None
        if member["ligand"]:
            contacts = structures.contacts_to_ligand(
                member["pdb_id"], member["ligand"], member["chain"], 5.0
            )
            glycines = [item for item in contacts if item["one_letter"] == "G"]
            chosen = (glycines or contacts or [None])[0]
            if chosen:
                try:
                    frame = numbering.resolve_frame(
                        member["pdb_id"], member["chain"], member["accession"]
                    )
                    centre = frame.to_canonical(chosen["seqid"])
                    notes.append(
                        f"centred on {member['ligand']} contact: deposited "
                        f"{chosen['seqid']}{chosen['one_letter']} at "
                        f"{chosen['min_distance']} A, canonical {centre}"
                    )
                    if frame.offset:
                        notes.append(f"numbering frame offset {frame.offset}")
                except numbering.FrameUnresolved as error:
                    notes.append(f"frame unresolved: {error}")

        if centre is None:
            summary = [
                item for item in structures.chain_summary(member["pdb_id"])
                if item["chain"] == member["chain"]
            ]
            if not summary or not summary[0]["first_seqid"]:
                continue
            observed = summary[0]
            centre = (observed["first_seqid"] + observed["last_seqid"]) // 2
            notes.append(
                "no glue present in the deposited assembly: window centred on the "
                "midpoint of the observed chain and flagged"
            )

        start = max(1, centre - half)
        end = min(len(sequence_full), start + length - 1)
        start = max(1, end - length + 1)
        window = sequence_full[start - 1 : end]
        if not window:
            continue

        peptides.append(
            Peptide(
                peptide_id=_peptide_id("benchmark", window, str(member["index"])),
                sequence=window,
                source="benchmark",
                label="degraded",
                accession=member["accession"],
                gene=member["gene"],
                start_res=start,
                end_res=end,
                degron_class=f"benchmark_{member['gene'].lower()}",
                e3_hint=member["e3"],
                notes=notes,
            )
        )
    return peptides


# --------------------------------------------------------------------------- #
# Folded-domain context (D-NOB-027)
# --------------------------------------------------------------------------- #

# A window covering at least this fraction of its parent domain is treated as
# representing the domain rather than as a slice cut out of one. Below it, the
# window cannot fold on its own and cannot reproduce an interface the intact
# domain makes.
DOMAIN_COVERAGE_SELF_SUFFICIENT = float(paths.thresholds()["substrate"]["domain_coverage_self_sufficient"])


def domain_context(accession: str | None, start: int | None, end: int | None) -> dict:
    """Is this window a linear epitope, or a slice cut out of a folded domain?

    Added after the benchmark panel made the distinction unmissable. IKZF1 is
    the only panel member whose 15-mer is not inside an annotated folded domain,
    and it is the only one whose pose the pipeline recovers: 5.0 to 5.4 angstrom
    across ten seeds, against 19 to 29 angstrom for windows cut from
    bromodomains, kinase domains and RRMs.

    The reason is structural rather than statistical. A 15-mer taken from the
    middle of a 112-residue bromodomain has no tertiary context, cannot fold,
    and therefore cannot present the surface the intact domain presents. It
    docks somewhere plausible and confident, and wrong.

    Every peptide carries this flag so a hit whose window sits inside a folded
    domain can be filtered out of a ranked view, or read with the caveat
    attached, rather than being compared like for like with a genuine linear
    degron.
    """
    from nobble.curate import interpro

    unknown = {
        "inside_folded_domain": None,
        "domains": [],
        "max_coverage": None,
        "status": "not_assessed",
    }
    if not accession or start is None or end is None:
        return unknown
    try:
        records = interpro.domains(accession)
    except Exception:                               # noqa: BLE001
        return unknown | {"status": "interpro_unavailable"}

    enclosing = [
        record for record in records
        if record["type"] == "domain"
        and record["database"] in ("interpro", "pfam")
        and record["start"] <= start and end <= record["end"]
    ]
    if not enclosing:
        return {
            "inside_folded_domain": False,
            "domains": [],
            "max_coverage": None,
            "status": "linear_or_loop_epitope",
        }

    window = end - start + 1
    coverage = max(window / record["length"] for record in enclosing)
    return {
        "inside_folded_domain": coverage < DOMAIN_COVERAGE_SELF_SUFFICIENT,
        "domains": [
            {
                "accession": record["accession"],
                "name": record["name"],
                "start": record["start"],
                "end": record["end"],
                "length": record["length"],
                "coverage": round(window / record["length"], 3),
            }
            for record in enclosing[:3]
        ],
        "max_coverage": round(coverage, 3),
        "status": (
            "slice_of_folded_domain" if coverage < DOMAIN_COVERAGE_SELF_SUFFICIENT
            else "covers_its_domain"
        ),
    }


def annotate_domain_context(peptides: list[Peptide]) -> list[Peptide]:
    """Attach the folded-domain verdict to every peptide, cached per protein."""
    cache: dict[tuple, dict] = {}
    for peptide in peptides:
        key = (peptide.accession, peptide.start_res, peptide.end_res)
        if key not in cache:
            cache[key] = domain_context(*key)
        context = cache[key]
        peptide.domain_context = context
        if context.get("inside_folded_domain"):
            best = context["domains"][0] if context["domains"] else {}
            peptide.notes.append(
                "window lies inside the folded domain "
                f"{best.get('accession', '?')} and covers only "
                f"{context['max_coverage']:.0%} of it: it cannot fold alone, so a "
                "failure to reproduce a domain-mediated interface is expected "
                "(D-NOB-027)"
            )
    return peptides


def benchmark_substrate_constructs() -> list[dict]:
    """The substrate construct each benchmark member should actually use.

    A member whose epitope is a slice of a folded domain gets the whole domain;
    one whose epitope is linear keeps its 15-mer. The token cost is computed
    against the tier-1 cap so the trade is explicit rather than discovered at
    run time. See D-NOB-027 and FINDINGS.md F6.
    """
    from nobble import paths
    from nobble.curate import constructs as C
    from nobble.curate import ligands as L
    from nobble.curate import manifest as M

    cap = int(paths.thresholds()["manifest"]["token_cap_tier1"])
    ligand_map = L.benchmark_ligands()
    peptide_by_member = {
        (item.gene, item.e3_hint): item
        for item in annotate_domain_context(benchmark_peptides())
    }

    plan = []
    for member in BENCHMARK_CHAINS:
        peptide = peptide_by_member.get((member["gene"], member["e3"]))
        if peptide is None:
            continue
        context = peptide.domain_context or {}
        construct_name = M.E3_TO_CONSTRUCT.get(member["e3"])
        receptor_residues = (
            C.CONSTRUCTS[construct_name].residue_count() if construct_name else 0
        )
        ligand = ligand_map.get(member["index"])
        ligand_atoms = (ligand.heavy_atoms or 0) if ligand else 0

        if context.get("inside_folded_domain") and context.get("domains"):
            domain = context["domains"][0]
            substrate_length = domain["length"]
            substrate = {
                "mode": "folded_domain",
                "accession": peptide.accession,
                "interpro": domain["accession"],
                "start": domain["start"],
                "end": domain["end"],
                "length": substrate_length,
                "reason": (
                    f"the 15-mer covers only {context['max_coverage']:.0%} of "
                    f"{domain['accession']} and cannot fold alone"
                ),
            }
        else:
            substrate_length = peptide.length
            substrate = {
                "mode": "peptide_15mer",
                "accession": peptide.accession,
                "start": peptide.start_res,
                "end": peptide.end_res,
                "length": substrate_length,
                "reason": "the epitope is linear, so a 15-mer is the right construct",
            }

        tokens = receptor_residues + substrate_length + ligand_atoms
        # Spec 1.1 declares two exceptions, both receptors that cannot be
        # truncated. D-NOB-027 adds a third on the same grounds applied to a
        # substrate: CR-8 is recognised through CDK12's folded kinase domain,
        # and a kinase domain cut in half is not a kinase domain.
        declared = construct_name in {"VHL_VCB", "DCAF15_DDB1_DDA1"} or (
            substrate["mode"] == "folded_domain"
            and substrate["length"] >= FOLDED_DOMAIN_EXCEPTION_MIN_LENGTH
            and tokens > cap
        )
        declared_reason = None
        if declared and construct_name not in {"VHL_VCB", "DCAF15_DDB1_DDA1"}:
            declared_reason = (
                f"substrate is a {substrate['length']}-residue folded domain that "
                "cannot be truncated without destroying it (D-NOB-027)"
            )
        plan.append({
            "member": member["index"],
            "gene": member["gene"],
            "e3": member["e3"],
            "receptor_construct": construct_name,
            "receptor_residues": receptor_residues,
            "substrate": substrate,
            "ligand_heavy_atoms": ligand_atoms,
            "tokens": tokens,
            "cap": cap,
            "within_cap": tokens <= cap,
            "declared_exception": declared,
            "declared_reason": declared_reason,
            "acceptable": tokens <= cap or declared,
        })
    return plan


# A C2H2 zinc finger is held in its fold by a single Zn(2+) ion tetrahedrally
# coordinated by two cysteines and two histidines. The CCD code is ZN.
STRUCTURAL_ZINC_CCD = "ZN"


def requires_structural_zinc(peptide: "Peptide") -> dict:
    """Whether this peptide needs a Zn(2+) ion to fold as the domain it is.

    The Sievers arm submits whole zinc fingers rather than tiles, precisely
    because a zinc finger is a folding unit. The ion is what makes it one: a
    C2H2 finger with no zinc is not a domain with a missing accessory, it is
    a disordered 23-mer, and co-folding it against CRBN would measure the
    wrong thing in the arm that carries the headline ROC.

    The 15-mer benchmark degrons are deliberately excluded even when they
    happen to carry two cysteines. IKZF1's degron window is a fragment of
    zinc finger 2 whose histidines fall outside it, so there is no
    coordination site to complete, and bench04 scored the best Delta-ipTM in
    the panel without one. The test is the complete motif, not the source.
    """
    # A composition-matched scramble of a zinc finger carries the same two
    # cysteines and histidines in shuffled positions, so it cannot form a
    # canonical site. It still gets the ion. The scramble's job is to differ
    # from its positive in exactly one variable, the residue order, and
    # withholding the zinc would make it differ in two: a negative that
    # fails for the wrong reason tells you nothing about the positive.
    # An explicit decision wins over inference. A design variant inherits
    # its parent's cofactor: an alanine scan of a zinc finger mutates the
    # coordinating cysteines and histidines, so inferring from the variant's
    # own sequence would drop the ion at exactly C3A and C6A, the positions
    # the scan most wants to measure. The lift there would be large, would
    # look like "this position is critical", and would be reporting the
    # missing zinc rather than the substitution (D-NOB-038).
    if peptide.cofactor is not None:
        return dict(peptide.cofactor)

    domain_classes = ("zinc_finger", "scramble_of_zinc_finger")
    if peptide.degron_class not in domain_classes:
        return {"required": False, "reason": "not a zinc-finger domain"}
    sequence = peptide.sequence or ""
    cysteines = sequence.count("C")
    histidines = sequence.count("H")
    if cysteines >= 2 and histidines >= 2:
        return {
            "required": True,
            "ccd": STRUCTURAL_ZINC_CCD,
            "reason": (
                f"complete C2H2 coordination site present ({cysteines} Cys, "
                f"{histidines} His): the fold depends on the ion"
            ),
        }
    return {
        "required": False,
        "reason": (
            f"incomplete coordination site ({cysteines} Cys, {histidines} His): "
            "no zinc added rather than a zinc with nothing to hold it"
        ),
    }
