# NOBBLE decision log

Seeded from BUILD_SPEC.md Section 8. Decisions D-NOB-008 onward are made during
the unattended build: each records the decision, the alternatives, the reason and
how to reverse it.

| ID | Decision | Date |
|---|---|---|
| D-NOB-001 | Tier 1 runs ternaries and retains full scoring, rather than binary-only triage with ternaries reserved for survivors | 2026-11-03 |
| D-NOB-002 | Tier B (ligandable unproven) is included in the first campaign rather than deferred until Tier A calibration completes | 2026-11-03 |
| D-NOB-003 | GSPT1 and BRD4 are mandatory benchmark panel members, as community standards. BRD4 runs on both VHL and CRBN arms | 2026-11-03 |
| D-NOB-004 | Token cap of 400 for tier 1, with VHL (VCB trimer) and DCAF15 (DDB1 BPA-BPC + DDA1) as declared structural exceptions | 2026-11-03 |
| D-NOB-005 | Affinity head is recorded for the small-molecule chain only and is never a ranking key. No peptide affinity is reported | 2026-11-03 |
| D-NOB-006 | Composite weights are fitted on the benchmark panel and the Sievers matched set, not hand-set | 2026-11-03 |
| D-NOB-007 | NOBBLE is a BoltzMaker campaign preset plus a fifth BINMAN module, not a standalone stack. Shared code is widened in place in those repositories, never forked | 2026-11-03 |

---

## D-NOB-008: consume BINMAN's stores as SQLite plus TSV, not DuckDB

**Date:** 2026-11-03

**Decision.** Spec 2 states NOBBLE consumes "BINMAN's DuckDB store". BINMAN has no
DuckDB file: it ships `data/atlas/binman.sqlite` (12 tables, the serve-time atlas,
including `bridge` at 285,996 rows and `ligase` at 650 rows, both exactly as the
spec expects) and the curated source datasets as TSV under `data/validation/`.
NOBBLE reads the SQLite atlas read-only (`mode=ro`) and the TSVs directly, and
keeps its own analytical store at `data/nobble.duckdb`.

**Alternatives.** Convert BINMAN's atlas to DuckDB first (adds a copy that can
drift from the source of truth); or ask Marc (forbidden in unattended mode).

**Reason.** The spec's intent is "do not re-acquire, read what BINMAN already
curated". The file format was an incidental assumption in the spec. Reading the
real store read-only honours the intent and cannot corrupt BINMAN.

**Reversal.** Change `nobble/curate/binman_store.py`; the table and column names
are unchanged either way.

---

## D-NOB-009: benchmark resolver matches composite accessions by token, and uses PROTAC-DB for the bivalent arms

**Date:** 2026-11-03

**Decision.** The benchmark resolver (spec 3.1) splits MGTbind's
`protein_*_uniprot_id` on underscore and matches by set membership, and it
resolves the two BRD4 PROTAC arms from `protacdb_protacs` rather than MGTbind.

**Reason.** Two findings from the real data, both of which make the literal spec
reading fail:

1. MGTbind encodes multi-protein receptors as underscore-joined composites
   (`ELOB_ELOC_VHL`, `DDB1_CRBN`, `DDB1_DCAF15_DDA1`, `Q9NYV4_O75909`). Exact
   accession equality returns zero rows for every panel member whose receptor is
   a complex, which is most of them. Token matching resolves 5 of 7 immediately,
   and as a side effect encodes the VCB and DCAF15 trimer exceptions of spec 1.1
   directly from the deposited stoichiometry rather than by assertion.
2. MGTbind is a molecular-glue database and deliberately carries no PROTACs: MZ1,
   dBET, ARV and AT1 all return zero rows. `protacdb_protacs` carries both, with
   PDB identifiers, which is consistent with spec 2.1 listing PROTAC-DB as the
   bivalent class source.

