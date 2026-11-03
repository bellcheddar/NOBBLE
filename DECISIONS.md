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
