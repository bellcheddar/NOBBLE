# NOBBLE build log

2026-11-03T18:39:32Z  Phase 0: hardware probe written and run. Apple M2 Ultra, 16P/8E cores, 128 GB, 60 GPU cores, 507 GB free, MPS available on torch 2.10.0.
2026-11-03T18:53:39Z  Phase 1: BINMAN store reader. All 12 curated sources present; row counts match spec 2.1 exactly. Degronopedia and ProtCID confirmed unavailable (BINMAN G7).
2026-11-03T18:53:39Z  Phase 1: benchmark panel resolver. 7/7 resolve. MGTbind encodes multi-protein receptors as underscore-joined composite accessions, so matching is by token set; MGTbind carries no PROTACs, so the two BRD4 arms resolve from PROTAC-DB (5T35, 6BNB).
2026-11-03T18:53:39Z  Phase 1: all seven benchmark depositions already present in BINMAN's assembly cache. Ligand CCDs read from structure: 85C, 759, Y70, LVY, EF6, RC8.
2026-11-03T18:53:39Z  Phase 1: GSPT1 degron gate failed, then resolved. Root cause was a numbering frame mismatch of 138 residues, not a Degron Scan bug: deposited G575 is canonical 437, which is exactly the scan's second-ranked hairpin tip. Added nobble/curate/numbering.py. Gate now 2/2.
2026-11-03T18:53:39Z  Phase 1: receptor constructs from InterPro boundaries. Six constructs, token counts measured. DDB1 reduced to BPC alone on measured CR-8 contacts, avoiding a third exception. DCAF15 measures 1229 tokens against the spec's ~900 estimate.
2026-11-03T18:53:39Z  Phase 1: tests/test_phase1.py, 9 passed. All three testable Phase 1 gates pass.
2026-11-03T19:25:33Z  Phase 1: Tier A 17 ligases (10 of 12 spec-named present; FEM1B and DDB1 absent from BINMAN triage). Tier B gate passes: 15 ligases, frozen to data/tier_b_selection.parquet. Open Targets tumour_enriched is 0 for all 650 rows, so filter 4 is skipped and recorded (D-NOB-017); DCAF8L1, CCNF and ASB8 come out at ranks 1-3 exactly as spec 3.3 predicts.
2026-11-03T19:25:33Z  Phase 1: peptide library 25,567 unique candidates (7 benchmark, 12,029 curated degron, 160 Sievers matched, 558 C-degron, 12,813 scrambles). 332 carry a required PTM.
2026-11-03T19:25:33Z  Phase 1: ESM-2 t12 35M diversity reduction on MPS, 25,567 -> 220 in 12s, priority-ordered with every positive followed by its own scramble.
2026-11-03T19:25:33Z  Phase 1: 11 receptor MSAs precomputed via Boltz's own MMseqs2 client, depths 530 to 10,292, cached content-addressed under data/msa/. DDB1 BPC shared between two constructs.
2026-11-03T19:25:33Z  Phase 1: gap-aware frame resolver (D-NOB-020). Fixed four unmeasurable benchmark pockets. CRBN tri-tryptophan pocket recovered independently from 5HXB, 6H0F and 5FQD, all agreeing on W380/W386/W400.
2026-11-03T19:25:33Z  Phase 1: benchmark manifest 7 pairs, 105 jobs, 0 errors, 10 warnings (all smiles_fallback for dBET57). jobs_per_pair computed as 15 (D-NOB-019).
2026-11-03T19:25:33Z  Phase 2: campaign assembled, 100 YAMLs emitted (5 conditioned jobs dropped for member 3, which has no measurable pocket). Smoke test passed: 124-token job in 42.5s on MPS, 0.343 s/token. Full 100-job queue launched in tmux; resume verified (skipped the completed job).
- 2026-11-04T00:05Z Tier 2 wired and partitioned. It was unrunnable:
  `build_tier2_queue` wrote `queue_tier2.jsonl` and `run_campaign` only opened
  `queue.jsonl`. Wiring it exposed a silent bias: `delta_iptm` is a difference
  of two minima over seeds, a minimum is not robust to sample count, and tier 2
  draws 25 diffusion samples against tier 1's 1. Pooling them would have pushed
  the ternary minimum down on sample count alone, for exactly the pairs
  selected as most promising. Tier 2 now has its own queue, state and results
  files; `metrics.aggregate` filters on `tier_setting` as a hard partition;
  `tests/test_tiers.py` (4 tests) constructs the contamination case and fails
  without the filter. 40 tests pass. delta_iptm unchanged on all 6 scored
  pairs, confirming the filter is a no-op on existing data. D-NOB-032.