Resolved panel: GSPT1/CRBN/CC-885 **5HXB**; BRD4/VHL/MZ1 **5T35**;
BRD4-BD1/CRBN/dBET57 **6BNB**; IKZF1/CRBN **6H0F** and five others;
CK1alpha/CRBN/lenalidomide **5FQD**; RBM39/DCAF15/indisulam **6PAI** and six
others; cyclin K/DDB1/CR-8 **6TD3** and 29 others. All seven resolve, so the
Phase 1 gate is satisfiable.

**Alternatives.** Hardcode the accessions (spec 3.1 forbids it, and it is the
named source of silent error); or query RCSB for every pair (slower, and the
local data already answers it).

**Reversal.** `nobble/curate/benchmark.py`, functions `_accession_tokens` and
`resolve_panel`.

---

## D-NOB-010: Degronopedia and ProtCID are unavailable, so the furniture veto is reported as not computed

**Date:** 2026-11-03

**Decision.** BINMAN's own Gate G7 records that `degronopedia` and
`protcid_interfaces` could not be acquired automatically (both publish through a
JavaScript front end with no bulk-export endpoint). NOBBLE therefore:

- assigns degron motif classes from `degron.motif_family` in BINMAN's atlas and
  the Koren 2018 C-degron rules, not from Degronopedia;
- computes every other score, and reports the ProtCID packing-only veto of spec
  4.7 as `furniture: null` with status `not_computed: protcid_unavailable`,
  never as `false`.

**Reason.** Spec 4.7 makes the furniture veto a flag, not a ranking key, so its
absence degrades one column rather than blocking the campaign. Recording it as
`false` would assert a check that was never run, which is the failure mode the
spec's own validation section is written against.

**Alternatives.** Substitute a hand-written packing control (BINMAN spec 4.1b
forbids this, for good reason); block the build (disproportionate for a flag).

**Reversal.** Place the two files under `BINMAN/data/validation/raw/` and re-run
BINMAN's `pipeline/acquire_validation.py --refresh`, then NOBBLE's scoring stage.

---

## D-NOB-011: nobble.mdeller.com resolves but is not yet serving NOBBLE

**Date:** 2026-11-03

**Decision.** Recorded as a Gate G3 item rather than treated as done.

**Finding.** `nobble.mdeller.com` resolves to the droplet (45.55.102.228, the same
host as binman.mdeller.com) and answers HTTP 200 on port 80, but with nginx's
default welcome page: there is no NOBBLE vhost. HTTPS fails certificate
verification because the only certificate presented covers
`alphabetti.mdeller.com`. So the DNS half of "live" is done and the server half
is not.

**Consequence.** The deploy script is written but not run. G3 needs an nginx
vhost for the subdomain and a certbot certificate, both root actions on the
droplet.

**Reversal.** Not applicable: this is a finding, not a choice.

---

## D-NOB-012: deposited and canonical residue numbering are different frames, and every cross-frame comparison goes through an explicit mapping

**Date:** 2026-11-03

**Decision.** `nobble/curate/numbering.py` anchors each deposited chain in its
canonical UniProt sequence and returns the offset. Nothing in NOBBLE compares a
deposited residue number with a BINMAN residue number directly.

**Why this is not housekeeping.** The Phase 1 degron gate failed on GSPT1 first
time. The cause was not BINMAN's Degron Scan. 5HXB numbers its GSPT1 chain
440 to 634, in the frame of the 637-residue isoform; UniProt canonical P15170 is
499 residues, and so is the AlphaFold model the scan ran on. The offset is 138.
The literature degron glycine at 575 is canonical residue **437**, which is
exactly the tip residue of the scan's second-ranked GSPT1 hairpin
(419-442, tip 437G, pLDDT 86.5, geometry score 0.694).

So the scan was right and the comparison was wrong. Measured naively, a correct
scan looks like a miss on the single highest-value benchmark member in the panel,
and the spec's instruction would have sent the build off to fix a scan that has
no bug. Hardcoding either number would have made the pipeline silently wrong in
the other frame.

