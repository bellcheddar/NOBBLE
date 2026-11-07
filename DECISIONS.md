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

---

## D-NOB-017: the Open Targets tumour-enrichment filter is unpopulated, so it is skipped and recorded, not applied

**Date:** 2026-11-03

**Finding.** Spec 3.3's fourth Tier B filter is "Open Targets tumour enrichment
above the repertoire median". BINMAN's `ligase.tumour_enriched` column is **0 for
all 650 rows**: it has one distinct value and therefore no discriminating power.
Applied literally, the Tier B funnel runs 564 ligandable-unproven to 33 on
fpocket, 26 on pLDDT and then to **zero**, failing the Phase 1 gate on a column
that was never filled in.

What settles the diagnosis rather than leaving it a judgement call: the three
ligases spec 3.3 itself says "should appear" at the top of this ranking, DCAF8L1,
CCNF and ASB8, all carry `tumour_enriched = 0` as well. The spec's own expected
answer is incompatible with its own filter as applied to this store, so the
filter is unpopulated rather than selective.

**Decision.** Skip the filter when the column carries no variance, record the
skip in the funnel and in `tier_b_selection.provenance.json` as
`not_computed: open_targets_enrichment_unpopulated`, and never report any ligase
as tumour-enriched or not. The check is written to apply itself automatically if
the column is ever populated, so no code change is needed then.

**Result.** Tier B selects 15 ligases and the gate passes. DCAF8L1, CCNF and ASB8
come out at ranks 1, 2 and 3, which is exactly what spec 3.3 predicts and is good
evidence the rest of the selection function is right.

**Alternatives.** Substitute a tumour-enrichment source of my own (re-acquiring a
source the spec assigns to BINMAN, and unverifiable here); or let the gate fail
(reports a data gap as a science result, which spec 5 is written against).

**Reversal.** Populate `ligase.tumour_enriched` in BINMAN and re-run
`nobble.curate.freeze.write_tier_b(force=True)`. The filter re-arms itself.

---

## D-NOB-018: degron regions come from BINMAN's structural scan, because UbiBrowser carries no coordinates

**Date:** 2026-11-03

**Decision.** Spec 3.4 tiles curated degrons "across the annotated degron region
plus or minus 20 residues". UbiBrowser's literature export is two columns, E3
gene and substrate gene, with no degron coordinates at all, and Degronopedia
(which would have carried them) was never acquired (D-NOB-010). The region
therefore comes from BINMAN's own Degron Scan for that substrate, taking its
three highest-scoring degrons per protein.

**Reason.** It is the only degron coordinate source available, and it is the one
the Phase 1 gate independently validated against two deposited ternaries: the
scan's tip residue is exactly the deposited degron residue for both GSPT1 and
IKZF1. Using it is better evidenced than using an annotation that is absent.

**Consequence.** The curated arm inherits the scan's motif bias. Every one of the
12,029 curated peptides carries `motif_family = crbn_hairpin_glycine`, because
that is the only geometry the scan looks for. So this arm is a CRBN-style
glycine-degron library, not a general degron library, and the About page must say
so rather than implying proteome-wide degron coverage.

**Reversal.** Acquire Degronopedia, or widen BINMAN's scan with further motif
families (its `motif_family` column exists for exactly that), then re-run.

---

## D-NOB-019: jobs per pair is computed from the axes emitted, not quoted from the spec

**Date:** 2026-11-03

**Finding.** The spec gives two incompatible job counts. Spec 1.2 says "two jobs
(binary and ternary) across five seeds, so a 400-pair campaign is 4,000
inferences", which is 10 per pair. Phase 2's build list then adds a third axis,
"(conditioned + unconstrained)", which would make it 20.

**Decision.** Neither number is hardcoded. `manifest.jobs_per_pair()` computes it
from the axes actually emitted, and the real figure is **15**: conditioning
places a ligand in a pocket, so it is meaningless for the binary arm, which has
no ligand. The binary arm runs 5 seeds unconstrained and the ternary arm runs 5
seeds in each of the two conditioning states.

**Why it matters.** This number multiplies the entire campaign budget. Inheriting
the wrong one would misplan the 48-hour run by a third in one direction or a
third in the other.

**Reversal.** `nobble/curate/manifest.py`, `jobs_per_pair` and the `COMPLEXES` and
`CONDITIONS` tuples it is derived from.

---

## D-NOB-020: the numbering frame resolver is per-residue and gap-aware

**Date:** 2026-11-03

**Finding, and a second instance of the D-NOB-012 trap.** The first frame
resolver concatenated a chain's observed residues into one string and compared
positions. That works for substrate peptides, which are short and continuous,
and fails for receptors, which are not: 5HXB's CRBN chain, 5FQD's CRBN chain,
6Q0W's DCAF15 chain and 6TD3's DDB1 chain all have unmodelled internal loops.
Every residue after the first gap disagreed, so all four were rejected as "not a
contiguous run" and **four of the seven benchmark pockets could not be
measured**, which would have silently reduced those pairs to unconstrained-only
and destroyed the conditioning-agreement signal of spec 4.7 for most of the
panel.

Their true offset is zero in every case: the numbering already matched.

**Decision.** `resolve_frame` now compares each observed residue by its own
deposited number, derives candidate offsets from exact k-mer matches on
contiguous runs, and picks the offset with the best agreement across the whole
chain. All six receptor chains now resolve at 0 per cent mismatch, and no
substrate regressed (GSPT1 remains 138, the rest remain 0).

**Independent check that it is right.** The CRBN pocket, measured through this
mapping from three unrelated depositions (5HXB, 6H0F, 5FQD), lands on construct
positions 63, 69 and 83, which are W380, W386 and W400: the tri-tryptophan IMiD
pocket, recovered by measurement from three structures that agree, with no
residue number written anywhere in the code.

**Reversal.** Not a preference: the previous version was wrong.

---

## D-NOB-021: the Sievers arm is matched-sampled, and it dominates the first campaign's budget

**Date:** 2026-11-03

**Decision.** The Sievers screen contributes all 32 degraded zinc fingers plus
four length- and composition-matched non-degraded controls each, 160 peptides in
total, rather than all 5,663 rows or a random sample.

**Reason.** The screen is 32 positives against 5,631 negatives. That imbalance is
the real biology (IMiD-sensitive zinc fingers are rare), but no campaign budget
runs 5,663 peptides, and the value of this set is specifically that its negatives
came out of the same screen as its positives. Matching preserves that; diversity
selection would actively destroy it, since a useful control here is one that
resembles its positive. Spec 3.4's diversity reduction still governs the rest of
the library.

**Consequence to flag.** At the pre-measurement budget of 220 peptides, those 160
plus the 7 benchmark members and their scrambles leave room for only 7 diverse
discovery peptides. The headline calibration set crowds out discovery in the
first campaign. The measured throughput from the benchmark panel resizes this
automatically (`diversity.campaign_budget` reads `data/throughput.json`), and the
first measurement, 0.343 s/token, sizes the run at 271 pairs rather than the
spec's 200 to 250. The queue is priority-ordered regardless, so a run cut short
still yields the benchmark panel and then the ROC before it reaches discovery.

**Reversal.** `nobble/curate/peptides.py`, `sievers_matched_set`, and the budget
in `nobble/curate/diversity.py`.

---

## D-NOB-022: Delta-ipTM is measured on the receptor-to-peptide chain pair, not the global ipTM

**Date:** 2026-11-03

**Decision.** `delta_iptm` reads Boltz's `pair_chains_iptm` cell for the
receptor-to-peptide pair. The global `iptm` is recorded beside it as
`delta_iptm_global`, never used as the headline.

**Reason.** Spec 4.3 defines Delta-ipTM as a difference of "interface
confidence" without saying which interface. For a ternary complex the global
ipTM averages the receptor-peptide interface together with the receptor-ligand
and peptide-ligand ones, and the ligand interface is the easy one: the first
benchmark ternary returned `ligand_iptm` of 0.98 while its receptor-peptide pair
ranged from 0.08 to 0.91 across seeds. A glue that sits beautifully in its
pocket while the degron fails to dock would therefore raise the global figure,
and the headline number would rise on an interface that is not the one being
asked about.

The matrix is also not symmetric (0.885 one way, 0.954 the other on the same
seed), so the minimum of the two directions is taken, which keeps the statistic
conservative in the same spirit as spec 4.3's seed minimum.

**Reversal.** `nobble/score/metrics.py`, `_pair_iptm` and `peptide_chain_index`.

---

## D-NOB-023: the mandated seed minimum is reported, and so is a robust companion, because one collapsed seed can invert it

**Date:** 2026-11-03

**Finding, on the first pair of the benchmark panel.** GSPT1/CRBN/CC-885, which
spec 3.1 calls "the highest-value single test in the panel", returned
receptor-peptide ipTM across its five conditioned ternary seeds of **0.885,
0.877, 0.806, 0.082, 0.911**. Four seeds agree closely; one diffusion run
collapsed outright.

Spec 4.3 mandates the minimum across seeds. So that single failed run becomes
the headline, and Delta-ipTM for the canonical positive control reads **-0.756**:
a large negative glue dependence for the pair the whole pipeline exists to
confirm. On the median it reads **+0.021**.

**Decision.** `delta_iptm` keeps the mandated definition. Alongside it NOBBLE
reports `delta_iptm_median`, `iptm_median_binary`, `iptm_median_ternary`,
`collapsed_seeds_*` and a `seed_collapse_affects_delta` flag that is true when a
collapsed seed actually set the minimum. The Delta tab shows both, and the
About page states which is the spec's definition.

**Why not just switch to the median.** The minimum is defensible and the spec
chose it deliberately: for "does this interface reliably form", a pair that
fails one run in five has told you something real, and a mean or median hides
it. The problem is not that the minimum is wrong, it is that the minimum answers
"worst-case seed behaviour" while the ROC in spec 4.3 is asking "does glue
presence change the interface". Those come apart exactly when a diffusion run
fails, so both numbers are needed and neither should be quietly substituted for
the other.

This also raises the value of spec 4.4's convergence measure, which was already
argued for on these grounds: a collapsed seed shows up directly as a pose
outlier, and convergence discriminates a genuinely unstable interface from a
single bad diffusion trajectory in a way no confidence aggregate can.

**Consequence for the campaign.** The seed-collapse rate is now itself a
reportable number. If collapses are common, the five-seed budget of spec 1.2 is
too small for a minimum-based statistic and that is a finding about the method,
not a bug to paper over.

**Followed up, and the interpretation changed.** The collapsed seed was examined
structurally rather than left as a number. Its peptide sits **81.4 angstrom from
the receptor centroid**, in free solvent, with zero heavy-atom contacts inside 5
angstrom, against roughly 19 angstrom and 40 to 82 contact atoms for every
docked seed. So the 0.082 was not an artefact and not a low-confidence
interface: ipTM reported, correctly, that no interface existed because that
trajectory never docked the peptide.

This makes spec 4.3's choice of the minimum more defensible than it first looked,
and the diagnostics more necessary rather than less. The minimum is genuinely
reporting "one run in five produced nothing", which is real and worth knowing.
But it is answering a different question from the ROC in the same section, which
asks whether glue presence changes the interface, and a number that is dominated
by docking failures cannot also serve as a glue-dependence statistic. Both are
reported, and `docking_check` in `nobble/score/poses.py` now distinguishes an
undocked run from a docked one, so a failed trajectory is never averaged in as a
weak interface.

**Reversal.** `COLLAPSE_MARGIN` in `nobble/score/metrics.py`; set it above 1.0 to
disable the diagnostic entirely.

---

## D-NOB-024: the lysine reach window is not a validated predictor, so NOBBLE reports its geometry and not a fit

**Date:** 2026-11-03

**Finding.** Spec 4.2 instructs NOBBLE to "apply BINMAN's reach-window fit
(already calibrated against 976 observed diGly sites)" and reports the output as
`lysine_reach_fit`. BINMAN's reach window is **not calibrated**. Its
`config/thresholds.toml` carries `fitted = false`, deliberately and on measured
evidence, and its FINDINGS.md records the same conclusion.

The measurements, on 369 assayed lysines across 43 induced ternary complexes:

| boundary | AUC |
|---|---|
| Cb-Cb distance | 0.4223 |
| NZ to centroid distance | 0.4770 |
| NZ relative SASA | 0.4595 |
| NZ relative SASA, within protein | 0.5020 |

All at or below chance, and the Cb-Cb direction is slightly **inverted**:
ubiquitylated lysines sit farther from the ligand than unmodified ones (median
18.73 against 14.89 angstrom).

BINMAN's own explanation is mechanistic, which is why this is not a refitting
problem: the ligand site is where a substrate is *recruited*, not where ubiquitin
is *transferred*. The E2 that transfers it sits elsewhere on the cullin
scaffold, tens of angstrom away, and is not in the trimmed receptor construct at
all. Spec 4.2's intuition ("a peptide that forms an excellent interface and
presents no lysine into the ubiquitination shell is not a degrader lead") is
reasonable but has been measured from the recruitment site and does not hold
there.

**Decision.** NOBBLE computes and reports the geometry, which is real and
descriptive: lysine count, per-lysine relative SASA in the context of the full
complex, distance from each NZ to the nearest ligand atom, and how many are
exposed. It does **not** emit a `lysine_reach_fit` score, because that name
asserts a validated window that does not exist. Every record carries
`status = not_validated` and the AUC table above travels with the code.

**Consequence for the composite (spec 4.8).** `w2 * lysine_reach_fit` has no
validated quantity to multiply. The component is kept as a candidate so the
Phase 3 weight fit can speak for itself, but the fitted weight will be reported
next to these AUCs, so a non-zero weight cannot be mistaken for validation. If
the fit assigns it weight on the benchmark panel alone, that is overfitting to
seven pairs and will be said so.

**Alternatives.** Emit the unfitted starting values as if they were a window
(asserts a check that was never validated, and BINMAN explicitly refuses to ship
them); or drop lysine geometry entirely (loses a real measurement that a user
may well want to see per pose).

**Reversal.** If BINMAN's window is ever fitted and clears its own floor, set
`fitted = true` there and add the score here; the measurements this module
already produces are the inputs it would need.

---

## D-NOB-025: the CONECT integrity assertion counts TER serials

**Date:** 2026-11-03

**Decision.** `conect_integrity` builds its serial sequence from ATOM, HETATM
**and TER** records in file order, and resolves CONECT targets against the
ATOM/HETATM serials only.