- 2026-11-04T00:05Z PROGRESS.md gates section corrected: it still claimed no
  NOBBLE vhost and an ALPHABETTI certificate. Verified live: certificate is
  issued to nobble.mdeller.com, verifies cleanly, runs to 2027-02-01, port 80
  returns 301. No gate is currently open. Throughput paragraph updated from the
  optimistic 0.343 s/token to the measured median of 0.4738 over 80 jobs.
- 2026-11-04T00:40Z Tier-2 wiring completed. score_campaign still opened
  results.jsonl unconditionally, so asking for tier 2 would have silently
  rescored tier 1 and written the answer over scores.jsonl. It now takes
  sampling_tier, resolves its paths through tier_files, filters the job list
  as well as the minima (by_pair feeds geometry and PLIP per job, a second
  route a stray record could take into a tier-1 number), and writes
  scores_tier2.jsonl. The composite is not refitted on tier 2: the decile is
  the top of the tier-1 ranking by construction, not a sample, so fitting on
  it would be fitting on the selection. tools/tier2.sh now runs select,
  refine and score. 42 tests pass.
- 2026-11-04T01:15Z Budget honesty. Measured throughput (median 0.4738 s/token,
  up from the optimistic 0.343) cut affordable pairs from 271 to 156, but the
  Sievers matched set is 160 peptides on its own, so the mandatory members now
  exceed the entire budget. `reduce_library` documented itself as "Select
  `budget` peptides" and never trimmed the mandatory set, so it overran and
  said nothing. Trimming is the wrong fix: the Sievers split is the control set
  the headline ROC is computed on. The overrun is now reported
  (`status`, `over_budget_by`, `notes`) and the priority ordering is what makes
  it safe. Added `projected_hours()` so Gate G1 is evaluated mechanically:
  167 pairs = 2,505 jobs = 51.1 h, over the 48 h per-run target by 3.1 but far
  under the 96 h G1 threshold, so **G1 does not open** and the build continues.
  tests/test_budget.py (6 tests). 48 tests pass.
- 2026-11-04T01:15Z Noted while there: `reduce_library` and `campaign_budget`
  have no callers anywhere in the tree, and no library manifest exists. Phase
  1's "25,567 reduced to 220" was computed in a run that persisted nothing, so
  the reduction is not reproducible from a committed entry point and violates
  the CLAUDE.md rule that every stage writes a manifest. Assembly takes over
  20 minutes, which is the argument for persisting it. Entry point next.
- 2026-11-04T01:35Z Added `nobble/curate/library.py`: the committed entry
  point that assembles, reduces and persists the peptide library to
  `data/manifests/library.jsonl` plus a summary carrying the reduction's own
  account of itself and the Gate G1 projection. Idempotent, with `--force` to
  rebuild. Measured the cost while writing it: assembly ran over 30 minutes
  wall clock for 42 seconds of CPU, so it is network-bound on UniProt and
  InterPro rather than compute-bound. That is the argument for persisting it,
  and for the half-written case being treated as unbuilt rather than reloaded.
  tests/test_library.py (4 tests). 52 tests pass.