GSPT1 is the only panel member with a non-zero offset: the other six already
agree with canonical numbering, which is exactly what makes this trap dangerous.

**Reversal.** Not a preference: the mapping is required for correctness.

---

## D-NOB-013: the DDB1 receptor for benchmark member 7 is BPC alone, chosen by measurement

**Date:** 2026-11-03

**Decision.** Benchmark member 7 (cyclin K / DDB1 / CR-8) uses DDB1's C-terminal
beta-propeller (BPC, IPR004871, 790-1099) as the whole receptor.

**Reason.** CR-8 contacts DDB1 only at residues 907, 908, 909, 928 and 947, all
inside BPC, with no BPA or BPB atom within 5 A (measured on 6TD3). Dropping both
other propellers costs nothing structurally and brings the job to 355 tokens,
inside the 400-token tier-1 cap, so this member needs no declared exception.
Carrying BPA as well would have put it at 689 tokens and forced a third
exception for no structural gain.

**Reversal.** `nobble/curate/constructs.py`, the `DDB1_BPC` construct.

---

## D-NOB-014: FEM1B's substrate-binding domain is ankyrin repeats, not TPR

**Date:** 2026-11-03

**Decision.** The FEM1B construct is the N-terminal ankyrin-repeat region
(IPR036770, residues 5-301, 297 aa).

**Reason.** Spec 1.1's token table calls this construct "FEM1B TPR (~360 aa)".
InterPro annotates no TPR domain on Q9UK73 at all: FEM1B is an ankyrin-repeat
protein and recognises its C-degron substrates through those repeats. The
residue count the spec gives (~360) is close to the ANK region's 297, so the
intent is clear and only the domain name was wrong.

**Reversal.** `nobble/curate/constructs.py`, `FEM1B_ANK`.

---

## D-NOB-015: DCAF15 measures 1,229 tokens, not the ~900 the spec estimates

**Date:** 2026-11-03

**Finding, recorded rather than worked around.** Spec 1.1 states that a DDB1
BPA-BPC truncation keeps the DCAF15 job "under 1,000 tokens" and estimates ~900.
Built from real InterPro boundaries the construct is 1,184 residues (DCAF15
35-259 and 387-599, DDB1 BPA 15-348 and BPC 790-1099, DDA1 1-102), which with a
15-mer and a 30-atom ligand is **1,229 tokens**: roughly 37 per cent over the
stated figure and over the 1,000 the spec treats as the ceiling for it.

**Decision.** Keep the construct as specified and carry the true number, because
spec 1.1's justification is structural rather than budgetary: DCAF15 does not
engage RBM39 without DDB1 and DDA1. The declared exception stands, at its
measured size. The campaign sizer treats DCAF15 jobs at their real token cost,
so the 48-hour budget is computed from 1,229 and not from 900. If Phase 2's
measured throughput makes this member unaffordable, the reduction to try first is
DDB1 BPC alone, by the same measurement that settled D-NOB-013.

**Reversal.** Not a choice to reverse: the figure is measured. The construct can
be narrowed as described above.

---

## D-NOB-016: for benchmark member 7 the peptide comes from CDK12, because cyclin K does not touch the glue

**Date:** 2026-11-03

**Finding.** In 6TD3, CR-8 makes **no** contact with cyclin K within 5 A (zero
atoms), while making 18 contacts with CDK12 across residues 732 to 877 and five
with DDB1 BPC. The ternary interface is DDB1:CR-8:CDK12.

**Decision.** The member keeps its spec label (cyclin K is what is degraded, and
that is the readout the literature reports), but the peptide chain submitted to
Boltz is drawn from the CDK12 interface region, since that is the chain that
forms the interface Delta-ipTM is supposed to measure. Submitting a cyclin K
peptide would measure an interface that does not exist in the crystal and would
score the benchmark's most unusual member against the wrong chain.

**Reversal.** `nobble/curate/benchmark.py`, panel member 7's substrate accession.