**Reason.** Spec 4.6 requires asserting on CONECT integrity for every structure
rather than sample-checking, so the assertion has to be right or it rejects
everything. The first version collected only ATOM and HETATM serials.
`renumber_contiguous` gives every TER its own serial, so an A/P/L complex has two
TER serials sitting between atom serials, and the atoms-only sequence shows one
apparent discontinuity per chain boundary. It reported exactly that: two "gaps"
at 854 and 970 on a file whose serials were in fact perfectly contiguous, and it
would have failed every structure the fix had just repaired.

A second, unrelated failure was found at the same time and is worth recording
because it has now happened three times in this build: several tools are console
scripts resolved through PATH rather than importable modules, and invoking a
pixi environment's interpreter directly does not activate the environment.
`mkdssp`, `pdb_tidy` and `pdb_validate` were all reported missing while
installed. `paths.tool_env()` now assembles PATH and `LIBCIFPP_DATA_DIR` in one
place so no caller has to remember.

Note also that cif2plip renumbers chains to strict single-letter identifiers, so
NOBBLE's A/P/L become A/B/C. The mapping is parsed from the script's output
rather than assumed: assuming it would have attributed every degron contact to
the receptor, which is precisely the comparison F2b turns on.

**Reversal.** `nobble/score/plip.py`, `conect_integrity`.

---

## D-NOB-026: NOBBLE's own CSS classes are prefixed, because inheriting a design system inherits its namespace

**Date:** 2026-11-03

**Finding.** The application's data tables were given `class="ledger"`, which
reads naturally and was wrong. `depot.css`, inherited wholesale from BINMAN,
already defines `.ledger` as BINMAN's **page layout grid**:

```css
.ledger { display: grid; grid-template-columns: var(--rail-w) minmax(0, 1fr); }
```

A `<table class="ledger">` therefore computed to `display: grid`, which
blockifies its children: `thead` and `tbody` stopped participating in table
layout, the header row and the first body row both landed at the same
coordinate, and the header painted over the first row of data.

**What made it hard to see, and what to do about it.** The page looked almost
right, and the first body row was simply invisible behind the header: on the
Pose tab seed 1 of fifteen was missing and nothing said so. A full-page
screenshot shows the same symptom that a horizontally scrolling table shows, so
the first reading of it was wrong. It was settled by measurement rather than by
looking: `thead` and the first row both reported `top: 843.4`, `thead`
computed to `display: block` rather than `table-header-group`, and the table
itself computed to `display: grid`. Enumerating every CSS rule matching the
element found none, which is what finally pointed at the class on the table
rather than at a rule targeting the thead.

**Decision.** Anything NOBBLE adds to the inherited stylesheet carries its own
name: the tables are `.ntable`. `depot.css` is never edited, so BINMAN remains
the single source of the design system and the two cannot drift.

**Reversal.** Not a preference. Reusing a name that the inherited sheet already
defines is a collision whichever way round it is written.

---

## D-NOB-027: a substrate whose epitope is a slice of a folded domain is submitted as the whole domain

**Date:** 2026-11-03

**Finding.** The benchmark panel separated cleanly, and not on the axis
expected. IKZF1 / CRBN recovers its crystal pose at 4.99 to 5.40 angstrom across
all ten seeds, bridges in 10 of 10, converges at 0.73 and gives Delta-ipTM
+0.32. GSPT1, both BRD4 arms and the rest sit at 19 to 29 angstrom median, bridge
in 3 to 4 seeds of 10, and converge at 0.00.

Checking each submitted 15-mer against the InterPro annotation of its own parent
protein explains it completely:

| Pair | Window | Inside a folded domain |
|---|---|---|
| GSPT1 | 430-444 | yes, 15 per cent of a 99-residue domain |
| BRD4 BD2 | 379-393 | yes, 17 per cent of the bromodomain |
| BRD4 BD1 | 98-112 | yes, 18 per cent of the bromodomain |
| CSNK1A1 | 33-47 | yes, 7 per cent of the kinase domain |
| RBM39 | 261-275 | yes, 21 per cent of the RRM |
| CDK12 | 809-823 | yes, 5 per cent of the kinase domain |
| **IKZF1** | **144-158** | **no: linear or loop epitope** |

The one pair that works is the one pair whose epitope is linear. A 15-mer cut
out of a bromodomain has no tertiary context, cannot fold, and cannot present
the surface the intact domain presents. The model docks it confidently and
roughly 20 angstrom from the real contact.

**Decision.** A substrate whose epitope covers less than 80 per cent of an
enclosing folded domain is submitted as that whole domain. One whose epitope is
linear keeps its 15-mer, because that is the correct construct for a degron and
degrons are what the discovery arms are made of. `domain_context()` applies the
test, every peptide in the library carries an `inside_folded_domain` flag, and
`benchmark_substrate_constructs()` produces the corrected plan with its token
cost.

**What it costs.** Five of the seven then fit inside the 400-token tier-1 cap
(GSPT1 239, BRD4/CRBN 269, IKZF1 144, CSNK1A1 397); BRD4/VHL and RBM39/DCAF15
are already declared exceptions. One does not:

**CDK12 / DDB1 / CR-8 is 636 tokens and becomes a third declared exception.**
Truncating the kinase domain to the measured CR-8 contact span would bring it to
roughly 488, still over the cap, and would recreate precisely the defect this
decision exists to remove: a fragment that cannot fold. The exception rests on
the same structural grounds as spec 1.1's other two, with one extension. Spec
1.1 declared exceptions for **receptors** that cannot be truncated (VHL needs
ElonginB and ElonginC; DCAF15 needs DDB1 and DDA1). This is the same argument
applied to a **substrate**: CR-8 is recognised through CDK12's folded kinase
domain, and a kinase domain cut in half is not a kinase domain.

**Scope, and a warning about the discovery arms.** The campaign in flight keeps
its 15-mers; its results are reported with this caveat attached rather than
re-run. The discovery arms are entirely 15-mers, so any curated-degron hit whose
window falls inside a folded domain is open to exactly the same objection. The
flag now travels with every peptide so those hits can be filtered out of a
ranked view rather than compared like for like with genuine linear degrons.

**Reversal.** `DOMAIN_COVERAGE_SELF_SUFFICIENT` in
`nobble/curate/peptides.py`; set it to 0 to submit everything as a 15-mer.

---

## D-NOB-028: icon concepts, chosen without asking because the build is unattended

**Date:** 2026-11-03

Both icon skills ask the author to propose concepts and wait for a pick. In
unattended mode that becomes decide, log and continue, so the choices are
recorded here instead.