- 2026-11-04T02:00Z Sievers arm drug-routed. The arm was about to be built
  with the IMiD left implicit. Counting first: of 32 degraded zinc fingers,
  pomalidomide is significant for 23 and lenalidomide for 8, so a single-drug
  arm would co-fold most positives with a drug the screen says does not
  degrade them while still labelling them degraded. Drug is now assigned per
  peptide and each control inherits its positive's. Eight positives dropped
  (significant only for CC-122/CC-220, no CCD in the ligand table), before
  matching so they cannot consume a kept positive's controls. Arm is 24
  positives + 96 controls = 120 peptides, down from 160. Rebuilt the library
  manifest on it: 158 selected (7 benchmark, 120 Sievers, 31 scrambles),
  2,370 jobs, 48.4 h projected against 63.1 h for the 160-peptide arm, so it
  now lands within half an hour of the 48 h target. Mandatory is 127, under
  the 156 budget, but the selection is still 2 over once scrambles are paid
  for, so the campaign stays calibration-only with no discovery headroom.
  D-NOB-033. 58 tests pass.
- 2026-11-04T02:30Z Main campaign manifest built: `build_campaign_manifest`
  reads the persisted library and routes each arm by its own rule (benchmark
  from its deposited chains, Sievers to CRBN with the IMiD assigned in
  D-NOB-033, scrambles inheriting their parent's construct and ligand).
  158 pairs, 2,370 jobs, 0 errors, 0 unroutable, written to
  data/manifests/campaign.jsonl. Matches the library projection exactly.
  Caught a bug in the first version: scramble inheritance rebuilt the parent's
  ligand with by_ccd, which returns nothing for a SMILES-encoded degrader, so
  bench03's dBET57 scramble dropped out as unroutable while its positive ran.
  A positive with no control is worse than running neither. The benchmark
  builder now exposes the resolved Ligand objects instead.
  tests/test_campaign_manifest.py (5 tests). 63 tests pass.
- 2026-11-04T03:00Z Structural zinc added. There was none in the codebase and
  the Sievers arm was about to submit 120 whole C2H2 zinc fingers as bare
  23-26mers; all 120 carry the complete coordination motif, checked. A C2H2
  finger without its Zn is a disordered peptide, not a domain, which
  contradicts the arm's own reason for taking fingers whole. ZN chain now
  added for complete sites, in BOTH arms: a cofactor in the ternary only
  would make Delta-ipTM report "the glue changed the interface" for "the
  peptide folded this time". Scrambles of fingers get it too, so the control
  differs from its positive in one variable rather than two. The 15-mer
  benchmark degrons are excluded (IKZF1's histidines fall outside its
  window). Not yet validated empirically: a two-job with/without test should
  run before the main campaign. D-NOB-034. tests/test_zinc.py (5 tests).
  68 tests pass. Campaign manifest rewritten: 158 pairs, 2,370 jobs, 0 errors.
- 2026-11-04T03:30Z Zinc probe run, and it falsified the strong form of
  D-NOB-034. Peptide-only folds: ZEP2 (degraded) pLDDT 95.66 with zinc vs
  95.37 without; ZN346 (control) 87.79 vs 85.99. A chain at 95.37 is not
  "a disordered 23-mer", so that claim was wrong as applied to what Boltz-2
  predicts: it reproduces the canonical C2H2 fold from sequence alone. The
  zinc stays as cheap insurance (chemically right, one token, does not hurt)
  but the claim that the arm "would have measured noise without it" is
  withdrawn. D-NOB-034 corrected in place with the table. One caveat kept:
  the gain was larger for the control (1.80) than the degraded finger (0.29),
  and a zinc effect correlated with the label would be the same confounder
  D-NOB-035 refuses MSAs to avoid, so it is being rerun at 6 fingers per class.
- 2026-11-04T03:30Z D-NOB-035: the Sievers fingers get no MSA. Not for cost
  (the 120 queries are network-bound and would not contend with the GPU) but
  because alignment depth would not be evenly distributed across the two
  classes the ROC separates: 24 degraded fingers from 24 genes against 96
  controls from 86, matched on length and composition and not on how well
  studied the parent is. Depth correlating with the label would put homology
  into the headline ROC. Giving none to any removes it by construction. The
  confounder is asserted, not measured, and the decision records that.
- 2026-11-04T03:50Z Main campaign assembled:
  campaigns/campaign_20261104T004632Z. 158 pairs (7 benchmark, 120 Sievers,
  31 scrambles), 2,360 jobs, 2,360 YAMLs, queue written, 0 unroutable.
  Pockets are measured once per (construct, ligand) rather than per pair:
  120 Sievers pairs share CRBN_CULT with one of two IMiDs, so two
  measurements serve them all, taken from the benchmark depositions 6H0F
  (Y70) and 5FQD (LVY). The two agree on 12 of 13 residues, measured
  independently from different structures, which is a free consistency check
  on the pocket the whole arm is conditioned on. 10 conditioned jobs dropped
  for want of a pocket: bench03 and its scramble, whose dBET57 is
  SMILES-encoded because 6BNB assembly 1 carries no PROTAC. Positive and
  control lose the conditioned arm together, so they stay symmetric.
- 2026-11-04T04:10Z Caught a silent contamination in the headline ROC before
  it could run. The main campaign puts benchmark, Sievers and scramble pairs
  in one scores.jsonl for the first time; cross-tabulating label against tier
  showed the benchmark panel carries peptide_label "degraded", the same as
  the Sievers positives. matched_control_roc selected on label alone, so its
  seven pairs would have joined the positive side of the curve: a different
  experiment, other E3s, PROTACs as well as glues, no matched negatives, and
  chosen for having good co-crystals, so the AUC would have risen. Now scoped
  to tier == sievers_zf and reports how many pairs it excluded. The weight
  fitter is deliberately left unscoped because spec 4.8 fits on the panel and
  the Sievers set both; the contrast is documented in weights._label so it is
  not tidied away later. D-NOB-036. tests/test_roc_scope.py (3 tests), with
  the contamination case verified to fail without the filter. 71 tests pass.
- 2026-11-04T04:25Z The same ROC contamination existed in the browser.
  delta.html's buildRoc() filtered on peptide_label === 'degraded' with no
  tier filter, so fixing the Python left the figure on the live site still
  counting benchmark pairs as Sievers positives. Two implementations of one
  curve had diverged the moment one was corrected. Now scoped to
  tier === 'sievers_zf' to match, and the panel reports how many pairs it
  excluded. No wrong curve was ever displayed: the three-negative floor kept
  it from drawing, but the count under it said "6 positive(s)" when the
  correct answer was none. QC: 12 captures, 0 non-200, 0 console errors,
  0 serious axe violations. Deployed.
- 2026-11-04T04:25Z Benchmark queue finished: 99/99, exit 0, zero failures
  across the whole run. The corrected campaign started automatically.
- 2026-11-04T04:45Z Zinc class-asymmetry caveat closed. Rerun at 6 fingers
  per class: degraded mean gain -0.07 (baseline 95.22), not-degraded +1.40
  (baseline 92.38). The apparent asymmetry is headroom, not label: gain
  correlates with the starting score at r = -0.704, and the class difference
  is t = 1.64 at n = 12 with within-class sd of 1.74 and 1.34. The ion cannot
  bias the ROC toward either class. Noted separately and not acted on: the
  degraded fingers fold better than their controls before any zinc (95.22 vs
  92.38), which cancels in a difference-of-arms statistic but would be a
  duller explanation than the glue if the ROC comes out strong.
- 2026-11-04T05:05Z Added tools/preflight.py and ran it on the assembled
  campaign: 2,360 jobs, 158 pairs, 0 errors, 0 pairs with an asymmetric
  cofactor. Every receptor chain has a cached MSA, so nothing will contact a
  server mid-run, and every peptide chain correctly has none. The asymmetric
  cofactor check is the reason this is a tool: the other failures announce
  themselves by stopping the queue, while a zinc in one arm only completes
  the run and quietly reports the cofactor instead of the glue.
- 2026-11-04T05:05Z Two bugs found by writing it. `latest()` matched on
  prefix alone, so a scratch directory named `campaign_smoke` sorted after
  `campaign_20261104T004632Z` and silently became "the latest campaign". It
  now requires a timestamp suffix. And preflight's own token-cap check
  ignored declared exceptions, flagging the 1,223-token DCAF15 jobs the
  manifest deliberately allows: a checker stricter than the rule it checks is
  just a false alarm.
- 2026-11-04T05:20Z Sievers arm smoke-tested end to end on two real jobs from
  the assembled queue, because static validation cannot prove Boltz accepts a
  four-chain job with a metal ion and a glue. Both completed: binary 38.2 s
  (chains A receptor, P peptide, Z zinc), ternary conditioned 112.9 s (plus L
  pomalidomide). Confidence JSON parses and the receptor-peptide pair ipTM
  reads out of pair_chains_iptm at (0, 1), which is where scoring looks.
  Not a result: the ternary here is conditioned against an unconstrained
  binary and it is one seed, so the difference between them is not Delta-ipTM.
- 2026-11-04T05:20Z The smoke test exposed a silent break worth pinning.
  Scoring locates the peptide by position, len(construct.segments), not by
  name. The cofactor is appended after the peptide so the index is unchanged,
  confirmed against the real output (A, P, Z, L). Had it gone in before, every
  ipTM lookup in the Sievers arm would have read receptor-to-zinc instead of
  receptor-to-peptide, in range and without raising. Now tested, and the test
  verified to fail when the cofactor is moved. 72 tests pass.
- 2026-11-04T06:00Z Design arm built and deployed as a seventh tab
  (DESIGN_ARM.md, D-NOB-037). nobble/design/ holds the variant generators
  (alanine scan, saturation, chemistry grouping) and design lift,
  delta_iptm(variant) minus delta_iptm(parent), which refuses rather than
  approximates when parent and variant were not run identically. The tab
  reports the validation state of the score beside the figures and states
  that the durable claim is the ordering of positions, not the absolute lift.
  31 scannable parents, a 15-variant scan costing 225 jobs and 4.9 hours.
  Default parent now chosen on measured Delta-ipTM (IKZF1/CRBN, +0.316)
  rather than an arbitrary length tiebreak that had landed on a PROTAC pair.
  QC 14 captures, 0 non-200, 0 console errors, 0 serious axe. 85 tests pass.
- 2026-11-04T06:00Z Two process gaps closed while shipping it: the QC page
  list and deploy.sh's route verification both had hardcoded six-tab lists,
  so a broken seventh tab would have passed QC and deployed as "verified".
  Both now include /design.
- 2026-11-04T06:25Z Design assembler built: nobble/design/assemble.py emits a
  runnable campaign from a planned scan. IKZF1/CRBN alanine scan assembles to
  16 pairs (parent plus 15 variants), 240 jobs, pocket derived from 6H0F.
  Preflight passes: 0 errors, 0 asymmetric cofactors. The parent is re-run
  alongside its variants rather than reused from an earlier campaign: 15 jobs
  out of 240 buys parent and variant measured under identical settings, which
  is what lift depends on.
- 2026-11-04T06:25Z D-NOB-038, found while building it. An alanine scan of a
  zinc finger mutates the coordinating residues, so inferring the cofactor
  per variant drops the zinc at C3A and C6A, measured on ZEP2. Those are the
  coordinating cysteines, the positions the scan exists to interrogate. Their
  lift would have been large and negative, read as "this position is
  critical", and been reporting the missing ion. A wrong answer that matches
  the prior is worse than an obviously broken one. Variants now inherit the
  parent's cofactor. 89 tests pass.