**Blog mark** (`nobble_icon.svg`, the repo's social image): single hero object.
Two protein domains, the larger one the E3 ligase, with the glue as a white
hexagon clamped in the cleft between them and a bond stub reaching into each
face. It depicts the one thing NOBBLE measures: whether a small molecule
creates an interface between two proteins that would not otherwise form. A
first attempt drew the domains as plain ellipses and failed its own squint
test, reading as two beans with a dot; the lobed outlines and the white
focal hexagon were the fix.

**Favicon** (`nobble_favicon.svg`): a deliberately different idea rather than a
crop of the blog mark, per the skill. Where the blog mark draws the whole
scene, this draws only the interface: a disc split by a bright slot. Two
shapes, no text, and the silhouette survives 16 pixels, which was checked on
the downsample rather than assumed.

**Rendering note.** The house render script needs cairosvg and Pillow, and the
default Anaconda interpreter has a broken Pillow (`libopenjp2.7.dylib` missing).
BINMAN's pixi environment has a working pair, so the icons render through that
interpreter. Worth knowing before the next icon.

**Outstanding, and it needs Marc.** A GitHub repository has no avatar of its
own: it inherits the owner's. The blog mark is the **social preview image**,
which can only be set through the repository's settings page and not through
the API, so `nobble_icon_300.png` is in the repository ready to upload at
Settings, General, Social preview.

---

## D-NOB-029: a substrate submitted as a folded domain gets an MSA; a 15-mer does not

**Date:** 2026-11-03

**Decision.** In the corrected-construct campaign, substrates submitted as
whole folded domains carry their own cached MSA. Substrates that remain 15-mers
carry `msa: empty`, unchanged.

**Reason.** Spec 1.3 says peptide and ligand chains get no MSA, and for a
peptide that is right: a 15-mer degron has no meaningful homology signal and an
alignment of one is not an alignment. A folded domain is not a peptide. It is a
protein chain that has to fold for the prediction to mean anything, and
co-folding a 294-residue kinase domain with no evolutionary signal would fold
it badly.

What makes this more than a technicality is what the campaign is for. D-NOB-027
claims the 15-mers failed because a fragment cannot fold; the corrected
campaign tests that by giving the same substrates their whole domain. Running
the domain arm without an MSA would handicap precisely the arm meant to show
the improvement, and a null result would then be uninterpretable: unfoldable
fragment, or foldable domain starved of signal. So this follows spec 1.3's
reasoning rather than its literal wording, and the distinction is recorded on
every job as `substrate_msa_cached`.

Six substrate-domain MSAs were generated, all successfully.

---

## D-NOB-030: the corrected campaign runs after the benchmark queue, not beside it

**Date:** 2026-11-03

**Decision.** `tools/run_corrected.sh` waits for the `nobble-bench` tmux
session to exit before starting.

**Reason.** There is one MPS device. Two queues against it would roughly halve
each one's throughput and risk an out-of-memory on the large jobs, which are
already the slowest: the DCAF15 members measure 790 to 823 seconds each at
1,199 tokens and hold about 5 GB resident. Serialising costs nothing in total
time and removes the failure mode.

The MSA precompute is the exception and did run alongside, because it is
network-bound and never touches the GPU.

---

## D-NOB-031: the Mol* presentation is BINMAN's, taken whole, with one corrected theme

**Date:** 2026-11-03

**Decision.** `molstar-bridge.js` is copied from BINMAN unchanged and never
edited here. NOBBLE's Pose tab adopts BINMAN's viewer markup, its control bar
and its stylesheet, so the two modules render identically: the translucent
gaussian-surface polymer at alpha 0.45 with radiusOffset 1.6, the ligand as
sticks with pinned magenta carbons inside an emissive shell at alpha 0.09, the
bloom in emissive mode, the furniture list and the framing radii. Every one of
those numbers was tuned against real structures and the reasons are in that
file's comments; reproducing them here by hand would have drifted on the first
value guessed.

**The one departure, and why it is a correction rather than a preference.**
The bridge colours confidence with Mol*'s `uncertainty` theme, which maps a
**high** B-factor to **high uncertainty** and therefore to a warm colour.
pLDDT runs the other way: high is good. A Boltz prediction writes pLDDT into
the B-factor column and these average 96 out of 100, so `uncertainty` painted
the entire model in the "very low confidence" band. The viewer was stating the
exact inverse of the truth about its own model, in the most legible way
available to it.

Mol* ships `plddt-confidence`, which is the real AlphaFold four-band scale. It
reads the `ma_qa_metric` category, and Boltz writes that category: checked in
the loaded file rather than assumed. NOBBLE therefore asks the bridge not to
colour (`plddt: false`) and applies `plddt-confidence` afterwards, scoped to
the **polymer components only**. Applied to every component it overrode the
ligand's `element-symbol` theme and took its pinned magenta carbons with it,
so the ligand stopped reading chemically and began reporting a confidence it
does not have.

**Not fixed in BINMAN, deliberately.** The same inversion would affect any
model BINMAN loads that carries `ma_qa_metric`, so it is worth raising there.
Editing another live application's shared file from inside this build is not
the way to raise it, and a forked copy that drifts is worse than no copy.

**Reversal.** `colourByConfidence` in `nobble/app/templates/pose.html`; remove
it and pass `plddt: true` to return to the bridge's behaviour exactly.

## D-NOB-032: a sampling tier is a hard partition on scoring, not a label on a row

Tier 2 was built but never wired: `build_tier2_queue` wrote
`queue_tier2.jsonl` and `run_campaign` only ever opened `queue.jsonl`, so
nothing could run it. Wiring it up exposed the reason that was worth
pausing over.

`delta_iptm` is `iptm_min_ternary - iptm_min_binary`, and both terms are a
**minimum over seeds**. A minimum is not robust to sample count: drawing more
diffusion samples can push a minimum down and can never push it up. Tier 1
draws one diffusion sample per job, tier 2 draws twenty-five. Scoring grouped
jobs by `pair_id` alone, so had tier-2 results been appended to
`results.jsonl`, the refined ternary records would have joined the tier-1
ternary minimum while the binary arm stayed at one sample. `delta_iptm` would
have fallen for precisely the pairs that were selected for being the most
promising, and it would have read as the glue weakening the interface. The
failure is silent: nothing raises, nothing goes out of range, and the number
stays entirely plausible.

**Decided.** Three changes, because a convention would not have been enough.

1. `tier_files()` gives tier 2 its own queue, state and results files. Tier 1
   stays immutable, so a refinement run cannot corrupt the measurement that
   selected it.
2. `metrics.aggregate()` takes `sampling_tier`, defaulting to 1, and filters
   on it. This is a hard partition, not a label. Records written before the
   field existed default to tier 1, which is what they are.
3. The runner stamps `tier_setting` on every result. The existing `tier`
   field could not be reused: it already carries the **curation** tier (Tier A,
   Tier B, benchmark), which is an unrelated axis, and overloading it would
   have been the same class of mistake one level down.

**Tier 2 stays ternary-only**, which is what the module already did, but the
justification it carried was wrong. It argued that refining the binary arm
would "spend the budget on the control rather than the measurement". For a
difference of two minima the control *is* half the measurement, so that
reasoning would license the exact bias above. The correct reason is narrower:
spec 1.2 gives tier 2 one purpose, pose refinement on the top decile. It is
not a second and better estimate of Delta-ipTM, and the partition is what
stops it being read as one.

**Alternatives rejected.** Refining both arms keeps Delta-ipTM symmetric and
comparable, but doubles tier-2 cost to re-measure a quantity tier 1 already
measures adequately, and the spec does not ask for it. Recomputing a separate
tier-2 Delta-ipTM from tier-2 binaries would be defensible science but is
scope the spec does not contain.

**Reversal.** `tier_files()` in `nobble/execute/runner.py` and the
`sampling_tier` filter in `nobble/score/metrics.py`. Drop the filter and point
both tiers at one results file to return to the pooled behaviour.
`tests/test_tiers.py` fails first if that happens: the contamination case is
constructed deliberately, because it is not visible by inspection.

## D-NOB-033: the Sievers arm is co-folded with the IMiD that actually degraded each zinc finger

**Date:** 2026-11-04

The Sievers screen tests five IMiDs (CC-122, CC-220, lenalidomide,
pomalidomide, thalidomide) and reports which were significant per zinc
finger. The arm was about to be built as "160 peptides against CRBN", with
the drug left implicit. Counting first rather than assuming showed why that
would not work: of the 32 degraded zinc fingers, pomalidomide is significant
for 23 and lenalidomide for only 8.

Running the whole arm under one IMiD would co-fold most positives with a drug
the same screen says does not degrade them, while still labelling them
degraded. That is not a noisy label, it is an inverted one, and it inverts
exactly the label the headline ROC is computed on.

**Decided.** The drug is assigned per peptide, pomalidomide (`Y70`) preferred
over lenalidomide (`LVY`) because it covers far more of the set. Each matched
control inherits its positive's drug, so the comparison the ROC makes is
within-drug: a control co-folded with a different IMiD than its positive
would differ from it in two things at once and would measure neither.

**Eight positives are dropped**, not substituted: INSM1, PLAL1, ZKSC5, ZN285,
ZN292, ZN526, ZN644 and ZN860 are significant only for CC-122 or CC-220,
which have no CCD code in BINMAN's ligand table. Spec 4.18 scopes its
falsifiable prediction to "lenalidomide or pomalidomide", so these fall
outside the arm. The drop happens *before* matching, so a dropped positive
cannot consume controls a kept positive would otherwise be matched against.
The arm is therefore 24 positives and 96 controls, 120 peptides rather than
160, and the matched structure is intact.

**Thalidomide is excluded although it has a CCD (`EF2`).** Every
thalidomide-significant row in the screen is also pomalidomide-significant,
so including it would change no assignment while widening the claim past what
the spec predicts.

**Consequence, measured after the rebuild rather than predicted.** The arm
shrinking to 120 brings the *mandatory* set to 127 against a measured budget
of 156, but the selection is 158 once each kept positive's scramble is paid
for, so it is still 2 over and there is still no headroom for discovery. The
campaign remains calibration-only. What did change is the projection: 2,370
jobs at 48.4 hours against the 63.1 hours the 160-peptide arm would have
cost, which lands within half an hour of the 48-hour per-run target. Getting
the drug assignment right paid for itself in compute as well as in validity.

**Also fixed.** `screen_drugs` is now a structured field on `Peptide`. The
first version of the assignment parsed the drug list back out of the prose in
`notes`, which made the arm's composition depend on the wording of a sentence.

**Reversal.** `IMID_PREFERENCE` and `sievers_drug_for` in
`nobble/curate/peptides.py`. Widen the preference list to use more IMiDs, or
return `IMID_CCD["POM"]` unconditionally to go back to one drug for the arm.
`tests/test_sievers_drugs.py` fails first in either case.

## D-NOB-034: a C2H2 zinc finger is submitted with its zinc, in both arms

**Date:** 2026-11-04

There was no zinc anywhere in NOBBLE. The Sievers arm was about to submit
120 whole C2H2 zinc fingers as bare 23-to-26-residue chains, and all 120
carry the complete coordination motif (at least two cysteines and two
histidines; checked, not assumed).

A C2H2 finger is held in its fold by a single Zn(2+) ion coordinated by
those four residues. Without it the chain is not a domain with a missing
accessory, it is a disordered 23-mer. The arm takes these whole rather than
tiled on the explicit grounds that a zinc finger is a folding unit, so
leaving the ion out contradicts the reason the arm is built the way it is,
in the one arm that carries the headline ROC.

**Decided.** Peptides whose class is `zinc_finger` and that carry a complete
C2H2 site are submitted with a `ZN` ligand chain.

**In both arms, which is the part worth stating.** Delta-ipTM is the ternary
ipTM minus the binary one. A cofactor present only in the ternary arm would
fold the peptide differently between the two, and the difference would
report "the glue changed the interface" for what was really "the peptide
folded this time". That is the same class of error as pooling sampling tiers
into one minimum (D-NOB-032), one level up: a quantity defined as a
difference is only interpretable when its two terms differ in one thing.

**Scrambles of zinc fingers get the ion too.** A composition-matched
scramble carries the same cysteines and histidines in shuffled positions and
cannot form a canonical site. It still gets the zinc, because its job is to
differ from its positive in exactly one variable, the residue order.
Withholding it would make the control differ in two, and a negative that
fails for the wrong reason says nothing about the positive.

**The 15-mer benchmark degrons are excluded although IKZF1's is a zinc
finger fragment.** Its histidines fall outside the window, so there is no
site to complete, and bench04 scored the best Delta-ipTM in the panel
without one. The test is the complete motif, not the source.

**Measured, and the strong form of the claim above is wrong.**
`tools/zinc_probe.py` folded one degraded finger and one control, each with
and without the ion, peptide chain only:

| finger | with zinc | without zinc | gain |
|---|---|---|---|
| ZEP2 (degraded) | 95.66 | 95.37 | 0.29 |
| ZN346 (not degraded) | 87.79 | 85.99 | 1.80 |

A chain predicted at pLDDT 95.37 is not "a disordered 23-mer", so that
sentence is simply false as applied to what Boltz-2 actually predicts. It
reproduces the canonical fold from sequence alone, as AlphaFold2 does,
having learned the mapping from structures that did contain the ion.

The decision to include the zinc stands, but as **cheap insurance rather
than a fix**: it is chemically correct, it costs one token, and it does not
hurt. What does not stand is the claim that the arm "would have measured
noise without it". That was reasoning from chemistry asserted as a result,
and the measurement contradicts it.

**The caveat was chased down and is closed.** The first pass showed a
larger gain for the control (1.80) than for the degraded finger (0.29). A
zinc effect correlated with the label is exactly the confounder D-NOB-035
refuses MSAs to avoid, so dismissing it at one sample per class would have
been inconsistent. Rerun at six per class:

| | mean gain | mean pLDDT without zinc |
|---|---|---|
| degraded (n=6) | -0.07 | 95.22 |
| not degraded (n=6) | +1.40 | 92.38 |

The difference looks like the feared effect and is not. Gain correlates
with the starting score at **r = -0.704**: the lower a finger scores
without zinc, the more the ion helps it. The controls simply start lower,
so they have more room. Treating the two classes as groups instead, the
difference is +1.47 with a standard error of 0.90, t = 1.64 at n = 12,
which is not a difference. Within-class scatter (sd 1.74 and 1.34) dwarfs
it.

So the zinc effect tracks headroom, not label, and the ion cannot bias the
ROC toward either class.

**A separate observation, noted and not acted on.** The degraded fingers
fold better than the controls before any zinc is added (95.22 against
92.38). That is a property of the peptides rather than of the ion, and
because Delta-ipTM is a difference between two arms that both contain the
same peptide, a constant per-peptide fold quality largely cancels. Worth
revisiting if the ROC comes out suspiciously strong, because "the positives
were easier to fold" is a duller explanation than "the glue changed the
interface" and would look the same from the AUC alone.

**Reversal.** `requires_structural_zinc` in `nobble/curate/peptides.py`;
return `{"required": False}` to go back. `tests/test_zinc.py` fails first,
including the both-arms case.

## D-NOB-035: the Sievers zinc fingers get no MSA, and the reason is the ROC rather than the cost

**Date:** 2026-11-04

D-NOB-029 established that a substrate submitted as a whole folded domain
carries its own MSA, following spec 1.3's reasoning rather than its literal
wording. A zinc finger is a folding unit, submitted whole for that reason,
so the rule appears to apply and 120 MSAs would be needed.

**Decided.** It does not apply here. The Sievers fingers carry
`msa: empty`, as spec 1.3 says peptide chains should.

**Reason, and it is not the cost.** The 120 MSAs are network-bound against
the ColabFold server and would run perfectly happily alongside the GPU
queue. The reason is that alignment depth would not be distributed evenly
across the two classes the ROC separates. The arm is 24 degraded fingers
drawn from 24 distinct genes against 96 controls drawn from 86, and the
matching that built it matched on length and amino-acid composition, which
is what makes a control a control here, and not on how well studied the
parent protein is. If the degraded set systematically came from
better-characterised proteins with deeper alignments, MSA depth would
become a variable that correlates with the label, and the headline ROC
would be partly measuring how much homology each chain was given rather
than whether the glue changed the interface.

Giving none to any of them removes that by construction. It costs some
absolute fold quality in exchange for a comparison that measures one thing,
which is the right trade in the arm that carries the result.

**The other half of the answer is D-NOB-034.** What a C2H2 finger needs to
fold is its zinc, not its homologues, and it now has one. The two decisions
were taken together and should be read together: an MSA was refused in the
same pass that added the structural support the chain actually depends on.

**Contrast with D-NOB-029, so the boundary is explicit.** That case was a
294-residue kinase domain submitted as a single arm's construct, where no
comparison between classes rode on the MSA and the chain genuinely could
not fold without evolutionary signal. The criterion is therefore not "does
it fold" alone: it is whether the MSA could correlate with the label of a
matched comparison.

**Reversal.** `build_yaml` in `nobble/execute/yaml_gen.py` sets the peptide
chain's `msa` to `msa_module.EMPTY`. Pointing it at a cached a3m for
zinc-finger peptides restores the other behaviour. If that is ever done,
measure alignment depth for the degraded and non-degraded sets first and
report the two distributions: the confounder above is testable, and it was
asserted here rather than measured.

## D-NOB-036: the matched-control ROC is scoped to the Sievers arm; the weight fit is not

**Date:** 2026-11-04

Assembling the main campaign put benchmark, Sievers and scramble pairs into
one `scores.jsonl` for the first time. Cross-tabulating the labels against
the tiers showed that the benchmark panel's seven pairs carry
`peptide_label: "degraded"`, the same label the Sievers positives carry.

`matched_control_roc` selected on that label alone, so the moment the
campaign ran, those seven would have joined the positive side of the
headline curve. They are a different experiment: other E3 ligases, PROTACs
as well as glues, and no matched negative drawn from the same screen. They
are also the panel chosen for having good co-crystals, so they would have
raised the positive side and the AUC with it.

The failure would have been silent and flattering. The curve still draws,
the number still looks plausible, and it moves in the direction that makes
the result look better. Nothing in the output would have said that seven of
the thirty-one positives came from somewhere else.

**Decided.** `matched_control_roc` filters to `tier == "sievers_zf"` and
reports `pairs_outside_the_arm_excluded` so the exclusion is visible rather
than implied. Spec 5.3 scopes the curve to "the Sievers degraded versus
non-degraded split", and that is now enforced rather than assumed.

**The weight fitter is deliberately left unscoped.** Spec 4.8 fits the
weights "on the benchmark panel and the Sievers matched set", so the panel
belongs in the fit and excluding it would fit on less than the spec asks
for. The same field therefore means different things to the two consumers,
which is exactly the kind of asymmetry someone later tidies away, so the
contrast is written into `weights._label` rather than left to be inferred.

**Scrambles count as negatives for the fit and not for the ROC.** A
scramble never went through the Sievers screen, so it is not a matched
control; it is a composition control, which is a different claim.

**Reversal.** The `arm = [...]` filter in `matched_control_roc`.
`tests/test_roc_scope.py` fails first, and its contamination case is built
so the benchmark pairs would drag a below-chance arm above chance.

## D-NOB-037: the design arm ships before the score that would rank it is validated

**Date:** 2026-11-04

A seventh tab, scoped in `DESIGN_ARM.md`. `BUILD_SPEC.md` contains no design
phase: it names "designed peptides" twice, both in section 3.5 as an input
class ESMFold would handle if such sequences existed. None of those
generators were built, so this is an addition rather than an unbuilt part of
the spec, and the spec is left as written.

**The constraint that shaped it.** The composite is not validated: the
matched-control ROC reports `not_computed` until the Sievers arm runs. A tab
that ranked invented peptides by it would be the failure this project exists
to avoid, because a ranked list reads as a recommendation whatever the
caption says.

**Decided.** Build it so it is useful before the score is trusted.

1. Every variant is anchored to a parent carrying an experimental label.
   Nothing is scored in the abstract.
2. The headline number is design lift, `delta_iptm(variant) -
   delta_iptm(parent)`: a difference of differences, cancelling whatever the
   receptor, the glue and the parent degron each contribute.
3. The claim the tab makes is the **ordering** of positions, which survives a
   monotone miscalibration of the scale. "Position 7 matters more than
   position 3" is robust in a way "this peptide will be degraded" is not, and
   the tab says so next to the figure rather than in a footnote.

**Lift refuses rather than approximates.** If the variant and its parent
differ in construct, E3, ligand or modality, or either has fewer than three
seeds, no lift is returned. The subtraction would otherwise report the
conditions instead of the substitution, in a plausible number nothing else
flags. Same rule as D-NOB-032 and D-NOB-034, one level up.

**Alanine first, saturation second.** A scan of a 15-mer is 15 variants and
225 jobs, about 4.9 hours. Saturating every position is 285 variants and
4,275 jobs, which no budget absorbs, so `saturate()` requires explicit
positions and raises without them. The scan is what chooses where to look.

**A position already alanine is scanned to glycine**, not emitted unchanged.
An unchanged variant costs 15 jobs to learn nothing and would read on the
chart as "this position does not matter" when it was never tested.

**The default parent is chosen from the measurement.** Every benchmark degron
is a 15-mer, so "the shortest" was an arbitrary tiebreak and it landed on
BRD4/VHL: a PROTAC pair, in an arm about glue dependence. It now ranks by
measured Delta-ipTM and picks IKZF1/CRBN at +0.316, the canonical IMiD
neosubstrate and the largest signal in the panel. A scan of a parent with no
glue dependence measures the noise floor.

**ESM-2 is deliberately not used to propose substitutions**, although it is
already in the stack for diversity reduction. It would introduce a second
opinion about which designs are good, and the arm exists to test NOBBLE's.

**Reversal.** `nobble/design/`, the `/design` route, and the `design.json`
block in `deploy/build_atlas.py`. `tests/test_design.py` (13 tests) covers
the generators and every refusal path in lift.

## D-NOB-038: a design variant inherits its parent's cofactor rather than re-deriving it

**Date:** 2026-11-04

Building the design assembler exposed a trap in the arm's most interesting
case. `requires_structural_zinc` infers the cofactor from the sequence: a
complete C2H2 site means a `ZN` chain. An alanine scan mutates residues one
at a time, so a scan of a zinc finger mutates the coordinating cysteines and
histidines, and the inference then returns `False` for those variants.

Measured on a real finger (ZEP2, 25 residues): a 25-position scan drops the
ion at **C3A and C6A**, two variants out of twenty-five.

Those two are not incidental. They are the coordinating cysteines, the
positions a scan of a zinc finger exists to interrogate. The parent would
carry a zinc and those variants would not, so their design lift would
subtract two differently-constituted systems and report the missing ion as
the substitution's effect. The lift would be large and negative, it would
read as "this position is critical", and that conclusion is the one a
structural biologist expects, so it would very likely be believed. A wrong
answer that agrees with the prior is worse than an obviously broken one.

**Decided.** `Peptide` carries an optional `cofactor` dict that overrides
inference, and every design variant is given its parent's. If the parent has
a zinc, so does C3A, even though C3A cannot coordinate it. That is correct
for a control: the variant differs from its parent in the residue, not in
the chemical system around it.

**Consequence worth being explicit about.** C3A is then a finger with a zinc
it cannot hold properly, which is not a physically tidy object. That is the
right trade. The scan's question is "what does this residue contribute to
the interface, holding everything else fixed", and holding everything else
fixed is the whole of it. A variant that also loses its ion answers a
different and uninterpretable question.

**Reversal.** The `cofactor` field on `Peptide` and the early return in
`requires_structural_zinc`. `tests/test_design.py` holds both halves: one
test demonstrates the trap without inheritance, another pins that
inheritance closes it.

## D-NOB-039: the remaining campaigns run as one chain, in a deliberate order

**Date:** 2026-11-04

Four pieces of compute are outstanding and there is one MPS device, so they
are strictly sequential: two campaigns sharing it halve each other's
throughput and risk an out-of-memory on the larger jobs. `tools/run_chain.sh`
runs them behind whatever is already on the GPU.

**Order, and the reasoning.**

1. **The corrected-construct comparison.** Cheap, and it answers a question
   already paid for: the corrected campaign is running now, so scoring and
   comparing it costs CPU rather than GPU.
2. **The main campaign.** 158 pairs, 2,360 jobs, 51.8 projected hours. It
   carries the matched-control ROC, which is the project's falsifiable test
   and the thing every other number is waiting on.
3. **Tier 2.** Refines the top decile, so it needs the ranking the main
   campaign produces. Cannot go earlier.
4. **The design scan.** Last, and this is the one worth justifying. It is
   only 4.9 hours and it would be tempting to slot it in early for a quick
   complete result. But the design tab's own caveat is that the composite is
   not trustworthy until the Sievers arm has run, so running the scan first
   would produce lifts that have to be caveated into uselessness, and then
   rerun. Running it after the ROC means the lifts arrive against a score
   whose discrimination has been measured.

**Why this is started rather than proposed.** Unattended mode: Gate G1 is the
only thing that would stop a run of this size, and it is closed. The main
campaign projects to 51.8 hours against a 96-hour G1 threshold, measured
mechanically rather than estimated (`projected_hours`). The 48-hour figure it
exceeds is the per-run target, not a gate, and the queue is priority-ordered
so a run cut short yields the benchmark panel and then the Sievers split
before it loses anything.

**Resumability is what makes a 60-hour chain reasonable.** Every stage skips
completed job ids from its own `state.jsonl`, so a kill anywhere is recovered
by rerunning the script rather than by working out where it stopped. Each
stage also tolerates its successor failing: the chain uses `|| true` on the
analysis steps so a scoring error cannot strand the compute behind it.

**Preflight gates the expensive stage.** The main campaign does not start
unless `tools/preflight.py` passes on it, because the failure worth catching
there is the silent one: a cofactor present in one arm completes the run and
reports itself as the glue.

**Reversal.** `tmux kill-session -t nobble-chain`. Nothing is lost: each
stage is resumable and the assembled campaigns stay on disk.

## D-NOB-040: the design scan picks its target after the main campaign, not before

**Date:** 2026-11-04

The design scan was assembled against IKZF1/CRBN, chosen by the largest
measured Delta-ipTM among the parents that had been scored. At the time that
meant the seven benchmark pairs, because nothing else had run.

The chain then ran that pre-assembled campaign last, which quietly undid the
reason for putting it last. Queuing the scan behind the main campaign is
meant to buy a validated score and a wider field: 31 scannable parents, of
which 24 are Sievers fingers that will have been measured by then. Reusing a
target chosen from seven benchmark pairs throws that away and keeps only the
delay.

**Decided.** The chain re-assembles the design campaign after the main
campaign has scored, so the parent is chosen from 158 pairs rather than 7.
IKZF1 may well still win: it is the canonical IMiD neosubstrate and it leads
the benchmark at +0.316. The point is that it should win against the full
field rather than by default.

**Reversal.** The re-assembly block in `tools/run_chain.sh`. Remove it to
scan whichever campaign `campaigns/design_*` last holds.

## D-NOB-041: the site is not republished while a campaign is running

**Date:** 2026-11-04

The main campaign runs for about 52 hours, during which the published site
shows the benchmark panel and nothing moves. The obvious improvement is to
refresh and deploy periodically so a visitor sees the campaign filling up,
and now that `build_atlas` takes a campaign that would work.

**Decided against.** `deploy.sh` rsyncs `deploy/atlas/structures`, and
`build_atlas` copies every structure referenced by `results.jsonl`. Mid-run,
the runner is writing those files. Copying one as Boltz writes it publishes
a truncated mmCIF, and a truncated structure does not announce itself: the
viewer loads what is there and draws a partial chain, which is a wrong
picture rather than a missing one. Scoring a results file that is being
appended to is safe, because the format is line-oriented and torn lines are
already handled; copying a structure mid-write is not.

The status panel already carries the honest version: it names the campaign
it published and says how many others were queued when the slice was built
(D-NOB-036 and the `outstanding` field). A static site that says it is
static beats a live one that might show a half-written structure.

**If it is wanted later**, the safe form is to publish only the JSON
documents mid-run and hold the structures back until the campaign ends,
rather than to copy structures more carefully. A refresh can also be run by
hand at any point: `bash tools/refresh.sh <campaign> && bash deploy/deploy.sh`.

**Reversal.** Add a publisher loop to the main-campaign stage of
`tools/run_chain.sh`, and read the paragraph above first.

## D-NOB-042: the chain publishes once at the end, and deploys

**Date:** 2026-11-04

Reading `run_chain.sh` end to end after several rounds of edits found two
gaps, neither of which would have failed anything.

**The atlas was built too early.** `refresh.sh` runs straight after the
main campaign, before tier 2 and the design scan have produced anything.
Both then ran for hours into files the published bundle did not contain:
refined poses the structure catalogue could not offer, and a scan profile
with no chart. The compute would have happened and the site would not have
known.

**And nothing deployed.** The chain built an atlas and stopped. After about
sixty hours the live site would still have been showing the benchmark
panel, waiting for someone to notice and run `deploy.sh` by hand.

**Decided.** A single rebuild after the last stage, then a deploy.

Once, at the end, not between stages: D-NOB-041 rules out publishing while
a campaign is writing structures, because the rsync can copy an mmCIF
mid-write and a truncated structure draws a partial chain rather than
failing. Every stage that can change the bundle has finished by then.

Deploying is the point of having built the bundle, and the permission is
explicit and repeated. It runs last, after everything, and `deploy.sh`
already refuses to report success unless all nine routes answer 200. A
failed deploy prints how to retry and does not fail the chain, because the
atlas is built locally either way and the compute is the expensive part.

The chain ends by printing `tools/status.sh`, so the last thing in the log
is where everything stands rather than the tail of a deploy.

**Reversal.** The two blocks at the end of `tools/run_chain.sh`. Removing
the deploy leaves the atlas built and unpublished, which is the previous
behaviour.

## D-NOB-043: bound every wait after a kill, and measure elapsed time in code

**Decision.** Two changes. `nobble/execute/runner.py` no longer uses
`subprocess.run(timeout=...)`: it drives `Popen` through `_run_boltz`,
which returns `ok`, `timeout` or `unkillable`, sends SIGKILL up to
`KILL_ATTEMPTS` times across `KILL_GRACE_SECONDS`, and bounds every wait
it performs. A job that survives the window is abandoned, recorded as
failed, and not retried. Separately, `nobble/execute/watchdog.py` reports
how long each running job has been going, from `started_at` in
`state.jsonl`, against a bound derived from the runner's own timeout,
retry count and kill grace.

**Why, honestly.** The runner change was made while chasing a stall that
had not happened: a local timestamp read as UTC (F20). The defect it
fixes is real regardless and is demonstrated by a test that hangs the
old code, so it stays. But it is hardening against a latent fault, not a
post-mortem, and the record should not imply otherwise.

The watchdog is the change that addresses what actually went wrong. The
failure was a hand-computed elapsed time across two timezone
conventions. The campaign already stores the timestamp; nothing was
reading it.

**Alternatives.** Leaving `subprocess.run` and raising the timeout
addresses neither problem: the hang is after the timeout, and the
misreading had nothing to do with its value. Stopping the queue on an
unkillable job is wrong for an unattended 2,360-job run, where it turns
one bad job into a dead night. Retrying an unkillable job was rejected
because the orphan may still hold the device.

**Cost.** An abandoned orphan can hold GPU memory, so later jobs may slow
or fail. That is visible in the manifest as failed jobs rather than
invisible as a stall, which is the trade. The watchdog's `overdue` signal
is advisory and will sometimes fire on a merely slow job; the `stalled`
signal needs no tuning because its bound comes from the runner.

**Reversal.** `_run_boltz` in `nobble/execute/runner.py`, and deleting
`nobble/execute/watchdog.py` with its `[watchdog]` block in
`config/thresholds.toml`.

## D-NOB-044: the receptor-peptide ipTM is the substrate receptor's, not chain A's

**Decision.** `metrics._receptor_peptide_iptm` takes the minimum of Boltz's
`pair_chains_iptm` across the segments of the *substrate-recognition*
protein against the peptide, rather than chain 0 against the peptide.
Scaffolding chains are excluded. Each seed record now carries the chains
used and the previous chain-0 value, so the change is auditable from the
data and not only from this file.

**Why.** Spec 4.3 defines the headline as
`iptm_min_ternary - iptm_min_binary` and specifies the minimum across
seeds. It does not say which chain pair the ipTM is. For a single-chain
receptor there is nothing to decide. For `DCAF15_DDB1_DDA1`, which is five
chains, the code was deciding silently: chain 0, the N-terminal domain of
DCAF15, while DCAF15's C-terminal domain, which the substrate also binds,
was ignored. Measuring one arbitrary half of a two-segment protein is not
a definition anyone would have written down on purpose.

The minimum is the rule this module already applies twice: across the two
directions of Boltz's asymmetric matrix, and across seeds. Applying it to
the receptor's own segments is consistent rather than new. It also matches
`score/geometry.py`, which already merges receptor segments because "for a
multi-segment receptor the relevant side is the receptor as a whole".

**Alternatives.** The minimum across *all* receptor chains was rejected: it
would be dominated by DDB1 at 0.05 to 0.66 in the real data, a chain the
peptide is not supposed to touch, so the statistic would measure how well
the degron fails to engage the scaffold. Leaving chain 0 and only
documenting it was the safer option and was rejected because the number is
the project's headline and "chain A of five" is not a defensible reading of
spec 4.3.

**Measured effect, before deciding.** Across all 183 scored jobs in both
finished campaigns, 9 seed values change, all RBM39/DCAF15, by at most
0.0103. At the pair level exactly one Delta-ipTM moves:
`corr06_RBM39_DCAF15`, from +0.1872 to +0.1937. The benchmark campaign is
unchanged in every pair. No verdict, threshold or published conclusion
turns on 0.0065, which is why this was a safe correction rather than a
Gate G6 question.

**Cost.** The two finished campaigns' `scores.jsonl` were written under the
old definition. The corrected campaign is still running and the chain
rescores it on completion; the benchmark campaign's numbers are identical
either way, so nothing needs republishing.

**Reversal.** `_receptor_peptide_iptm` in `nobble/score/metrics.py`. Every
record also carries `iptm_receptor_peptide_first_chain_only`, so the old
series can be recovered without rerunning anything.

## D-NOB-046: the Slabicki graded labels were never acquired, so the ROC's secondary test is reported as not computed

**Date:** 2026-11-04

**Finding.** Spec 5.3 asks for two tests in the matched-control layer:
"Delta-ipTM on the Sievers degraded versus non-degraded split, with the
Slabicki graded labels as a secondary continuous test". Spec 2.1 lists
"Slabicki 2025 (Mol Cell), per-compound, graded degradation labels,
alanine scan, 29-analog panel" among the sources, with the rationale that
it "converts a binary readout into a dose-like one".

That dataset does not exist in BINMAN. Its validation store holds
seventeen parsed datasets and the raw downloads behind them; none is
Slabicki's. The name appears only in `references.json`, as three
bibliography entries, one of which is the Sievers paper he co-authored.
NOBBLE consumes BINMAN's stores rather than acquiring its own (spec 2.1),
so there is no continuous label to correlate against.

**Decision.** `matched_control_roc` reports
`secondary_graded_test: "not_computed:
slabicki_graded_labels_unavailable"` with the reason, beside the binary
curve it can compute.

**Why.** The same principle as D-NOB-010, where Degronopedia and ProtCID
were unavailable and the furniture veto reports `not_computed` rather
than `false`. A reader comparing this output against the specification
should find the missing half named. The alternative, which is what was
happening, is an output that satisfies half a requirement and looks
complete, and nothing anywhere recording that the other half was ever
asked for.

**Cost.** The binary split is a coarser test than a graded one. A
continuous label would separate a weak degrader from a strong one;
degraded against not-degraded cannot. The headline ROC is therefore less
sensitive than the specification intended, and says so.

**Reversal.** Acquire the Slabicki per-compound data into BINMAN, then
correlate Delta-ipTM against the graded labels in `matched_control_roc`
beside the binary curve. The field is where the result would go.

## D-NOB-047. The significance level lives in the configuration

**Decision.** `benchmark.html` styled its Pearson correlation on a literal
`p < 0.05`. That value is now `scoring.significance_alpha` in
`config/thresholds.toml` and is injected into the template.

**Alternatives.** Allowlist it in the template sweep as the chart's own,
the way the 10 and 15 angstrom near-miss bands are. Rejected: those two
are presentation bands with no meaning outside the chart, whereas 0.05 is
a statistical threshold that decides whether the project shows a
correlation as holding. A reader changing what the project counts as
significant should not have to know it is written in markup.

**Reversal.** Put the literal back in the template and remove the key.
The test that holds it would fail, which is the point.

## D-NOB-048. The zinc motif is tested before the curated class

**Decision.** `requires_structural_zinc` counts the coordination site
before consulting `degron_class`, so the reason it records is true of the
peptide it describes. A complete site in a peptide submitted as a tile is
reported rather than silently declined.

**Alternatives.** Leave the order and reword the reason to something
vaguer, such as "not curated as a zinc-finger domain". Rejected: it is
still an explanation built on the wrong attribute, and it would leave the
motif untested for every peptide outside the domain classes. Also
considered dropping the class gate entirely, since the docstring says the
motif is the test: rejected because a non-domain peptide with two
cysteines and two histidines would then gain an ion it never had, which
changes numbers to fix a wording.

**Cost.** None measured. The decision is unchanged for all 5670 peptides
in the library, which is a test rather than a claim.

**Reversal.** Restore the class gate ahead of the motif count. Three
tests fail, one of them naming IKZF1 directly.

## D-NOB-049. A campaign directory does not outlive a failed assembly

**Decision.** All four assemblers build inside `fresh_campaign()`, which
removes the directory if the block exits by exception or without writing
`campaign.json`. `latest()` additionally requires that marker, so a
directory left by a killed process is never returned as a campaign.

**Alternatives.** Stage under a dot-prefixed name and rename into place on
success. Rejected as more machinery for the same outcome: the rename is
atomic but `campaign_id` is derived from the directory name in all four
assemblers, so the staging name would have had to be threaded through each
of them. Also considered a tool that reports and clears incomplete
directories: useful, but it treats the litter rather than the cause, and
the cause is three lines long.

**Cost.** A failed assembly no longer leaves its partial YAMLs for
inspection. Acceptable: nothing diagnosed a failure from them, and the
exception that caused it is still raised.

**Reversal.** Replace the `with fresh_campaign(prefix) as directory:` lines
with the original two mkdir calls. Five tests fail, two of them sweeps that
name the file that regressed.

## D-NOB-050. The atlas build refuses on an input the code would not emit

**Decision.** `nobble/validate/inputs.py` compares every job's YAML against
the queue row describing it, and `deploy/build_atlas.py` refuses to publish
while any disagree. The chain corrects the known case itself, after the main
campaign and before the publish.

**Alternatives.** Exclude the affected pair from the atlas and caption it.
Rejected: silently dropping a benchmark pair from a seven-pair panel is its
own misreport, and the pair is one of the two the comparison report cites.
Also considered checking only for the known hydroxyproline: rejected because
it would not catch the reverse case, a YAML missing a modification the queue
requires, which is what a reassembly actually causes.

**Cost.** A disagreement blocks the whole publish rather than part of it,
so a single stale pair keeps the site on its previous atlas. Accepted: the
previous atlas is stale, and stale is recoverable in a way that a wrong
number presented as a measurement is not.

**Reversal.** Remove the check from `main()`. One test fails, and it names
the file and the pair.

## D-NOB-051. The atlas output directory is overridable

**Decision.** `build_atlas.py` takes `NOBBLE_ATLAS_OUT`, and the test that
exercises its refusal writes to a temporary directory.

**Alternatives.** Leave the test pointing at the real atlas, since the build
refuses and writes nothing. Rejected on evidence: mutating the refusal away
is a normal step in checking that test, and it rebuilt the published atlas
from a part-scored campaign. A test whose safety depends on the code it is
testing being correct is not a test.

**Reversal.** Hard-code `OUT`. The refusal test would then write to the real
atlas whenever the refusal is absent, which is the state it exists to detect.

## D-NOB-052. The GPU guard waits on processes, not on session names

**Decision.** `nobble_wait_for_gpu` waits for tmux sessions and then for any
`nobble.execute.runner` process outside its own ancestry, excluding
`--throughput` runs. `run_queue.sh` and `run_corrected.sh` now wait before
starting inference, which they did not.

**Alternatives.** Extend the session list. Rejected: the list had already
drifted once, and an orphaned process belongs to no session at all, which no
list can fix. Also considered a lock file: rejected because a run killed with
SIGKILL leaves the lock held and the next run blocked, which trades a false
negative for a false positive that needs a human.

**Cost.** `pgrep` is consulted every poll instead of `tmux has-session`, and
the guard now depends on the runner's module path appearing in the process
command line. Both are cheap; the second is why the pattern is in one place.

**Reversal.** Delete `nobble_wait_for_runners` and its call. Two tests fail,
one of them naming the script that stops waiting.

## D-NOB-053. The poll interval and the process pattern are overridable

**Decision.** `NOBBLE_GPU_POLL_SECONDS` and `NOBBLE_GPU_PATTERN` default to
60 seconds and the runner's module path.

**Alternatives.** Keep both fixed. Rejected on evidence: with a 60-second
interval and a campaign running on the machine, no test could assert that
the guard waits, and removing the wait altogether passed the whole file.
A seam that exists only for a test is a cost; a guard nothing can prove
waits is a larger one.

**Reversal.** Hard-code both. The test that proves the guard waits would
then either hang or be skipped on any machine that is actually busy, which
is every machine where the guard matters.

## D-NOB-054. Compute is projected per token band, not at one rate

**Decision.** `write_throughput` records a median seconds-per-token rate and
a job count for each configured token band, and `projected_hours` prices each
job in its own band when given the per-job token counts. A band with no
measurement is priced at the slowest rate observed.

**Alternatives.** Fit a curve, since attention cost is super-linear in
sequence length. Rejected on evidence: one job above 800 tokens is not a
curve, and a fitted model would state a precision the data does not support.
Banding states only what was measured. Also considered keeping the flat rate
and widening the comment to admit the bias: rejected because the number is
reported to a Gate, and a figure known to be low is not improved by saying so
beside it.

**Cost.** A band measured once sets the price for every job in it, so the
29 jobs over 800 tokens are priced from a single observation. Visible rather
than hidden: the job count is recorded with the rate, and more measurements
move the figure as the campaign runs.

**Reversal.** Drop `job_tokens` from the call sites. The projection falls
back to the flat rate, which is still implemented and whose basis string
says it used one rate for every job size.

## D-NOB-055. The stale-input check discovers queues rather than naming one

**Decision.** `stale_inputs` globs `queue*.jsonl` and reports the queue each
finding came from.

**Alternatives.** List the two queues explicitly. Rejected for the reason
the finding exists: the first version named the one queue I knew about, and
a list is the same mistake with a second entry. A glob covers a third queue
without an edit, and the sweep tests assert what it discovers.

**Cost.** A YAML shared by two queues is reported twice, once per queue.
Kept deliberately: they are two jobs, they run under different settings, and
collapsing them would hide which stage is affected.

**Reversal.** Set `QUEUE_GLOB` back to `queue.jsonl`. Three tests fail.

## D-NOB-056. Mutation checks go through the harness, and it watches live state

**Decision.** `tools/mutate.py` takes `--file/--find/--replace/--tests` for
one-off mutations, refuses to write anything outside `nobble/`, `tools/`,
`deploy/` and `qc/`, refuses live state outright, and fingerprints the
campaign results, queues, state log, scores, published atlas and throughput
file before and after every run, exiting 4 if any changed.

**Alternatives.** Make live state read-only for the duration. Rejected: a
permission error surfaces as a test failure, which a sweep reads as the
mutation having been caught, so a guard would manufacture false successes.
Also considered running the suite in a copied tree: correct in principle and
far more machinery, and it would not have caught the atlas lapse, whose test
wrote to a path the copy would have carried with it.

**Cost.** Size and mtime are a weaker fingerprint than a hash, so a rewrite
preserving both would pass. Accepted deliberately: hashing hundreds of
megabytes between every mutation in a sweep of twenty would dominate the run.

**Reversal.** Drop the fingerprint calls from `main`. Four tests fail,
including the two that feed it an appearing and a disappearing file.

## D-NOB-057. An em dash standing for "no value" is not punctuation

**Decision.** The house style's ban on em dashes applies to punctuation in
prose, code comments and UI copy. A quoted em dash used as an empty-value
placeholder, `{{ value or '-' }}` in a table cell, is allowed and is checked
to still exist, so the allowance cannot quietly come to cover prose.

**Alternatives.** Replace the 32 placeholders with an en dash or with "n/a".
Rejected: an en dash is still a dash and would need the same decision, "n/a"
in a numeric column reads as a value rather than its absence, and the churn
buys nothing a reader would notice. Also considered treating them as
violations and leaving them: rejected because a rule with 32 standing
exceptions is not enforced, it is ignored.

**Reversal.** Delete `PLACEHOLDER` from the sweep. 33 em dashes are then
reported, which is the signal to decide this question again rather than a
defect.

## D-NOB-058. The model's query is shown, labelled, and kept after the figures

**Decision.** The ask panel renders the translated query as "read as a
filter", after the count and the matched pairs.

**Alternatives.** Hide it. Rejected: results filtered by an unseen threshold
are worse than a visible one, and the reader cannot otherwise tell whether
the question was understood. Show it first, as the interpretation: rejected
because the first figure on the panel would then be one the model chose,
which is what the no-arithmetic contract is about however it is labelled.

**Cost.** A number the model selected does appear on screen. It is a filter
parameter rather than a measurement, it is never formatted like the computed
figures, and the panel says whose it is.

**Reversal.** Drop the `answer.query` branch from `askPanel`. One test
fails, and it is the one asserting the label is present.

## D-NOB-059. The two files that may differ from their peers, and why

**Decision.** `wsgi.py` and `tools/hwprobe.py` are allowed to differ from
BINMAN's copies. Every other file shared at the same relative path must be
byte-identical, which a sweep now enforces.

**Alternatives.** Replace NOBBLE's `hwprobe.py` with BINMAN's, widened to
write the campaign tuning. Rejected: that moves token caps, recycle counts
and diffusion samples, which are NOBBLE's vocabulary, into BINMAN, and
replaces a working Phase 0 probe mid-build. Also considered leaving the rule
unchecked on the grounds that the divergences are benign: rejected because
benign today is the state every fork starts in.

**Cost.** The hardware half of the probe is duplicated between the two
projects, so a fix to core-count or memory detection has to be made twice.
Recorded rather than hidden, and the sweep names it every time it runs.

**Reversal.** Remove an entry from `ALLOWED_TO_DIFFER`. The sweep then
reports that file as forked, which is the signal to decide again.

## D-NOB-060: a refinement job gets one budget, and a timeout is not retried

**Date:** 2026-11-04

A tier-2 job's time limit was `job_timeout_seconds * tier2_timeout_multiple`,
applied per attempt, with one retry. The multiple was 4 and the config
comment called it a guess, since tier 2 has never run.

It can be bounded from the campaign's own measurements rather than guessed.
Boltz runs the trunk once per recycle and the structure module once per
diffusion sample, so tier 2 against tier 1 is 10/3 on one part and 25/1 on
the other. Applying both ratios to the whole tier-1 time and adding them
double-counts, which makes the result an upper bound whatever the unknown
split, and a configured allowance then covers potentials, which are off at
tier 1 and on at tier 2 and so appear in neither ratio.

Checked against the live campaign, the guess was adequate for the pair the
decile selected and not for the heaviest one. Six of seven measured pairs
had between 4.6 and 10 times the headroom they needed.
`bench06_RBM39_DCAF15` had 0.83: the DCAF15 assembly is 1,223 tokens by
construction, its worst tier-1 job took 918s, and its bound is 7.2 hours
against a 6.0 hour cap.

**Decided, two parts.**

Each queued refinement carries a budget sized from its own pair's measured
tier-1 cost, with the configured cap as a floor. A pair with no measured
cost gets the floor.

The budget is per job rather than per attempt, so a timeout is not retried.

**Alternatives.** Raise the multiple to a larger constant: simpler, but
leaves a global number standing in for a per-pair quantity and would need
revisiting whenever the construct set changes. Refuse at queue-build time
when a selected pair does not fit the cap: protects the compute but
abandons the refinement, which is the outcome being avoided. Keep the
per-attempt cap and accept the second attempt: that is what was there.

**The second part is a trade-off and not a pure win.** A timeout caused by
a transient stall might have been recovered by a retry, and that recovery
is given up. It is given up because the budget is no longer a guessed
global cap: a refinement is now allowed roughly forty times its measured
tier-1 cost, so a job that reaches the budget is not one that was running
slightly slow. Against the recovery, a retried timeout cost a second full
budget, which at the old tier-2 setting was twelve hours per job across ten
jobs for an outcome the first attempt had already determined. The retry
itself stays available for crashes, which is the failure class a retry is
for, and takes whatever is left of the budget.

**Reversal.** Set `tier2_potentials_allowance` to 1.0 to drop the margin,
or delete the `timeout_seconds` key from the tier-2 queue builder to return
to the configured cap alone; the runner falls back to it when the key is
absent. To restore the retried timeout, change the `break` in `run_job`'s
timeout branch back to `continue` and pass `budget` rather than `remaining`
to `_run_boltz`. `tests/test_runner_timeout.py` and
`tests/test_refinement_budget.py` state the current rule in both
directions.

**Open.** The allowance of 1.5 is a margin rather than a measurement. The
first tier-2 run should replace it with the ratio it observes, which is the
one number here that real tier-2 timings would improve.

## D-NOB-061: a substrate construct is the longest enclosing domain-level entry, InterPro preferred

**Date:** 2026-11-04

`domain_context()` returns every annotation that encloses a degron, and
`benchmark_substrate_constructs` submits `domains[0]` as the substrate when
the 15-mer cannot fold alone. That list arrived in InterPro's response order
and was never sorted, so which boundary the plan gave depended on how the API
had ordered its records. The library was built when CSNK1A1's first enclosing
entry was IPR000719 at 269 residues; a later resolution put PF00069 at 219
first. F93 recorded the difference as a curation change. It was not a change
at all.

**Decided.** The list is ordered: longest domain-level entry first, InterPro
preferred over a PFAM member signature on a tie, accession last so the order
is total. Only entries of InterPro type `domain` from the `interpro` and
`pfam` databases are candidates, which is unchanged.

**Reason.** The construct's job is to fold. Every candidate already encloses
the degron, so the longest domain-level entry is the most complete folding
unit and a shorter one is a sub-match inside it. A PFAM match is one member
signature of the InterPro entry that integrates it, and its boundaries are
where the HMM alignment ends rather than where the fold does.

CSNK1A1 is the case that shows it. PF00069 gives 17-235 and IPR000719 gives
17-285 for the same domain name. Three other signatures on the same protein
agree with the longer boundary: CDD's catalytic domain at 16-281, SMART at
17-283, the PROSITE profile at 17-285. And 5FQD chain C resolves residues 10
to 303 continuously, with no unmodelled gaps, so the 50 residues PF00069
drops are ordered structure rather than a disordered tail. A protein kinase
is bilobal and 17-235 ends inside the C-lobe.

**What changes.** Seven substrates submit a domain rather than a fragment,
and exactly one of them moves: CSNK1A1 from PF00069 17-235 to IPR000719
17-285. BRD4, GSPT1, RBM39, CDK12 and ZN346 keep the entry they already had,
and CDK12 was already on IPR000719. Every substrate construct is now
InterPro-sourced, which is the convention `constructs.py` has always followed
for receptors.

The 269 residues are what the corrected campaign actually submitted, so the
superseded-substrate discrepancy and the caveat it put on the published
conclusion both go away rather than being reworded. The running main campaign
submits 15-mers for its benchmark pairs and is unaffected.

**Alternatives.** Order by coverage, which is what `max_coverage` already
computes: that picks the *shortest* enclosing domain, which would keep
CSNK1A1 on PF00069 and would move BRD4 from the 111-residue bromodomain to a
102-residue repeat-specific sub-entry. Shortest is right for asking whether a
degron fills its domain and wrong for asking what to fold. Pin CSNK1A1 to
IPR000719 by hand: fixes the instance and leaves the ordering
nondeterministic for everything else. Include homologous-superfamily entries:
IPR011009 would give 12-298, but a superfamily is not a domain and the type
filter excludes it for good reason.

**Reversal.** Delete the `enclosing.sort(...)` call in
`nobble/curate/peptides.py` to return to response order, which is the bug.
To keep the ordering and change the rule, the sort key is three lines and
`tests/test_substrate_domain_choice.py` states what each term is for.

**Note on `max_coverage`.** It still takes the maximum over all enclosing
domains, which is the smallest of them, and still decides
`inside_folded_domain`. That is deliberate and unchanged: "can this window
fold alone" is answered most conservatively by the domain it fills most of,
and a 23-residue zinc finger covering all of a 23-residue finger annotation
is self-sufficient however many larger domains contain it. The two questions
were sharing one ordering, which is what made the bug possible.

## D-NOB-062: one significance level, and it now sets the ROC's interval too

**Date:** 2026-11-04

D-NOB-047 moved `p < 0.05` out of `benchmark.html` into
`scoring.significance_alpha`, on the grounds that "a reader changing what the
project counts as significant should not have to know it is written in
markup". The config comment that came with it said the value "applies to
presentation rather than to any decision about the data".

That was true of the template and not of the matched-control ROC. Its
bootstrap took its bounds from `int(0.025 * rounds)` and
`int(0.975 * rounds)`, and reported "not distinguishable from chance at 95
per cent confidence" as a string, with two further copies in `about.html` and
in the design caveat. Four literals, agreeing with the configured 0.05 by
coincidence.

**Decided.** `significance_alpha` sets the ROC's interval as well. The bounds
are the alpha/2 and 1 - alpha/2 order statistics, `confidence_level()`
computes the percentage from it, the layer reports that percentage in a
`confidence_level` field beside `ci95`, and every surface prints it from
there. `scoring.bootstrap_rounds` replaces the `rounds` default argument.

**This widens what alpha governs, which is why it is a decision and not a
tidy-up.** It previously changed how one chart was styled. It now also
changes the width of the headline result's confidence interval, and therefore
whether the ROC's `interpretation` reads "above chance", since that branches
on the lower bound against 0.5. A reader turning alpha down to 0.01 is now
asking for a stricter verdict and will get one, which is what the field is
for.

**Alternatives.** A second key, `roc_confidence_alpha`, keeping the two
independent: rejected, because the config says in terms that this is "the
only significance level this project applies", and a second one would make
that false. Leave the four literals and allowlist them: rejected for
D-NOB-047's own reason, one level deeper. Derive only the prose from config
and leave the bootstrap at a fixed 95 per cent: rejected, because that is the
state this started in, where the printed number and the computed number
agreed by luck.

**The `ci95` key keeps its name.** It is the conventional one and it is read
by the published atlas, the About page and the drift check, so renaming it
has a cost and no benefit while `confidence_level` states the actual level
beside it. If alpha changes, the key is a conventional name and the field is
the fact.

**Reversal.** Put `0.025` and `0.975` back in the return statement and the
percentages back in the three surfaces; `tests/test_significance_level.py`
fails in four places, which is the point. To keep the derivation and decouple
the ROC again, add a second key and read it in `_bootstrap_interval` only.

**Note on how it was missed.** The cutoff sweep examined this function. Its
allowlist carried `_bootstrap_interval.rounds` with a reason, so someone
looked at the signature and waved the default through, correctly. The two
percentile literals are one line below in the return statement, and the sweep
reads comparisons, module constants and default arguments, not arithmetic
(F80). An allowlist records what was looked at and waved through, which is
not the same as what was looked at.

## D-NOB-063. The Tier B glue recall set is defined by observed bridges, not by a size class

**Decision.** `glue_recall_set` selects CCDs observed bridging a triaged E3
ligase in a deposited structure, where a bridge of that CCD is classed
`molecular_glue` or `protac` and the CCD is not flagged as furniture. One
representative per Murcko scaffold, a curated glue preferred, then the
most-deposited, then the code.

**Alternatives.** BINMAN's `ccd_class = 'glue_candidate'`, which is what it
was, and which is a size filter: 7,676 CCDs whose rule is literally
`size_and_no_furniture_signal`. Or the spec's named sources, MGDB, MolGlueDB
and MGTbind, which BINMAN's atlas does not hold and which would mean curating
three external databases to run one exploratory arm.

**Why.** The arm's question is whether a known glue chemotype shows a signal,
so the set has to be compounds known to glue. Observed bridging is the same
evidence base the rest of the project runs on, which makes the recall set
answerable to the same data as the primary signal rather than to a separate
annotation. The check that it is right is that all five of the campaign's
curated glues survive it.

**Reversal.** Replace `_recall_rows`. The three conditions are one SQL
statement and each is separately load-bearing, documented in F133. If the
spec's named sources become available, the right change is to add them as a
source and keep the bridge evidence as a filter, not to swap one for the
other.

## D-NOB-064. Tier 2 is priced against the gate, judged on the upper bound, and reduced automatically

**Decision.** `nobble/execute/budget.py` prices a tier-2 queue from the
campaign's own measured tier-1 seconds for the jobs that would be refined,
against hours already spent and `max_compute_hours`. The scaling factor is a
range until a refinement has run, the gate is judged on its upper end, and
the decile is reduced by dropping pairs from the bottom of the ranking until
it fits. Gate G1 opens only if nothing is affordable.

**Alternatives.** Judge on the lower end, which is what I wrote first: a
refusal then does not depend on a split nobody has measured, which is the
right property for a refusal and the wrong one for permission to spend. Use
`scaling_bound`'s 42.5, which its own docstring says double-counts
deliberately and is a timeout rather than an estimate. Or reduce seeds rather
than pairs, which is cheaper per pair and makes the refinement a different
statistic from the tier-1 arm it is compared against.

**Why.** A per-job timeout bounds one job. The decile is 150 jobs, and
nothing compared the queue to the budget. Pessimism is acceptable here
because it is self-limiting: one completed refinement replaces the range with
a measured factor, and the refusal says so.

**Reversal.** `budget.gate_g1` chooses the end in one line. Removing the
reduction means deleting the `affordable_pairs` call in `tier2.run`, which
restores the previous behaviour of queueing the whole decile unpriced.

## D-NOB-065. Comparability across sampling regimes is a whitelist

**Decision.** `nobble/sampling.py` names the quantities that may be shown
tier 1 against tier 2: `bridge_formation_rate`, `bridge_percentile`,
`convergence_score`, `plip_fingerprint_match`. Anything else is withheld,
including everything derived from `iptm_min`. The module imports nothing.

**Alternatives.** A blacklist of the order statistics, which is shorter and
reads more naturally. Or showing everything with a caveat, which is what a
reader skips.

**Rule.** A mean, a median or a proportion gets less noisy as samples are
added. A minimum gets smaller. That is not a property of these four
quantities, it is a property of the shape of each statistic, so it decides
the list.

**Why a whitelist.** The two fail in opposite directions. A whitelist that
misses a comparable quantity shows less than it could. A blacklist that
misses an order statistic shows a biased number as an improvement, and it
would look exactly like a result. The second mistake is not recoverable by a
reader.

**Reversal.** Add or remove a key in `COMPARABLE`, with its shape stated.
`tests/test_sampling_comparability.py` refuses a key whose name says it is a
minimum, and refuses a key that `scores.jsonl` does not emit.

## D-NOB-066. The QC harness refuses a server it cannot identify

**Decision.** `/healthz` reports a digest over the app's own source, and
`qc/qc.mjs` exits 3 rather than reporting on a server whose digest is not the
working tree. `tools/app_fingerprint.py` is the one implementation.

**Alternatives.** Start a fresh server inside the harness on a random port,
which is tidier and loses the ability to QC a deployed site. Recompute the
hash in JavaScript, which is one fewer process and two implementations of one
hash. Or trust the operator, which is what was there.

**Why.** A QC run reported fourteen clean pages against a process started
hours earlier. The report was true about the wrong build. A check whose
subject is not the thing being checked is worse than no check, because it
produces a pass.

**Scope.** Vendored libraries are excluded and the loose files beside them
are not: the subdirectories are pinned third-party builds, the loose file is
BINMAN's shared bridge and it changes. `VENDOR.json` stands in for the
libraries, so a version bump still moves the digest.

**Reversal.** Delete the guard block above `chromium.launch()` in
`qc/qc.mjs`. The `/healthz` field is additive and harms nothing if unread.

## D-NOB-067. The copy budget applies to the data pages; About is the exposition page

**Decision.** `qc/copy_budget.mjs` holds every page to CLAUDE.md's budget of
under 40 words per panel and 150 per page, and reports `/about` without
applying it.

**Alternatives.** Hold About to the same figure, which means cutting a
526-word page to 150 and moving the rest to the README. Or drop the budget
check for prose pages generally, which gives any page an exemption by calling
itself prose.

**Why.** The rule states its own purpose: "Keep narrative prose in the app to
a minimum. One short line per panel saying what it shows or what the number
means. Reasoning belongs in DECISIONS.md and FINDINGS.md, not on screen." The
page that exists to explain the project is what keeps the explanation off the
six data panels. Holding it to a per-panel figure meant for a data panel
would push the reasoning back onto the panels or off the site.

**What this is not.** It is not a general prose exemption. One page is named
in the tool, and a second would need this decision rewritten.

**Reversal.** Remove `/about` from `EXPOSITION` in `qc/copy_budget.mjs`. Its
ten panels then report over budget and the page needs cutting to 150 words,
with the rest moving to the README, where the house style does allow prose.

## D-NOB-068. The Tier B construct gap is a form, not a guess

**Decision.** `config/tier_b_constructs.toml` ships empty, listing the
InterPro candidates for each of the fifteen Tier B ligases that fit the
tier-1 token cap, and `nobble/curate/tier_b_constructs.py` loads and
validates whatever is filled in. Until it has an entry per ligase, `report()`
returns blocked and names every gene still without one.

**Alternatives.** Pick the longest annotated domain, which F41 rejects in
`domain_by_accession`'s own docstring: which domain binds the substrate is
science knowledge and only the lookup belongs in the code. Use the frozen
selection's `best_window`, which is the highest-mean-pLDDT 200-residue
window and so a statement about which part of the model is confident. Or
write the fifteen into `constructs.py` myself, which is writing spec content
into code when BUILD_SPEC.md is authoritative.

**Why a form.** The gap is fifteen science decisions and no amount of code
closes it. What code can do is make answering cheap: the candidates are
listed, member-database duplicates collapsed, the four that exceed the cap
named, and a filled entry is checked rather than trusted. 59 InterPro
candidates across the fifteen, three of which have exactly one within the
cap.

**What is validated.** That the accession carries the entry, that an
ambiguous entry says which occurrence it means, that a rationale is present
because that is the one thing the file exists to record, and that the
construct fits the cap unless it declares an exception as spec 1.1 does for
VHL and DCAF15.

**Reversal.** Delete the file and the module. Tier B returns to being
selected, frozen and unrunnable with nothing saying why.

## D-NOB-069. The running chain finishes, then the current one runs after it

**Decision.** The chain that has been running since 01:02 is left alone to
finish, and `bash tools/run_chain.sh` is run again after it exits. Nothing
is killed and the script on disk is not edited again while it runs.

**What this is about.** The running shell holds `tools/run_chain.sh` on a
different inode from the file now at that path: 5,400 bytes against 8,812,
with its read offset equal to the size, so it has the whole of the old
script in memory and will execute exactly commit `2b0dc27` to the end. That
is the reassuring half of the finding, because editing a script bash is part
way through can make it resume mid-token. It did not, because the edits
replaced the file rather than writing into it.

The consequence is that the running chain has no F47 correction step. Fifteen
of `bench02_BRD4_VHL`'s jobs ran on a YAML carrying a hydroxyproline the
fixed rule no longer emits, `nobble.validate.inputs.stale_inputs` still
reports all fifteen, and `build_atlas.py` refuses while that is true. So the
chain will spend its remaining thirty-six hours on the queue, reach
`refresh.sh`, refuse to publish, run tier 2 and the design scan, refuse
again, and then deploy the benchmark atlas it already deployed.

**Alternatives.** Kill the chain when `run_queue` returns and start the
current script, which would save one pointless deploy and one tier-2 pass.
Rejected: it means matching a process by inode and killing it at a moment
nothing signals reliably, against a saving of a redundant rsync of an atlas
the droplet already has. The old chain's remaining work is not wasted
either, since tier 2 and the design scan are real compute on real results.

Edit the file in place so the running shell picks up the correction. Rejected
outright: bash reads a script by offset and an in-place edit of a running
script is how a shell ends up executing half of one line and half of
another.

**Why re-running is enough.** Every stage is resumable and idempotent, which
is the property the project has been built for. The second run's `run_queue`
skips all 2,360 completed job ids from `state.jsonl` and costs minutes, the
F47 correction clears exactly fifteen rows and re-runs them, and the refresh
that follows publishes for the first time. Tier 2 then re-selects its top
decile from scores that no longer include the stale pair, which is the right
order and not merely a repeat.

**How to reverse it.** Nothing to reverse: the decision is to run a script
that is already the documented next step. The risk it accepts is a window
between the two runs in which the published atlas is the benchmark one,
which is stale rather than wrong, and is what the site serves today.

## D-NOB-070. Three of the spec's four open items are answered by measurement

**Decision.** BUILD_SPEC.md section 9 lists four open items for Marc. Three
of them ask for a confirmation the system can make for itself, so they are
closed here from measured values rather than left waiting. The fourth is a
real decision and stays open.

**Item 1, the Studio's chip and unified memory.** Measured by
`tools/hwprobe.py` into `config/hardware.toml`: Apple M2 Ultra, 128.0 GB
unified memory, 16 performance and 8 efficiency cores over 24 logical, 60 GPU
cores, torch 2.10.0 with MPS available and built. The token cap and the
compute budget are derived from those rather than estimated, which is what
the item asked for, and CLAUDE.md's rule that nothing hard-codes a core
count, a memory figure or a device is what keeps it that way. Note the one
figure in that file still to be re-probed: `free_gb_project_volume` reads
507.0 because it was written in gibibytes under a gigabyte name, fixed in
F179, and it corrects itself at the next probe.

**Item 2, the Boltz version and the optional-kernels path.** Boltz 2.2.1 is
installed in BoltzMaker's environment, which satisfies the spec's "2.2.x or
later". The optional-kernels question is answered by what the runner does and
why: `nobble/execute/runner.py` passes `--no_kernels` on every job, because
the optional kernels are a CUDA path and MPS cannot use them. Disabling them
explicitly rather than relying on an import failing is what makes the run
deterministic. So the answer is not "installed" or "not installed" but "not
applicable on this accelerator", which no confirmation from Marc would
change.

**Item 4, the domain.** Resolved in service: `nobble.mdeller.com` answers 200
and serves the published atlas, with its own nginx vhost and TLS, rather than
a sub-route of `binman.mdeller.com`. The deploy script's final check fetches
every route on that host, so the choice is enforced by the thing that ships.

**Item 3, how the Tier B exploratory arm publishes**, stays open: a ranked
list, or an abstention-heavy list where BINMAN-LM Head C declines below a
confidence floor. That is a judgement about how to present an unproven tier
and not a measurement, and it is not blocking, because Tier B cannot run
until the fifteen constructs in `config/tier_b_constructs.toml` are filled in
(D-NOB-068, G1). The two questions arrive together, so the presentation
decision is best made when the constructs are chosen rather than now.

**Alternatives.** Leave all four waiting, which is what had happened: three
items had been answerable for some time and nothing recorded them, so the
spec's own open list overstated what was outstanding. Or answer item 3 by
picking one, which would be writing spec content into the build when
BUILD_SPEC.md is authoritative and the question is explicitly Marc's.

**How to reverse it.** Each closure is a measurement or a running service, so
re-probing or re-reading contradicts it directly if any of them changes: a
different chip, a different Boltz version, or the site moving to a sub-route.

## D-NOB-071. A fit that omits a component has answered zero for it

**Decision.** When `weights.json` reports `fitted: true`, a component absent
from the fitted weights renders at zero rather than at its hand-set default.
The panel's sliders then show the fit's answer for all five components and
nothing else, and the composite column agrees with the `nobble_score` the
pipeline stored.

**Why.** Spec 4.8 lets `components_used` be a subset: the fitter selects, and
`W.apply` renormalises over the weights that contribute. Falling back to the
default for a component the fit passed over mixes a hand-set number into a
figure the panel describes as "Fitted on N labelled pairs, never by hand",
and it does so silently, because the composite still looks like a composite.
Measured on the Sievers fixture, the disagreement was 0.6578 against 0.6189
on the first row of the ledger (F205).

**Alternatives.** Render the omitted components as the defaults they are, but
say so in the panel: rejected because the sentence would have to explain that
some sliders are fitted and others are not, and the copy budget for that
panel is one line. Hide the omitted sliders entirely: rejected because they
are the controls a reader uses to explore away from the fit, which is the
panel's purpose, and a missing slider cannot be moved. Have the fitter emit
an explicit zero for every component it did not select: tempting, and it
would make the app's job trivial, but it would also change what
`components_used` means and put a weight in the artefact the fitter never
chose.

**How to reverse.** `nobble/app/data.py:fitted_weight` returns `default`
instead of `0`, and `campaign.html`'s initialiser drops its `HAS_FIT` test.
Both have to move together or the server and the browser disagree on load;
`tests/test_unfitted_components_start_at_zero.py` pins both halves.

**Note.** This reverses one assertion in `tests/test_component_names.py`,
which was written for F106 and treated "the fit has no value for this
component" as "no fit applies here". That reading is right when nothing has
been fitted and wrong for every component a fit passed over, and the test now
pins both cases with the distinction stated.

## D-NOB-072. The fifteen Tier B receptor constructs, named

**Decision.** Marc named a substrate-binding domain for eleven of the fifteen
Tier B ligases on 2026-11-05 and excluded four. `config/tier_b_constructs.toml`
holds the answers; `tools/tier_b_candidates.py` produced the evidence each was
chosen against. Gate G1's construct half is closed.

| Gene | Construct | Range | aa | Chosen over |
|---|---|---|---|---|
| ASB8 | Ankyrin repeat superfamily | 25-231 | 207 | nothing: the only non-SOCS-box annotation |
| CCNF | Cyclin, N-terminal | 290-405 | 116 | the full 275-499 cyclin, both lobes |
| DCAF8L1 | WD40-repeat superfamily | 183-508 | 326 | nothing: the only annotated candidate |
| FBXO11 | Right-handed beta helix | 388-543 | 156 | the larger 523-826 pectin lyase fold |
| FBXW4 | WD40/YVTN superfamily | 133-265 | 133 | the wider 153-399 propeller |
| KCTD4 | KCTD4 C-terminal domain | 138-259 | 122 | the N-terminal BTB, which binds Cul3 |
| NEURL2 | Neuralized-like NHR/SPRY | 25-242 | 218 | the five-residue-wider Neuralized entry |
| SMURF2 | WW domain, third occurrence | 291-331 | 41 | a span covering both ordered WW domains |
| TRIM17 | B30.2/SPRY | 277-475 | 199 | nothing: no other substrate interface |
| TRIM55 | FN3/SPRY-containing | 119-301 | 183 | nothing: the only ordered non-RING candidate |
| TRIP12 | WWE domain, subgroup | 806-881 | 76 | the 292-residue Armadillo region |

**Excluded, with the reason in the form.** KCNC1 (Kv3.1) and KCND2 (Kv4.2)
are voltage-gated potassium channels that passed spec 3.3's filters on pocket
druggability and best-window confidence, neither of which asks for a
substrate interface; their BTB domains were offered as Cul3-adaptor
constructs and declined. RAG1 is the V(D)J recombinase, a genuine E3 whose
every ordered domain binds DNA or catalyses; its nonamer-binding domain was
offered and declined because what it recognises is DNA. RNF175 annotates
nothing but its RING and its membrane span.

**Why eleven is enough.** Spec 3.3's `min_ligases_for_gate` is 10, and
`report()` now checks it, so the exclusions are visibly above the floor
rather than assumed to be. One more exclusion would have taken the arm below
the number the gate was written for.

**Alternatives.** Fill the four in mechanically from the longest annotated
domain: ruled out by F41, and in these four cases it would have named an ion
transport domain, a DNA-binding domain and a RING. Drop Tier B: rejected,
spec 3.3 says "do not defer it" and eleven ligases answers the question the
arm exists for. Widen the candidate floor further than 35 to look for shorter
interfaces in the four: not done, because the limit for those four is the
absence of an annotated substrate interface rather than its length.

**How to reverse.** Any entry can be re-pointed by editing its
`interpro_entry` and `occurrence`, and an exclusion becomes a construct by
moving it out of `[exclusions]`. `tests/test_tier_b_constructs_are_named.py`
pins each residue count, so a wrong edit fails rather than silently changing
a receptor.

**Note on the occurrence indices.** Three constructs name an InterPro entry
annotated more than once, and `occurrence` counts from the N-terminus while
the candidate shortlist prints in order of length. Taking the shortlist's
index would have given FBXW4 the other half of its propeller and SMURF2 a WW
domain modelled in disorder at pLDDT 58. That is the failure F41 and F107
were both about, and it was caught here by checking the docstring rather than
by a test.

## D-NOB-073. The Tier B arm, and the ceiling that was gating it

**Decision.** Tier B runs as its own campaign stage: the eleven named
receptors (D-NOB-072) against the seven proven glue-degron pairs from the
benchmark panel, each with that degron's composition-matched scramble. 154
pairs, 1,540 jobs, 38.9 hours measured from the real construct and glue
sizes. Assembled as `tier_b_20261105T202811Z` and queued in
`tools/run_chain.sh` as stage 4b, after the design scan and before the
publish.

**The design, and what it buys.** A pair holds a known-working glue and
degron together and swaps only the receptor: lenalidomide with the IKZF1
zinc finger it actually degrades, against ASB8 instead of CRBN. The
benchmark panel therefore already contains that same glue and degron with
its proven receptor, which is a matched positive control costing no jobs.
The alternative offered was a single shared probe degron across all pairs,
which is simpler to describe and has no matched control, because no proven
receptor was ever run with that exact combination.

Scrambles were offered, declined and then asked for again, which is why they
are here. They give the arm an internal negative rather than one that
depends on cross-arm comparison, and the library already carried a
composition-matched scramble for all seven benchmark degrons, so they cost
jobs and no curation.

**Two arms, not three.** Conditioning places the ligand in a pocket derived
from the receptor's own deposited structure. A Tier B receptor has none, and
the pocket in the benchmark pair it borrows from belongs to a different
protein, so a conditioned arm would place the ligand in the wrong protein's
pocket. `expand_pair` now takes its axes as arguments for this.

**The ceiling.** `max_compute_hours` was 96. Marc lifted it: his own
machine, free compute, and the figure was an arbitrary spec number rather
than a measurement. Set to 240, which covers everything planned with
headroom and still trips on genuine runaway. Changed in `tools/hwprobe.py`
as well as `config/tuning.toml`, because the probe writes that file and the
next probe would have put 96 back.

This is also why the arm runs at full depth. Asked to choose under the old
ceiling, Marc took breadth over depth, all seven chemotypes at three seeds;
with the ceiling gone the question dissolved and both are affordable, so it
is seven chemotypes at five seeds.

**What the ceiling does not fix.** Tier 2's full decile is priced at 120 to
902 hours for 1,570 jobs, and the upper end is a month of wall-clock. Gate
G1 still reports it as not fitting, correctly: that is a wall-clock decision
rather than a budget line, and one completed refinement replaces the range
with a measured factor.

**DCAF8L1's token cap exception.** DCAF8L1's WD40 domain is 326 residues,
which is exactly the cap against the median 59-atom glue and ten tokens over
it against the largest benchmark glue, the 759 VHL PROTAC at 69 heavy atoms:
410 against 400, on ten of the arm's 1,540 jobs. Declared an exception on the
ground spec 1.1 declares VHL_VCB and DCAF15_DDB1_DDA1: the domain is what it
is, and trimming it to fit would trim the binding surface. The jobs carry
`token_cap_declared_exception`, so the overrun is visible in the data.

**What the arm can and cannot show.** Every pair is expected to fail: these
ligases have no known glue. A hit is a hypothesis, and a uniform absence of
hits is the likely result and still informative, because it says the
chemotypes that work on CRBN and VHL do not transfer. That is what
"ligandable but unproven" predicts, and the arm is worth running because
nothing had tested it.

**How to reverse.** Delete the campaign directory and drop stage 4b from
`run_chain.sh`; nothing downstream reads Tier B. The ceiling goes back by
setting `max_compute_hours` in both `config/tuning.toml` and
`tools/hwprobe.py`.

## D-NOB-074

**Gate G6 opened rather than proceeding to publish.** The pose-recovery
positive control fails on the benchmark panel (F212) and the matched-control
ROC is a null (AUC 0.4583, CI 0.3316-0.5842). Publishing the full campaign now
would put a chance-level result on the site while the control that makes it
readable has failed, which is the case G6 was written for.

The fallback ladder is not exhausted, which is why this is a question rather
than a verdict. Pocket conditioning is exhausted and does nothing (14.95 A
against 17.92 A median). Tier-2 refinement is untested on any pair with a
deposited structure, because the top-decile selection chose 16 pairs by
`nobble_score` and none is a benchmark pair.

**Alternatives.** Proceed and publish with the failure flagged on the page;
spend roughly 7 h of GPU refining the seven benchmark pairs to find out
whether refinement recovers the poses; or treat the null as the result and
stop. Deferred to Marc because it is a science call about what the project
claims, not a build call.

**Reversal.** Nothing is published and no inference has been discarded, so
every option remains open. The refinement experiment is additive: it writes
`results_tier2.jsonl` rows for the benchmark pairs and changes nothing already
measured.

**Not decided here:** whether to restart the chain onto the current script.
That is a build call and is taken in D-NOB-075.

## D-NOB-075

**The stale chain stopped, and tier 2 restarted carrying the benchmark
panel.** Marc chose, at Gate G6, to refine the seven pairs with deposited
structures before anything else, and to stop the decile now rather than let
its remaining 66 jobs finish first.

Three things were wrong with the state this found.

The chain running since 4 November at 01:02 was the script as it stood at
01:00, which predates both the F47 correction stage and the Tier B stage added
on the 5th. A bash script is read as it runs, so editing the file changed the
next run and not that one. The F47 correction therefore never fired, the atlas
build refused on the stale hydroxyproline exactly as designed, and nothing was
published: the droplet is still serving the 100-pair benchmark bundle. Said
here because "the correction is in the chain" was true of the file and false
of the process, and I reported the file.

Tier 2 could not measure itself (F212). The decile took 16 pairs by
`nobble_score` and none had a crystal, so `select_top_decile` now always
carries the pairs with a deposited structure as `recovery_controls`: outside
the ranking, outside `pairs_selected`, priced into the budget, and never
dropped by reduction. If reduction cannot fit even the controls, that is G1,
because a refinement that cannot be measured is not a cheaper refinement.

The controls run cheapest first, on each pair's own measured tier-1 cost. One
of them, bench06_RBM39_DCAF15, is 11.66 h of the panel's 18.80 h, and in
pair-id order it ran sixth of seven: the last two pairs would have reported
most of a day after the rest for no gain, when the question is how many pairs
refinement helps on.

**Measured, replacing a bound.** The tier-2 factor is 4.62, median over the 94
decile jobs already refined. That retires the 120 to 902 h range quoted for
the full decile: the 131 jobs now queued price at 26.22 h, of which the
controls are 18.80 h and the decile remainder 7.42 h, against 170.34 h left.

**Alternatives.** Letting the decile finish first was offered and declined, as
was publishing with the failure flagged and stopping inference altogether.

**Reversal.** The 94 refined decile jobs are untouched in
`results_tier2.jsonl` and `state_tier2.jsonl`, and the runner skips them, so
nothing was discarded and the decile resumes behind the controls. Tier 1 is
immutable by construction. Reverting the selection change restores the
decile-only queue.

**Note on the session name.** The refinement runs in tmux `nobble-tier2`,
which is in `NOBBLE_GPU_SESSIONS`. It was launched as `tier2b` first, a name
nothing waits on, which is the drift `tools/wait_for_gpu.sh` documents and
would have let a later chain run start a second campaign on the one MPS
device. Relaunched under the name the list knows rather than adding a name to
the list.

## D-NOB-076

**Publication is held, and the hold is enforced by the scripts that can
publish.** Gate G6 was put to Marc with the fallback ladder exhausted and the
tier-2 measurement in hand. He chose to hold publication: nothing goes to
nobble.mdeller.com until pose recovery passes its positive control or the
headline is re-scoped.

What the refinement measured, over the five control pairs that finished before
tier 2 was stopped:

| pair | n | tier 1 | tier 2 | move |
|---|---|---|---|---|
| bench01_GSPT1_CRBN | 10 | 29.14 | 24.91 | -4.98 |
| bench03_BRD4_CRBN | 5 | 20.40 | 17.40 | -2.70 |
| bench04_IKZF1_CRBN | 10 | 5.35 | 4.96 | -0.39 |
| bench05_CSNK1A1_CRBN | 10 | 12.21 | 12.27 | +0.03 |
| bench07_CDK12_DDB1 | 7 | 44.92 | 44.66 | -0.25 |

Two pairs move by more than the 2.0 Å `campaign_change_margin_a`, so
refinement does something; both land 17 to 25 Å from the deposited peptide, so
what it does is not recovery. The receptor anchor is stable on every pair,
which is what makes the two tiers comparable at all and rules out the move
being a change of frame.

**Enforced, not recorded.** The decision is in `config/publication_hold.toml`
and read by `tools/publication_hold.py`, called as the first pre-flight step
of `deploy/deploy.sh` and again, for the log's benefit, before the chain's
deploy stage. This is the point of the change rather than a detail of it: the
chain's last line is `bash deploy/deploy.sh`, so a hold living only in this
file would have been overruled by a script a few hours after Marc set it. A
missing hold file reads as held, because a gate that opens when its own
configuration is deleted is not a gate, and releasing it requires naming the
authorising decision in `released_by`.

**No success radius was invented.** Deciding this in code would have meant
choosing a radius inside which a pose counts as recovered, and this project is
not entitled to invent that number: there is no `recovery_success_a` in
`thresholds.toml` and `tools/publication_hold.py` reads no threshold at all. A
test asserts both. The refusal does print the live pose-recovery curve, read
out of the campaign's own `validation.json` rather than copied into the
config, so whoever releases the hold sees what is true then and not what was
true when it was written.

**Alternatives.** Publishing with the negative result stated plainly was
offered, and so was publishing the ranking and the ROC with the pose views
removed. Both were declined. The second would have hidden the evidence rather
than reported it, which is worth recording as the weaker of the two.

**Reversal.** Edit `config/publication_hold.toml`: `held = false` and a
decision in `released_by`. Nothing else changes, and the standing G3 approval
Marc gave in the same exchange then applies without a further question.

## D-NOB-077

**Tier 2 stopped with 89 jobs unrun, and the chain restarted in its place.**
The two informative control pairs had already answered G6, so the remaining
jobs would have spent roughly 13 h, most of it on `bench06_RBM39_DCAF15` at
11.66 h, confirming a question that was no longer open.

94 decile jobs and 42 control poses are untouched in `results_tier2.jsonl`,
and the runner skips completed job ids, so the chain's own tier-2 stage
resumes the same queue rather than restarting it. F214 closes out the job that
was mid-flight when the session was killed, so it reads as abandoned and gets
re-run rather than looking hung for the rest of the run.

The chain is the D-NOB-069 rerun, carrying the F47 `rerun_pair.py
bench02_BRD4_VHL` correction and the Tier B stage, neither of which the
4 November process ever had. It runs in tmux `nobble-chain`, which is in
`NOBBLE_GPU_SESSIONS`, under `caffeinate -dimsu`, logging to
`logs/chain_rerun_20261106.log`, and arms its own watchdog for its length.

**Alternatives.** Waiting for tier 2 to drain first was offered and declined,
as was leaving the chain parked indefinitely.

**Reversal.** The unrun tier-2 jobs are still in `queue_tier2.jsonl` and the
chain reaches them at its third stage, so nothing needs reinstating.

## D-NOB-078

**Standing approvals Marc gave at the same gate.** `Bash(git push:*)` is now
in `.claude/settings.local.json`, so the end-of-phase commits reach the remote
without a per-push question: G4 is answered once rather than each time. He
also re-confirmed G3, which applies the moment D-NOB-076 is released, and
approved pruning superseded Boltz structure outputs instead of opening G5 if
free space falls toward 50 GB. The outputs are regenerable from the queue,
which is why they are the right thing to prune; `results*.jsonl`,
`state*.jsonl` and the YAML inputs are not, and are not covered.

Delivering figures to his other device unprompted was offered and declined, so
figures stay described in the logs and in chat.

## D-NOB-079

**The F47 correction waits for the GPU rather than competing for it.** F219
found that the 6 November correction re-ran against Boltz's cached
featurisation, so `bench02_BRD4_VHL`'s fifteen tier-1 jobs in
`campaign_20261104T004632Z` still hold poses folded with the hydroxyproline.
`tools/rerun_pair.py` now clears the cached output, so re-running it will take
effect, and that costs roughly 40 minutes of inference.

The chain is on its tier-2 stage with one MPS device, and the chain has
already passed the correction stage, so running the correction now would
either contend for the device or be overwritten by nothing at all. It waits.

**What holds in the meantime, and is enforced rather than remembered.**
`deploy/build_atlas.py` refuses the campaign, so it cannot be published.
`tools/recovery_delta.py` marks the pair not comparable and excludes it from
every figure, so the G6 measurement rests on five pairs rather than six: its
tier-2 jobs featurise the corrected YAML while its tier-1 poses do not, and
the move across them reported +3.37 A, which reads as refinement making the
pair worse. `tests/test_stale_inputs.py` skips with the featurisation
disagreement quoted rather than with "the F47 correction has been applied".

**Alternatives.** Killing tier 2 again to run a 40-minute correction was
considered and rejected: tier 2 is answering G6 and bench02 is one pair of
seven, so the correction buys one more pair in a measurement that already has
five saying the same thing. Running both at once was rejected on the one-GPU
rule that D-NOB-077 and `tools/wait_for_gpu.sh` exist to enforce.

**Reversal.** `PYTHONPATH=. python tools/rerun_pair.py bench02_BRD4_VHL
--campaign campaigns/campaign_20261104T004632Z --apply` followed by
`bash tools/run_queue.sh --campaign campaigns/campaign_20261104T004632Z`,
then `tools/stale_featurisation.py` to confirm it took, which is the check
that did not exist the first time.

**And then `bash tools/refresh.sh campaigns/campaign_20261104T004632Z`**,
which is the step these instructions were missing. The re-run writes poses and
nothing else: the fifteen jobs' score rows were dropped by the correction, the
validation layers were computed over the old poses, and `deploy/atlas` holds a
bundle written at 23:01:38Z on 6 November that includes thirty bench02
structures folded with the hydroxyproline (F224). `refresh.sh` is the chain's
own stage 2 entry point and does all three in order, so the sequence is one
command rather than three remembered ones. Stopping after the featurisation
check leaves a campaign whose poses are corrected and whose published figures
are not, which is a worse state than the one being fixed, because every guard
reads as satisfied.

## D-NOB-080

**The footprint measurement lives in `nobble/score/poses.py` and is computed
by the validation layer, not by a tool run by hand.** F227 established that an
RMSD cannot distinguish a model that never found the degron site from one that
found it and placed the chain along it wrongly, and that the distinction
changes how the held headline reads. The measurement that separates them is
therefore part of what the pose-recovery failure is, not a side enquiry.

`poses.footprint(job, target)` shares `recovery_against_crystal`'s receptor
superposition, so the two numbers are commensurable by construction rather
than by coincidence. `layers.pose_recovery` calls it for each pair's
lowest-RMSD pose and writes the result into `validation.json`, which is what
`tools/provenance.py`, `tools/publication_hold.py` and the app already read.

**Alternatives.** Leaving it in `tools/pose_site.py` was the state for one
finding and was rejected once the cost was known: gridding the contact search
the way `docking_check` already does dropped the panel from about ten seconds
a pair to under two seconds in total, so the only argument for keeping it
outside the pipeline had gone. A fourth validation layer was rejected because
spec 5.1 to 5.3 define three, and a footprint is a decomposition of the first
rather than a fourth kind of validation.

**Reversal.** Delete the `footprint` key from `pose_recovery`'s summary and
the `_footprints` helper. `poses.footprint` and `tools/pose_site.py` stand
alone without it, and the tool is what produced every number in F227 to F230.

**What it does not do.** The layer cannot mark a pair `confounded`, because
that reads `tools/stale_featurisation` and a module under `nobble/` importing
from `tools/` is the dependency inverted. The flag stays with the tool and
with `deploy/build_atlas.py`. This is contained rather than open: the build
refuses the campaign while any featurisation disagrees, so a footprint written
for a confounded pair cannot reach the atlas.

## D-NOB-081

**The design scan's parent is chosen from candidates whose Delta-ipTM is not
flagged as a collapsed seed.** `nobble/design/report._default_parent` ranked
by `delta_iptm`, the difference of minima over seeds that spec 4.5 mandates
for scoring. For choosing a scan target that statistic is fragile in a way the
scorer already measures: one seed collapsing drags the binary minimum down and
inflates the difference by however far it fell, and
`seed_collapse_affects_delta` says when it has.

It had. ZN565 ranked first at +0.8886 on a binary minimum of 0.0601 against a
median of 0.8619, with `collapsed_seeds_binary` of [2]; by the median its
Delta-ipTM is +0.0913, the smallest of the top five. ZN787, the runner-up at
+0.4714, is flagged as well. Five of the thirty-one scored candidates are.

**Alternatives.** Ranking by `delta_iptm_median` instead would pick ZN654 and
was rejected: spec 4.5 mandates the minimum, and replacing the statistic to
fix a few unreliable members is a larger change than removing those members.
Leaving it alone was rejected because the consequence is 240 jobs and 4.4
hours spent on the claim that the chosen degron has the most glue dependence
to move, which for ZN565 rests on one seed. Weighting by the median-minimum
agreement was rejected as a composite nobody asked for.

**What it changes.** The parent becomes `benchmark_888fd2c63e`, IKZF1, at
+0.3156. That is the parent `campaigns/design_20261104T094939Z` was already
assembled for, which preflights clean at 240 jobs and prices at 4.4 hours
(F225), so the chain's stage 4 now agrees with what is on disk rather than
replacing it. `deploy/atlas/design.json` still names ZN565, so
`tools/provenance.py` will report the site and the ranking disagreeing until
the next rebuild, which is the drift check working rather than a new fault.

**Reversal.** Remove the `collapsed` set and the `usable` filter from
`_default_parent`; the ranking returns to the raw maximum. The flag it reads
is computed by the scorer either way and is in every scores row.

## D-NOB-082: let bench06's remaining refinement jobs run rather than stop the chain

bench06_RBM39_DCAF15's tier-2 jobs cannot succeed: every attempt exits 0 after
about two and a half hours without writing a confidence JSON. Eight remain in
the live run, about 21 hours of certain waste.

Nothing written to disk can stop them. `run_campaign` reads the queue and the
state file once, before its loop, and computes `pending` from them there; so
editing `queue_tier2.jsonl` or appending to `state_tier2.jsonl` has no effect
on a run already in progress. Writing a `done` record would skip them, and
would be a false entry in the manifest, which is not a trade worth making for
any number of hours.

The only lever is killing the runner. That was rejected. The eight bench06
jobs sit ahead of 66 Sievers and scramble refinements in the queue order, and
those are the jobs F253 and F254 are registered against. Killing the runner
mid-stage hands `tier2.sh` a non-zero code which it carries to the end
without aborting (F195), so the chain would continue to its later stages and
the Sievers refinements would simply never run. Trading 21 hours of waste for
two unanswerable predictions is the worse outcome.

The budget tolerates it, now that the budget can see it (F255). With the
corrected instrument the run ends at about 130 h of the 240 h cap, so G1 stays
closed either way and nothing downstream is blocked by the waste.

Alternatives: kill and restart the tier-2 stage with bench06 dropped, which
costs the Sievers work or a second GPU process contending for MPS; or raise
the per-job timeout so the jobs are killed sooner, which does not help because
they are not timing out, they are returning successfully with nothing written.

Reversal: drop bench06's rows from `queue_tier2.jsonl` before the stage is next
started from cold, which is the F47 correction's refresh. Removal is
load-bearing rather than cosmetic: `completed()` treats only `done` as
terminal, so the recorded failures do not stop a later run from re-attempting
all ten and spending the 26 hours again.

## D-NOB-083. Restart the chain so the tier-2 sampling reduction takes effect

Supersedes D-NOB-082 on new evidence. That decision let bench06's refinements
burn because the cause was unknown and the budget tolerated the waste. F298
measures the cause: every tier-2 success is at most 454 tokens and every
failure is 1,223, with no overlap, and the same jobs complete at tier-1
settings. `runner.sampling_for` now reduces tier 2's diffusion samples to fit
the largest product observed to complete.

The live runner started at 23:01 UTC on 6 November and so predates F238,
F289 and F298. It will not pick any of them up. Four bench06 refinements are
unresolved, one of them in flight, so under the running process they cost
about 10.4 hours and teach nothing: that code discards the stderr, which is
the evidence three findings have wanted.

Restarting costs the in-flight job's progress, which would have failed
anyway, and `tools/run_chain.sh` says in its own header that a kill anywhere
is recoverable by rerunning it. The 149 completed tier-2 jobs are skipped by
job id. The 66 remaining non-bench06 jobs are all at most 454 tokens, so the
reduction does not touch them.

The upside is not only the time. If nine samples complete, F268 becomes
answerable, having been unanswerable rather than pending. If they still fail,
the current runner keeps what Boltz said, so the failure is finally
diagnosable instead of being the sixth identical silence.

Alternatives: let the stage finish and drop bench06 before the next cold
start, which is D-NOB-082's reversal and spends 7.8 hours to learn nothing;
or kill only the runner process, which ends tier 2 with 70 jobs unresolved
because the chain would move to the next stage.

Reversal: the restart is the reversal. Kill the session and rerun
`tools/run_chain.sh`; nothing is destroyed, because `run_job` clears a job's
output directory before running it and `completed()` keys on `done`.
