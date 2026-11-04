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
- 2026-11-04T06:45Z Closed a gap that would only have surfaced after the
  compute: PairMetrics carried no parent_peptide_id, substitution or role, so
  a scored design campaign would have lost its linkage and lift.from_scores
  would have found zero variants and said so quietly, 240 jobs too late. The
  four fields now survive scoring, with a test that builds a design results
  file and checks they reach the serialised row.
- 2026-11-04T06:45Z tools/run_design.sh: waits for any GPU campaign to
  finish, preflights, runs, scores and computes the scan profile. Preflight
  runs before the queue rather than after, because the failure worth catching
  is the silent one.
- 2026-11-04T07:05Z Consistency sweep after the seventh tab. The LM query
  head was blind to the design arm: its schema declared tier as "benchmark,
  A or B" (stale, and conflating the pair's arm with the Tier A/B curation
  tier) and had no design fields, so validate() would correctly but
  unhelpfully reject any question mentioning a substitution. Schema now
  covers tier's real values plus peptide_sequence, parent_peptide_id,
  substitution and role. Six-tab references updated in PROGRESS.md,
  README.md and two module docstrings; README.html and README.preview.html
  regenerated with readme_forge rather than hand-edited. BUILD_SPEC.md left
  alone: it says six tabs and is correct about what it specifies, the design
  arm being an addition to it. README now documents the arm, including the
  two details that exist because the obvious implementation is wrong.
  90 tests pass, QC 14 captures clean, deployed.
- 2026-11-04T07:25Z tools/run_chain.sh started in tmux `nobble-chain`,
  waiting behind the corrected campaign. Runs the corrected comparison, then
  the main campaign (2,360 jobs, 51.8 h), then tier 2, then the design scan.
  The design scan is last deliberately: it is only 4.9 h and could be slotted
  in early, but its own tab says the composite is untrustworthy until the
  Sievers arm runs, so early lifts would need caveating into uselessness and
  rerunning. Preflight gates the main campaign. D-NOB-039.
- 2026-11-04T07:50Z Rendered the design tab's scan chart against a synthetic
  profile rather than waiting for the real one, and it was broken. The inline
  script sat in the `content` block, which Jinja renders before base.html
  loads Plotly, so it threw "Plotly is not defined". The routine QC never saw
  it: with no profile the script returns early and never touches Plotly, so
  the failure would have appeared only after the 4.9-hour scan produced data.
  Moved into the `scripts` block, where every other charted page puts it.
  Then two sizing passes: an explicit Plotly height of 320 exceeded the
  18rem .chart--short container and clipped the axis title, so the height is
  removed and the chart fills its container like the others.
  qc/scan_check.mjs keeps the check: it measures bars actually plotted from
  the live plugin state rather than reading the HTML.
- 2026-11-04T07:50Z Writing the synthetic fixture turned up a second defect.
  A naive generator emitted "A9A", a substitution of a residue for itself,
  and scan_profile ranked it most sensitive. Its two runs differ only by
  seed, so its lift is the noise floor, and nothing downstream distinguishes
  that from an effect. The real alanine scan never emits one (it scans an
  alanine to glycine) but lift.compute now refuses it rather than relying on
  every future generator remembering. 92 tests pass.
- 2026-11-04T08:15Z Header status was overclaiming. It read COMPLETE,
  "campaign finished", while the corrected campaign was running and the main
  and design campaigns were assembled and waiting: accurate about the
  published slice, misleading about the project, and a visitor would
  reasonably conclude the science was done. The droplet cannot see the
  Studio's queues, so build_atlas now records what was outstanding at build
  time and the panel says "published campaign finished; 3 more queued when
  this slice was built". Scoped as a build-time fact rather than a live
  feed, because that is what it is.
- 2026-11-04T08:15Z Fixed a legibility bug in the same panel: pairs rendered
  as "7/6 br" between "jobs 100/100" and "valid 1/3", so it read as a
  fraction, "7 of 6", which is impossible. They are two counts, scored and
  bridged, now separated by a middot. tests/test_status.py (3 tests).
  95 tests pass.
- 2026-11-04T08:30Z The status note was computed and never rendered. Fixing
  the wording in data.py had changed nothing visible: `site_status.note`
  appeared nowhere in base.html, so "complete" stood alone on the page while
  three campaigns were queued. The state word now carries it as a tooltip
  and the outstanding count shows inline as "+3 queued", because a caveat
  reachable only on hover is not a caveat. Live and verified.
- 2026-11-04T08:50Z About tab documents the design arm. That page is where a
  sceptical reader goes for caveats, and the arm carries the project's
  sharpest one: it proposes rather than measures, and it ships before the
  score it ranks by is validated. Four questions answered plainly, including
  what it does not claim.
- 2026-11-04T08:50Z Checked two things that turned out to be sound rather
  than broken, and they are recorded so they are not re-checked. The
  corrected comparison runs cleanly against a partially complete campaign
  and reports "incomplete" rather than erroring, so the chain's `|| true` on
  that step will not be hiding a crash. And `control_held: false` is a
  two-state boolean over a three-state fact, but every consumer
  disambiguates: benchmark.html renders held / not yet run / MOVED, and the
  conclusion text has a separate branch for the control having no number.
- 2026-11-04T09:10Z FINDINGS F10 and F11 written. F10 records that the zinc
  finger arm does not need its zinc: 12 peptide-only folds show Boltz
  reproduces the C2H2 fold from sequence alone, the ion is cheap insurance
  rather than a fix, and the apparent class asymmetry is headroom
  (r = -0.704 against baseline) not label. F11 records the three ways the
  design arm would have produced a confident wrong answer, all found by
  constructing the failure rather than waiting for it.
- 2026-11-04T09:10Z Design tab: all 31 parents selectable. Previews for
  every scannable parent are precomputed into the atlas (377K, 669 variants)
  because the droplet has no curation stack and cannot generate a scan on
  request. A bogus parent falls back to the default rather than erroring,
  and switching parent clears the scan profile unless the profile belongs to
  that parent: showing one degron's result beside another's variants would
  caption a measurement with the wrong sequence.
- 2026-11-04T09:10Z Verified the LM executes design queries end to end, not
  just that its schema validates them: filter on tier, sort on delta_iptm,
  select substitution, correct rows back.
- 2026-11-04T09:25Z Centralised the GPU wait into tools/wait_for_gpu.sh. It
  had been a copied loop in two scripts, absent from a third, and the lists
  had already drifted: run_design.sh waited on a session named
  nobble-campaign that nothing creates, while the chain runs in nobble-chain,
  so a standalone design run would not have waited for it. tier2.sh had no
  wait at all. One list now, and it skips the session the caller is itself
  running inside so a script cannot wait for itself.
- 2026-11-04T09:25Z Restarted tmux nobble-chain after editing run_chain.sh
  while it was executing. Bash reads a script by byte offset, so replacing
  lines underneath a running instance can resume it mid-sentence. It was
  still in its wait loop, so nothing was lost; noting it because the hazard
  is easy to create and silent when it bites.
- 2026-11-04T09:40Z Exercised the chain's never-run stages against
  synthetic data rather than waiting 60 hours to find out. Design scoring
  and the chain's lift block both handle the no-results case cleanly, and
  with a synthetic design scores file in the real campaign's shape the full
  path works: 15 variants computed, 0 refused, all 15 positions profiled.
- 2026-11-04T09:40Z That test exposed a gap. lift.compute checked each side
  had at least three seeds but never checked the two sides had the *same*
  count. delta_iptm is a difference of minima over seeds, so a variant
  scored over four seeds against a parent scored over five has a lower
  minimum before any substitution is considered. They normally match,
  coming from one campaign with one seed tuple: they stop matching when a
  job fails, which is exactly when nobody is checking seed counts. Now
  refused. 96 tests pass.
- 2026-11-04T10:10Z Cut the UI prose on Marc's instruction: too much narrative
  text and too many disclaimers. Rendered visible prose down from about 2,100
  words to 1,220, with six of seven tabs now at or under 150 words
  (campaign 145, pose 100, interactions 56, delta 96, design 69,
  benchmark 203, about 551). Removed explanations of why decisions were made,
  caveats restating what the About page already says, and the 29-word footer
  disclaimer repeated on every page (now 8). Kept pipeline-generated status
  text, including validation layers' refusal reasons: those are output
  explaining why a number is absent, not decoration.
- 2026-11-04T10:10Z Added the rule to CLAUDE.md and to the marcs-vibe-coding
  skill so it holds on future builds: one short line per panel, under 40
  words per panel and 150 per page, disclaimers only where a figure would be
  actively misread without one.
- 2026-11-04T10:10Z Before that, rendered the app against a synthetic
  158-pair atlas rather than waiting for the main campaign. All routes 200
  and fast, but the per-pair minimum-against-median plot drew 158 category
  rows into a 26rem box at two pixels each, unreadable. It now shows the 12
  largest minimum-median gaps and states how many it left out. Also explained
  why the scatter legend counts 31 degraded while the ROC below uses 24: the
  ROC is the Sievers arm alone, and the two numbers differ on purpose.
- 2026-11-04T10:50Z Capacity checked against the droplet rather than assumed:
  154 G disk with 87 G free, 7.9 G RAM with 4 G available, NOBBLE using 62 M.
  At full campaign size results.jsonl projects to 5 MB (about 16 MB as Python
  objects) and scores to 3.2 MB, so there is no memory risk; structures reach
  roughly 540 MB on disk, pushed once because rsync is incremental.
- 2026-11-04T10:50Z D-NOB-040: the chain now re-assembles the design scan
  after the main campaign scores. It had been reusing a campaign whose parent
  was chosen from the seven benchmark pairs, which undid the reason for
  queuing the scan last. Restarted tmux nobble-chain to pick up the change.
- 2026-11-04T10:50Z Scored the corrected campaign at 64/100 for an early read
  on F6. No verdict yet, and the machinery said so correctly: "not concluded,
  the IKZF1 control has no number in both campaigns". The three-state control
  logic behaving as intended rather than collapsing to a false negative.
- 2026-11-04T11:05Z Dry-ran the chain's new re-assembly block before trusting
  it to run unattended, and it picked BRD4/VHL: a PROTAC pair, in an arm
  about glue dependence. The fallback fires whenever nothing is scored, which
  includes the case where the main campaign fails to score, so it has to be
  right on its own rather than relying on scores existing. Parents now carry
  a modality and the fallback prefers a glue, picking GSPT1/CRBN instead, and
  says plainly that a parent chosen this way has not been ranked against
  anything. 101 tests pass.
- 2026-11-04T11:20Z Preflight now checks that a cached MSA actually exists on
  disk, not merely that the YAML names one. The two are not the same, and a
  missing a3m fails at whichever job reaches it, hours into a run. Verified
  by pointing a job at a non-existent path and confirming preflight refuses.
  Both assembled campaigns pass: all 9 referenced MSAs present.
- 2026-11-04T11:35Z Gate G5 enforced rather than configured. The 50 GB floor
  had been in thresholds.toml and tuning.toml since Phase 1 and nothing read
  it. runner.disk_gate() now checks before every job and stops the queue with
  a count of what is left to rerun. Checked per job, not once at the start,
  because a 52-hour run fills a volume gradually and a gate should stop
  before the damage. My first version read the wrong config section and
  reported a floor of 0.0, a gate that can never open, which is why the test
  asserts the floor is read and is positive. Headroom: 543 GB free, about
  7 GB needed. 104 tests pass.
- 2026-11-04T11:50Z Swept the config for other thresholds that were set but
  never read, the pattern G5 had. Of 44 keys, two: rmsd_breakpoints and
  tumour_enrichment_above_median. The first was a real violation of the
  project rule that no cutoff is hard-coded in Python: success_rate_curve
  carried the breakpoints in a default argument while the configured value
  went unread, so editing thresholds.toml changed nothing. Now read from
  config, with a test that changing the config changes the curve. The second
  is genuinely dead (D-NOB-009: the column is 0 for all 650 rows) and is now
  annotated as not applied rather than looking live. 106 tests pass.
- 2026-11-04T12:05Z thresholds.toml opens with "Nothing in Python hard-codes
  a threshold". It was not true: nine module-level cutoffs lived in code
  (contact distances, the pocket radius, the collapse margin, the control
  tolerance, the exposed-SASA and mismatch fractions, the domain coverage
  floor). All nine moved into config with their values unchanged, verified
  one by one. A test now greps for new numeric module constants and fails on
  any that is a cutoff rather than a physical constant, so the file's opening
  claim is enforced rather than aspirational. 108 tests pass, preflight on
  the assembled campaign still clean.
- 2026-11-04T12:25Z **F6 supported.** Ran the corrected comparison early on a
  partially complete campaign rather than waiting for the chain, and found
  both the result and a defect that would have hidden it. GSPT1/CRBN 29.22 A
  -> 1.17 A, BRD4/VHL 19.23 -> 1.71, CSNK1A1 12.24 -> 6.19, BRD4/CRBN 20.40 ->
  16.52, none worse. The IKZF1 control moved by exactly 0.00 A: identical
  input, identical output, which is the control holding and a determinism
  check at once. Two pairs still to run.
- 2026-11-04T12:25Z The defect: RECOVERY_TARGETS is keyed on pair ids like
  bench01_GSPT1_CRBN, and the corrected campaign names the same biology
  corr01_GSPT1_CRBN. Pose recovery looked up the crystal by literal pair id,
  found none, and said "no predicted pose could be aligned". The comparison
  then said "not concluded" and would have said that after all 100 jobs.
  Every refusal was honest and none pointed at the pair id. Targets now
  resolve on (gene, E3) as well as the literal id. F12. 109 tests pass.
- 2026-11-04T12:45Z The F6 conclusion was published without saying it was
  provisional. "F6 supported: 4 pairs improved" over a campaign at 69 of 100
  is a verdict about whichever pairs happened to finish, and the per-pair
  table marked the gaps while the headline sentence did not. The conclusion
  now appends how many pairs are unfinished and names them, and the report
  carries pairs_compared, pairs_incomplete and provisional. Applied to every
  branch that draws a verdict, not just the supported one: "not supported"
  over a partial campaign overclaims in the same way. Live and verified.
- 2026-11-04T13:05Z Found a defect that would have wasted the entire main
  campaign. build_atlas hard-coded latest("benchmark"), and refresh.sh
  accepted a campaign, scored it, then called build_atlas with no argument.
  The chain called refresh.sh with no argument at all. So after 52 hours the
  main campaign would have been neither scored nor published: refresh would
  have re-scored the benchmark panel and the atlas would have republished it,
  with nothing failing and no message saying the 158-pair result had been
  skipped. build_atlas now takes the campaign, refresh.sh passes its own
  through, the chain passes the campaign it just ran, and the default
  prefers a main campaign with results over the benchmark panel. Verified in
  both directions: publishing the main campaign explicitly switches the
  atlas, and with no main-campaign results the default still picks the
  benchmark panel. 111 tests pass.
- 2026-11-04T13:25Z Second chain defect in the same family. tools/tier2.sh
  passed the campaign to nobble.execute.runner positionally, and the runner
  only accepts --campaign, so tier 2 would have died on argparse the moment
  the chain reached it: after the main campaign's 52 hours. Confirmed by
  running the exact command. Fixed, and every runner invocation in the repo
  audited: all now use --campaign.
- 2026-11-04T13:25Z Added tests/test_scripts.py. Two defects in one tick came
  from a shell script calling Python with arguments it does not accept, or
  dropping an argument it was handed. Neither fails until the stage runs, by
  which point the compute is spent or skipped. The tests parse the scripts
  rather than executing them, because these are GPU entry points and running
  them to find out is exactly what is being avoided. 115 tests pass.
- 2026-11-04T13:45Z tools/tier2.sh ran under `set -e`, alone among the
  runners. The runner exits 1 when any job failed, so one failure out of ten
  would have aborted the script before its scoring step, discarding the nine
  that ran to report a failure the log already showed. Dropped to
  `set -uo pipefail` like every other runner, with a test that pins it.
- 2026-11-04T14:00Z Considered republishing the site periodically during the
  52-hour main campaign and decided against it (D-NOB-041). deploy.sh rsyncs
  the structure directory and build_atlas copies every structure the results
  file references, so a mid-run publish can copy an mmCIF as Boltz is writing
  it. A truncated structure does not announce itself: the viewer draws a
  partial chain, which is a wrong picture rather than a missing one. Scoring
  a growing results.jsonl is safe because torn lines are handled; copying a
  structure mid-write is not. The status panel already says what it
  published and what was queued.
- 2026-11-04T14:30Z Verified the GPU wait does not block on its own tmux
  session. run_chain.sh runs inside nobble-chain and nobble-chain is in the
  list it waits on, but the chain blocks on nobble-corrected first, so the
  self-wait is unreached in the live run: it would have fired the moment the
  corrected campaign finished, and the chain would have waited for itself
  forever with nothing new in the log. The skip works, tested by running the
  function inside a session whose own name was the only entry in the list.
  Pinned as a test. 119 tests pass.
- 2026-11-04T14:30Z Saturation assembly tested end to end: 20 pairs, 300
  jobs, 0 errors, wild type excluded, every variant one residue from the
  parent. It had only been unit-tested at the generator, and it is the
  follow-up the alanine scan is meant to lead to.
- 2026-11-04T14:55Z Rendered a zinc-bearing Sievers pose before the main
  campaign produces 120 of them. Mol* builds a separate Ion component, so the
  zinc did draw, but as a default ball-and-stick dot inside a translucent
  gaussian surface: effectively invisible, which is the wrong reading for the
  ion the finger's fold depends on. Given spacefill, scoped to pose.html
  rather than molstar-bridge.js because BINMAN's structures carry no ions and
  there is no shared behaviour to widen (D-NOB-031). The glue keeps its
  sticks, its emissive shell and its pinned carbons, and the pLDDT theme
  still applies to polymer only.
- 2026-11-04T14:55Z The first attempt used
  updateRepresentations(components, {type}) and silently did nothing. That
  method takes (components, pivot, params), so the type arrived as the pivot.
  molstar-bridge.js carries a comment about having made exactly this mistake
  before; reading it is how the second attempt used the state builder
  instead. Verified by reading the component's representation back out of the
  live plugin, not from the screenshot. 119 tests, QC 14 captures clean.
- 2026-11-04T15:20Z Exercised the zinc-finger design scan, which the chain
  will likely produce: 24 of the 31 scannable parents are Sievers fingers, so
  a zinc-bearing scan is the normal case rather than an exotic one. ARID2,
  26 residues: parent carries the ion, all 26 variants inherit it, none lost
  it including the coordinating-cysteine mutants that would have dropped it
  under per-variant inference. Assembled fully (27 pairs, 405 jobs, 270 in
  the A P Z L layout) and preflighted clean with 0 asymmetric cofactors, then
  removed so the chain's target stays the IKZF1 campaign. Pinned as a test
  against a real library parent rather than a synthetic one. 123 tests pass.
- 2026-11-04T15:40Z Exercised the composite weight fitter at full campaign
  scale for the first time. It has never actually fitted: every campaign so
  far had too few labelled pairs and it refused, so the fitting path runs for
  real only after the main campaign. On 158 synthetic pairs shaped like the
  real queue it fits cleanly (AUC 0.8918) and correctly gives zero weight to
  the two components fed pure noise.
- 2026-11-04T15:40Z That exposed an overclaim. The reported AUC is in-sample
  by construction: the grid search maximises it on the same labelled pairs
  the composite then ranks. It was published as "AUC 0.89" on every scored
  row and in the About panel, which reads as performance on unseen pairs,
  which is what the matched-control ROC is for. The fit now carries an
  explicit in-sample caveat and the row status says "in-sample AUC".
  124 tests pass.
- 2026-11-04T16:00Z Exercised the matched-control ROC at real arm size for
  the first time. It is the project's falsifiable test and has never
  computed: every campaign so far had no matched negatives. At 24 degraded
  against 96 controls it computes cleanly, excludes the 38 pairs outside the
  arm, and the bootstrap interval brackets the point estimate.
  All three branches pinned, including the one that matters most: a weak
  edge gives AUC 0.594 with a 95 per cent interval running below 0.5, and
  the layer declines to call it a signal rather than rounding the point
  estimate into a finding. Added the converse too, so the layer is not
  merely cautious: a real separation is reported as above chance.
  My first assertion pinned AUC > 0.6 from an earlier ad-hoc run whose draw
  order differed; corrected to assert the property rather than tune the
  fixture until it agreed. 128 tests pass.
- 2026-11-04T16:25Z Rendered the app against a fitted composite at full
  scale, which has never happened: the fitter has always refused. The
  composite column, the partial badges and the sliders all render, and both
  fit caveats fire (in-sample AUC, and lysine geometry carrying 0.36 weight
  despite being unvalidated).
- 2026-11-04T16:25Z That exposed a real inconsistency. The weight sliders
  rendered hardcoded defaults under a caption reading "Fitted on the
  benchmark panel and the Sievers matched set, never by hand", beside a
  composite column computed from the actual fit. The two disagreed, so
  touching a slider jumped the ranking for no visible reason. The sliders
  now seed from the fit, Reset returns to the fit rather than to the values
  it replaced, and the caption says plainly when nothing is fitted.
- 2026-11-04T16:25Z Two mistakes of my own on the way. I added weight_fit to
  the /delta route instead of /campaign, because I matched the first
  occurrence of a line that appears in both; caught by reading the rendered
  page, which still said "Not fitted yet". And the fitter names the lysine
  component lysine_reach_exposed_fraction while the UI slider is
  lysine_reach, so the fitted weight landed on no slider and the default
  stood silently. Aliased. 128 tests, QC clean, deployed.
- 2026-11-04T17:10Z Tier 2's output was invisible. It writes scores_tier2
  and results_tier2, and nothing read either: not the atlas, not the app. A
  refinement run would have spent hours producing a better set of
  coordinates that no page could open. The atlas now publishes the tier-2
  slice, the app exposes it, and the pose catalogue offers refined
  structures marked as such rather than merged with tier 1, which were
  sampled differently (D-NOB-032).
- 2026-11-04T17:10Z Found a real cache bug on the way. data._cached
  documented itself as keyed by (path, mtime) and was keyed by (name,
  mtime), so two campaigns whose files shared an mtime returned each
  other's rows. In production _CAMPAIGN is set once and it never fires; it
  fires the moment anything reconfigures. The path is now in the key, as
  the docstring always claimed.
- 2026-11-04T17:10Z The two new tests passed alone, passed against every
  other test file pairwise, and failed only in the full run. The product
  code was correct throughout: printing the HTTP payload showed the right
  structures every time. A test that depends on accumulated global state
  measures the suite rather than the code, so they now run in a subprocess.
  Stable across three consecutive full runs. 130 tests pass.
- 2026-11-04T17:25Z The refined-pose URLs I added in the previous commit all
  404ed. The catalogue offered them; /structure/<job_id>.cif searched
  results.jsonl only, so no tier-2 job could be found and the viewer would
  have listed every refined structure and failed to open any of them. Worse
  than not listing them. Fixed to search both tiers, with a test that
  fetches every URL the catalogue advertises rather than asserting on the
  implementation. 131 tests pass.
- 2026-11-04T17:40Z Finished making tier 2 reachable from the viewer. The
  default pose now selects tier 1 explicitly rather than landing on it by
  accident of list order: the numbers on the page are tier 1, and showing a
  refined pose beside them would be a different structure from the one the
  scores describe. Refined poses are offered as per-seed links instead,
  shown only when they exist, so tier 2 is reachable without knowing the
  URL scheme. Verified both ways: with tier-2 data the note lists three
  seeds as working links; without it the note stays hidden. 131 tests pass,
  QC clean, deployed.
- 2026-11-04T17:55Z Verified the design arm end to end through the real
  path, not a synthetic injection: scored a real design campaign, let
  report.build() find it, let build_atlas publish it, and measured the
  rendered chart. 15 lifts computed, 0 refused, 15 bars plotted, no console
  errors. Then removed the synthetic scores and rebuilt the atlas before
  deploying: that test had put fabricated lifts into design.json, and
  deploying them would have published invented numbers as results.
- 2026-11-04T17:55Z The rebuild also removed 11 duplicate structure files
  with macOS " 2.cif" suffixes. I introduced them in efc1699 with a
  cp -r backup and restore of deploy/atlas while testing which campaign
  build_atlas publishes. 100 structures remain, matching the 100 jobs.
- 2026-11-04T18:10Z The PLIP fingerprint's notes were computed and never
  shown. On a Sievers pair the most important one says the structural
  zinc's four metal-coordination rows were excluded (F14), and without it a
  reader comparing the page to raw PLIP output cannot tell why the counts
  differ. Now rendered on the Interactions tab, where it already shows the
  chain map it used. Same class as the status note that was computed and
  discarded earlier: a sentence the pipeline writes and nothing displays.
- 2026-11-04T18:30Z Swept for the "computed and never rendered" pattern
  after hitting it three times. 64 of 129 record fields are never
  referenced by any template or script; most are legitimately internal.
  One mattered: bridge reject_reason. bench07_CDK12_DDB1 has no bridge
  percentile at all (0 of 10 seeds bridged) and the table showed a blank
  cell with no reason, because the per-seed reason was aggregated away.
- 2026-11-04T18:30Z Recovering it gave a finding. Every failed bridge in
  the panel fails identically: single_chain:1_qualifying_of_1, the glue
  burying surface against one chain rather than two. Not one seed anywhere
  failed for a weak or unbalanced bridge. That says the failure mode is
  placement rather than quality, consistent with CDK12 also having the
  worst pose recovery at 44.92 A. F16. The reason now reaches the pair
  record and the tooltip on an empty percentile cell. 131 tests pass.
- 2026-11-04T19:00Z Bridge formation added to the automated comparison and
  to the benchmark tab's table. The comparison reported pose RMSD only, so
  the chain would have produced F12 and missed F17: recovery compares a
  prediction to a crystal, bridging asks only whether the glue touched both
  chains inside the prediction, and they are independent. Now reported per
  pair, with the column rendering live.
- 2026-11-04T19:00Z Note for future debugging: locally the app points at the
  campaign directory, where comparison.json does not exist, so the whole
  comparison panel is absent. On the droplet NOBBLE_CAMPAIGN points at the
  atlas and it renders. Checking a published panel locally needs
  NOBBLE_CAMPAIGN=$(pwd)/deploy/atlas, not the default.
- 2026-11-04T19:15Z The comparison's conclusion now reports bridge
  agreement alongside the RMSD verdict, without folding it into the
  verdict. F6 is about pose recovery and the 2 A thresholds are calibrated
  on it, so widening the criterion would change what "F6 supported" means
  without saying so. But a reader should see that an independent
  measurement moved the same way, because two agreeing is a much stronger
  claim than either alone. Live conclusion now reads: 5 pairs improved,
  control held, none worse; bridge formation agrees with 3 pairs bridging
  in more seeds and none in fewer; provisional with CDK12 outstanding.
  132 tests pass.
- 2026-11-04T19:40Z The planned-scan table's Lift column read "not run"
  unconditionally, so once a scan completed the same page would have shown
  lifts in the chart and "not run" in the table above it. Now keyed on
  substitution against the profile, with a Bridged column beside it. The
  existing guard holds: when the chosen parent is not the one that was
  scored, the cells correctly stay empty rather than borrowing another
  degron's numbers, which is what the first render showed before I made
  the fixture consistent.
- 2026-11-04T19:40Z The table makes F19 legible in one row: C4A shows lift
  +0.0988 with bridged "lost". A reader scanning the lift column alone
  would read that as an improvement. 134 tests, QC clean, deployed.
- 2026-11-04T20:00Z Measured the post-inference scoring cost rather than
  assuming it: PLIP 1.1 s per ternary, bridge geometry 0.04 s, contacts and
  docking 0.01 s. Scoring the whole 2,360-job main campaign is about half
  an hour, dominated by PLIP. No concern, and now known rather than hoped.
- 2026-11-04T20:00Z Added tools/status.sh: campaigns with progress and
  scored counts, gate states, what the published atlas holds, live site
  reachability, and failure counts across the logs. A 60-hour chain leaves
  its state spread over tmux, queue files, state files and logs, and
  reading those by hand is what gets done wrongly when tired.
- 2026-11-04T20:00Z Two of my own bugs while writing it. The failure
  counter used `grep -c ... || echo 0`, and grep exits 1 on no matches, so
  every clean log printed "0\n0" and read as failed; verified the fix by
  planting a log with a Traceback and watching it appear and then vanish.
  And tests/test_scripts.py's positional-argument check matched
  "from nobble.execute.runner import disk_gate", a Python import rather
  than a CLI call; narrowed to -m invocations and confirmed it still
  catches the tier2.sh defect it was written for. 134 tests pass.
- 2026-11-04T20:25Z Re-read run_chain.sh end to end after several rounds of
  edits and found two gaps that would not have failed anything. The atlas
  was rebuilt straight after the main campaign, before tier 2 and the
  design scan existed, so both would have run for hours producing files the
  published bundle did not contain. And the chain never deployed, so after
  sixty hours the live site would still have shown the benchmark panel.
  Both fixed: one rebuild after the last stage, then a deploy, then a
  status print. D-NOB-042. Restarted tmux nobble-chain to pick up the
  change, since editing a running script is read by byte offset.
- 2026-11-04T20:45Z Swept for modules no test references. The first sweep
  said 28 of 38, which was wrong: it matched "nobble.design" from
  "from nobble.design import lift" and never saw the submodule. Corrected
  with an AST walk: 4 modules, about 480 lines, chiefly execute.msa.
- 2026-11-04T20:45Z Tested the MSA cache key, which every job rides on.
  build_yaml writes the a3m path into each receptor chain, so two
  sequences sharing a key would align one protein against another's
  homologues with nothing to say so, and one sequence producing two keys
  would make the campaign call the server mid-run, which spec 1.3 exists
  to prevent. Checked against the real constructs as well as invented
  strings: 11 segments, 11 keys, no collisions. Also pinned that a
  zero-byte a3m is a failed fetch rather than a cache hit. 140 tests pass.
- 2026-11-04T21:00Z Tested curate.interpro, which had none. Construct
  boundaries come from named InterPro entries and every job is built on
  them: a wrong boundary gives the wrong receptor length, token count and
  pocket residues, and nothing fails.
- 2026-11-04T21:00Z Found an undefended assumption while there. Domain
  extents were taken as fragments[0]["start"] and fragments[-1]["end"],
  which assumes InterPro returns fragments in positional order. It does:
  345 multi-fragment locations across 1,197 cached accessions, none out of
  order. That is an undocumented property of someone else's API, and
  relying on it would move a construct boundary silently if it changed.
  Now min and max by position. Verified no construct moved, and preflight
  on the assembled campaign is still clean. 144 tests pass.
- 2026-11-04T21:20Z Closed the last three untested modules. curate.plddt's
  best-window search decides Tier B membership and is a rolling sum with
  1-based inclusive reporting, the shape that goes wrong by one and still
  returns a plausible number. Tested at both edges and on a domain buried
  in disorder: correct, no bug. curate.freeze guards a frozen scientific
  commitment, so a test now pins that a plain call cannot reselect, that
  the real file's mtime does not move, and that it still holds the 15 rows
  PROGRESS claims. Every module in nobble/ now has a test referencing it.
  148 tests pass.
- 2026-11-04T21:40Z No linter is installed in either environment, so ran a
  stdlib AST pass instead: compile every file, then flag unused imports,
  bare excepts and mutable default arguments across nobble/, tools/ and
  deploy/. No bare excepts and no mutable defaults in 50 files. 52 unused
  imports reported, 41 of them `__future__ annotations`, which is used
  implicitly and is a false positive.
- 2026-11-04T21:40Z The other 11 were real dead imports, each appearing
  only on its own line: Path in four modules, gemmi in lysine, math and
  paths and peptide_module in layers, field in two dataclass modules.
  Removed and verified three ways rather than on the test suite alone:
  151 tests, every one of the 38 modules imported, and the touched
  modules exercised against real data (interpro resolves CULT, layers
  recovers 17.14 A, compare concludes, assemble builds 16 pairs).
  Preflight on the 2,360-job campaign still clean, QC still clean.
- 2026-11-04T22:00Z Checked for a shell linter (none installed) and
  syntax-checked every inline script and static JS file through node:
  8 blocks, 0 errors.
- 2026-11-04T22:00Z Added tests/test_docs_match_reality.py. Documentation
  drift has been a real defect in this build rather than a hypothetical
  one: PROGRESS has claimed six tabs when there were seven, an open Gate
  G3 that had been satisfied hours earlier, and a running benchmark queue
  that had finished. Each was true when written. Four claims are now
  pinned: the main campaign's 2,360 jobs and 158 pairs, the tab count, the
  285,996-bridge reference, and the README's design-scan costs, all
  derived from the code and data rather than hand-kept.
- 2026-11-04T22:00Z Verified the tests fail on drift rather than assuming
  they would: introduced the exact errors they exist to catch (2,400 jobs,
  160 pairs, six tabs, 285,000 bridges, 230 jobs) and all four failed,
  then restored. A documentation test that cannot fail is decoration.
  156 tests pass.
- 2026-11-04T06:12:16Z  correction: no stall occurred. `stat` local time was compared against `date -u`, turning a healthy 13-minute job into an imagined 5h13m hang; I killed it at 80% done, costing one attempt. The unbounded post-kill wait in subprocess.run found while investigating is real and is fixed anyway; added nobble/execute/watchdog.py so elapsed time is computed, not eyeballed (F20, D-NOB-043). 165 tests.
- 2026-11-04T06:22:16Z  test: droplet route coverage derived from app.url_map rather than a hand-kept tuple, which had silently stopped covering /design and four API routes; route count in PROGRESS pinned against deploy.sh (F21). 171 tests.
- 2026-11-04T06:25:36Z  test: pinned the conditioned/unconstrained invariant at both the generator and on disk. Swept all 2,800 queued YAML across four campaigns: zero mismatches, so the control is sound; it was simply untested (conditioning appeared in tests only as fixture data). 177 tests.
- 2026-11-04T06:27:23Z  fix: watchdog yardstick changed from the slowest completed job to the median, matching runner.throughput(). Job 81's recorded 2037s (inflated by the attempt I killed) had become the scale and nearly doubled the overdue threshold. 178 tests.
- 2026-11-04T06:33:34Z  test: licensing guard derived from the PROTAC-DB table (all 15,502 structures) rather than one hand-written fragment, plus a test that the redaction demonstrably ran instead of the field merely being absent; dead clause removed from build_atlas.redact. Verified end to end against the live site: name published, structure withheld (F22). 180 tests.
- 2026-11-04T06:36:37Z  fix: check_prediction reported 'RBM39 WRONG' on 6 of 10 poses with no qualification; now reports pose counts, marks the verdict provisional against the complete baseline, and computes the distance to a different answer from the F13 thresholds (3.354 A, so F18 stands). 186 tests.
- 2026-11-04T06:42:28Z  fix: matched_control_roc now reports per-pair seed counts and names an imbalance. Delta-ipTM is a difference of minima and the curve never checked comparability; it is clean today (all 120 sievers_zf pairs at 10 ternary + 5 binary) but only because a scoping rule added for another reason excludes the two short pairs (F24). 193 tests.
- 2026-11-04T06:45:59Z  ui: /benchmark now carries one generated line saying all 7 recovery targets predate Boltz-2's 2021-09-30 cutoff, so the figures are retrospective. The time_split layer had computed this correctly and it never reached the page (F25). 197 tests.
- 2026-11-04T06:51:32Z  fix: three hardcoded cutoffs moved to thresholds.toml, including the 2.0 A behind 'F6 supported' (which the conclusion wording also quoted separately, so a change would have left the sentence claiming the old value). AST guard added; two float comparisons allowlisted with reasons (F26). 201 tests.
- 2026-11-04T06:56:36Z  fix: design lift now reports bridge rate change and flags a weakened bridge, not only outright loss (a 10/10 parent against a 1/10 variant read as a clean improvement). Guard extended to module-level constants, which caught MINIMUM_SEEDS and four more cutoffs now in thresholds.toml (F27). 210 tests.
- 2026-11-04T07:00:20Z  fix: five inline integer cutoffs moved to thresholds.toml, including the 25 behind 'indicative' weights and the floor below which the headline ROC is refused. Guard extended to inline ints with 15 structural comparisons allowlisted by reason; 0 and 1 deliberately out of scope (F28). 213 tests.
- 2026-11-04T07:04:03Z  fix: lm.validate never checked a filter's value, so a model returning ['delta_iptm','gt','high'] made /api/ask return 500. Types now declared and published, values checked with the reason given, and execute wrapped as a floor under that. The no-arithmetic contract itself verified by AST (F29). 225 tests.
- 2026-11-04T07:10:30Z  fix: fourth cutoff sweep, over default arguments. Five were real, including the F20 job timeout and the tier-2 decile fraction; contacts_to_ligand's default 5.0 was answering three different measurements across four copies of the number, so the default is removed and each caller must state which. Tier-2 selection now reports the arm composition of the decile (F30). 234 tests.
- 2026-11-04T07:16:10Z  fix: Delta-ipTM's chain pair was chain 0 against the peptide, which for the 5-chain DCAF15 construct meant one arbitrary half of DCAF15 while the half the substrate also binds was ignored. Now the minimum over the substrate receptor's own segments, scaffold excluded. Measured first: 9 of 183 seed values move, one pair's Delta-ipTM goes +0.1872 to +0.1937, no verdict changes (F31, D-NOB-044). 240 tests.
- 2026-11-04T07:20:36Z  fix: cif2plip received the structure path as given while running with cwd elsewhere, so PLIP failed on every pair of the corrected campaign and would have failed on all 158 of the main campaign (run_chain passes a relative path). The failure was published as plip_fingerprint_match 0.0 rather than null, which would have fed 158 zeros to the weight fitter. Paths resolved; a non-ok fingerprint now yields null with its reason (F32). 245 tests.
- 2026-11-04T07:22:41Z  fix: run_campaign resolves the campaign path on entry, so recorded paths are absolute however the caller named it. The relative/absolute split between campaigns was the condition that let F32 work on one campaign and fail on the next. Swept the other subprocess call sites: Boltz runs from the project root, so no second instance. 246 tests.
- 2026-11-04T07:25:50Z  fix: bridge_formation_rate counted unmeasurable seeds (no structure, no ligand chain, no peptide chain) in its denominator, reporting a prediction nobody could assess as one that failed to bridge. Denominator now counts measured seeds only, with the unmeasurable ones reported separately. Latent so far: all 24 recorded rejects are BINMAN's single_chain verdict, a real negative (F33). 251 tests.
- 2026-11-04T07:32:13Z  ui: unmeasurable seed counts now shown beside the bridged ratio in all four display sites, through one helper, silent at zero. F33 made the number honest and left the screen reading 4/4 as perfect. Also fixed two tests that passed alone and asserted nothing in the full suite: the droplet fixture's sys.modules deletion meant they patched a different module object than routes holds. 255 tests.
- 2026-11-04T07:40:43Z  test: mutation sweep over the eight highest-consequence modules found two real coverage gaps. metrics._minimum could become max or a median with the suite still passing, so spec 4.3's defining rule was untested; geometry.score_structure could report no bridge for every structure, its success path exercised only through stubs. Both closed, all eight mutations now caught (F34). 265 tests.
- 2026-11-04T07:46:39Z  test: second mutation sweep over the remaining modules. Five guards were unexercised; three turn a failure into a plausible number and are now covered: a ternary arm with no ligand (Delta-ipTM ~0 by construction), an RMSD over mismatched atom sets (zip truncates to a prefix), and a substitution past the end of the peptide. Two left untested on purpose, with the reason recorded (F35). 269 tests.
- 2026-11-04T07:49:54Z  test: chain readiness verified end to end before the campaign finishes. No defect: all scripts exist and parse, all Python entry points resolve, the inline block's data shape matches, deploy prerequisites are present and all nine live routes answer 200. The check is now a test that hands each shell invocation to the module's own argparse (F36). 285 tests.
- 2026-11-04T07:55:49Z  fix: third mutation sweep. app/data._cached could ignore its mtime stamp with the suite passing, which would have served numbers refresh.sh had already replaced for the life of the process; degron_gate's non-glycine fallback note could be dropped unnoticed. Both pinned, with the earlier bare-name cache bug its docstring records. Dead 'if False' branch removed. DECISIONS headings aligned with the file's own convention (F37). 291 tests.
- 2026-11-04T07:59:53Z  test: the last three uncaught mutations covered. errors/warnings swap was invisible in the design manifest (no issues) and would have refused the whole main campaign (20 warnings, 0 errors): one swap, two opposite failure modes. Gate, one-parent invariant and scramble ordering pinned; ordering checked against the written manifest rather than by loading an ESM checkpoint (F38). 297 tests.
- 2026-11-04T08:06:17Z  test: fourth sweep, over yaml_gen. Three spec requirements had no test: the receptor's cached MSA could be replaced by 'empty' for every chain (spec 1.3, would have degraded all 2,360 predictions with nothing raising), the peptide could be given an MSA (spec 1.3 forbids), and affinity could be requested past Boltz-2's 128 heavy-atom cap (spec 4.7, D-NOB-005). All pinned (F39). 302 tests.
- 2026-11-04T08:11:11Z  fix: preflight now verifies each receptor chain's cached a3m is the alignment of that chain's sequence, not merely present and correctly named. An alignment for another protein passed all three existing checks and would have folded confidently against the wrong conservation. Live cache verified clean (17 files, 0 mismatches, 11/11 needed present); preflight still ok on all 2,360 jobs (F40). 311 tests.
- 2026-11-04T08:15:45Z  fix: FEM1B's construct boundary was selected by InterPro's list order. IPR036770 is annotated twice on Q9UK73 (5-301 and 424-610) and domain_by_accession took the first, so a reordering upstream would have silently moved the construct to a different 187-residue region. domains() now sorts by position and an ambiguous entry refuses unless the construct declares which occurrence it means; FEM1B declares 0. Every boundary unchanged (F41). 319 tests.
- 2026-11-04T08:20:21Z  fix: swept for F41's shape. metrics.aggregate took twelve pair-level fields from pair_jobs[0] untested (ligand_key was already handled specially, so one field was known to vary and the rest trusted); a disagreement is now recorded, worst case being a pair half degraded and half not. assemble's stated shared-glue invariant is now a precondition. Both campaigns clean across 14 pairs. degron_gate's closest-contact choice checked and correct (F42). 325 tests.
- 2026-11-04T08:27:36Z  fix: three fields added this session were set only on the branch that computes them, so bridging_unmeasurable_reasons was absent from every healthy record and plip_fingerprint_match_status from every campaign scored with --no-plip. Both now carry a reason on every path, separating 'not run' from 'failed' from 'refused'. Schema guarantee now derived from the records and compared across branches (F43). 330 tests.
- 2026-11-04T08:30:07Z  finding: CDK12/CR8 scores Delta-ipTM -0.022 by minima and +0.449 by medians. Conditioned seeds 0.745-0.851, unconstrained 0.252-0.653, conditioning_disagreement 0.494: the model does not find the glue site unaided, and the mandated minimum lands on a collapsed unconstrained seed below the binary minimum. All of it flagged by the D-NOB-023 diagnostics. Provisional at 8/10 ternary seeds. The forced flag's tooltip now carries the magnitude (F44).
- 2026-11-04T08:39:23Z  fix: projected_hours applied a 397-token representative job from the corrected campaign to the main campaign's 124-token jobs, projecting 104.3 h against the 96 h Gate G1 threshold. Gate G1 was NOT open: summing real tokens at the rate measured per job size gives 54.0 h, over the 48 h target and 42 h clear of the gate. Now takes a token total, reports its basis, and both callers pass real tokens. A false gate would have stopped the unattended build (F45). 332 tests.
- 2026-11-04T08:49:50Z  test: fifth sweep caught 1 of 5; the four misses are frozen curation code deciding campaign composition, now checked as artefacts against their rules (a library of 25,519 instead of 158 would be 383,000 jobs). The Tier B pLDDT floor applies to best_window_mean_plddt, not the mean_plddt column named after the threshold: I asserted the wrong one first. Added a cross-campaign reproducibility canary (9 shared jobs bit-identical) and fixed two tests that served the wrong campaign because create_app overrides an earlier configure (F46). 342 tests.
- 2026-11-04T09:02:41Z  fix: every BRD4/VHL job carried a hydroxyproline on BRD4 Pro379. Spec 2.3 keys required modifications on the degron class; the rule keyed on the E3, so a PROTAC-recruited substrate inherited HIF-1alpha's requirement. MZ1's VH032 supplies that hydroxyproline itself. Rule fixed, the frozen library's stale field re-derived, and tools/rerun_pair.py written to correct the 15 affected YAMLs after the run rather than mid-run, which would leave one pair holding two inputs. Found by the reproducibility canary on its first real use (F47). 356 tests.
- 2026-11-04T09:06:13Z  fix: spec 4.7 says forced hits are shown separately and never ranked. The flag was computed, published and displayed, and nothing acted on it: a forced pair could take a tier-2 decile place and 25 diffusion samples with it, and the headline scatter drew it like a found pose. Now ranked separately with the near-misses reported, and drawn hollow with the magnitude in the hover. CDK12 is the live case at 0.494 (F48). 362 tests.
- 2026-11-04T09:12:51Z  fix: read spec section 4 against the code. 4.1, 4.2 and 4.4 clean (4.2 deviates deliberately per D-NOB-024, BINMAN's reach window being uncalibrated at AUC 0.42-0.48). 4.5's About-page caveat carried the conclusion without the ROC-AUC 0.5-0.60 behind it; both now in two short sentences. Three wrong readings of mine recorded (F49). 365 tests.
- 2026-11-04T09:15:16Z  test: converted the newest source-regex check to an executed one. delta.html's forced marker and hover are now named helpers run under node against real inputs, after three naive string checks of mine were wrong today in three different places and nothing executed was (F50). 367 tests.
- 2026-11-04T09:18:42Z  fix: spec 2.2 asks for a SMILES fallback flagged 'so the difference is visible in the results table'. The manifest flagged it and aggregate dropped the encoding before the table could read it, so bench03's fallback was indistinguishable from its six CCD-resolved neighbours. Encoding and merged flags now reach the pair record and the ligand cell marks the exception. The affinity-cap rule in the same section reads clean (F51). 374 tests.
- 2026-11-04T09:22:37Z  fix: spec 5.3 asks for two tests in the matched-control layer and only the binary split was computed. Slabicki's graded labels were never acquired into BINMAN (three bibliography entries, no dataset), so the continuous test is unimplementable; the layer now names it with its reason and D-NOB-046 records the cost. Spec 5.1 and 5.2 read clean, including the seven pairs named individually on About (F52). 379 tests.
- 2026-11-04T09:26:20Z  fix: spec Phase 4 facets the ledger on modality, tier and three flags; modality and tier were there and no flag was. forced and affinity_unavailable now offered, the latter needing the same dropped-join fix as F51 plus parsing of the JSONL string 'False'. furniture deliberately not offered, with the reason in the template: ProtCID was never acquired so the control could never match (F53). 387 tests.
- 2026-11-04T09:28:57Z  fix: delta.html's ROC panel hardcoded the 3-per-side refusal floor while F28 had moved the Python side to thresholds.toml, so the chart and the validation report were one config edit from disagreeing about whether a curve may be drawn. Both now read the configured value; the test changes it and requires both to follow. A divergence I created while removing hardcoded cutoffs (F54). 391 tests.

- 2026-11-04T09:40:08Z F55: template cutoff sweep added; benchmark.html's recovery band and significance level moved to config (D-NOB-047). F56: zinc cofactor reason keyed on curated class rather than motif, recorded 'not a zinc-finger domain' against IKZF1's ZF2 window; motif now tested first, 0 of 5670 decisions changed (D-NOB-048). Suite 407 passing.

- 2026-11-04T09:49:23Z F57: three empty design_* skeletons from failed assemblies; fresh_campaign() removes a directory on failure, latest() requires campaign.json, three copies of the stamp format collapsed to one (D-NOB-049). Main campaign measured: 54 done of 2360, median 75s/job, 44 jobs/h over a 1.21h window at 101% duty, 2306 remaining projected to 46.8h compute at a single median rate, corrected to 51.4h by F61. Within MAX_COMPUTE_HOURS, no G1. Suite 420 passing.

- 2026-11-04T09:52:31Z F58: failed assemblies now append the traceback to data/manifests/failed_assemblies.jsonl before the directory is removed; test fixture leaked records into the real manifest; recorder's except OSError widened after it masked the error it describes. Design scan reassembled cleanly (design_20261104T094939Z, 240 jobs) and its cofactor record now reads the F56 reason. Suite 426 passing.

- 2026-11-04T10:04:27Z F59: the YAML on disk and the queue row describing it were never compared; 15 bench02_BRD4_VHL jobs ran on a HYP YAML the fixed rule would not emit. nobble/validate/inputs.py compares them, the atlas build refuses before writing (D-NOB-050), the chain now runs the correction between the campaign and the publish, and run_chain.sh's four 'ls | tail -1' selections require campaign.json. Mutation testing the refusal rebuilt the published atlas from a part-scored campaign; restored from git and the output directory is now overridable (D-NOB-051). Suite 436 passing.

- 2026-11-04T10:16:43Z F60: the GPU guard checked tmux session names rather than the runner process, and run_queue.sh and run_corrected.sh did not wait at all; both fixed, --throughput runs excluded (D-NOB-052), poll interval and pattern overridable so the wait itself is testable (D-NOB-053). Mutation testing found three of my own tests asserting detection without the wait. Suite 444 passing, 1 skipped.

- 2026-11-04T10:23:14Z F61: projected_hours applied one median seconds-per-token to every job while its docstring claimed per-size rates; the measured rate ranges 0.211 to 0.663 s/token by job size. Throughput now records a rate per configured token band and the projection prices each job in its band (D-NOB-054). Main campaign reprojected: 51.4h for the 2,289 remaining, Gate G1 closed with 44.6h headroom. Queued design scan projects 4.4h. Suite 455 passing, 1 skipped.

- 2026-11-04T10:30:11Z F62: dry-ran the three stages that had never executed. Scoring and tier 2 selection both work; the composite correctly refuses on 6 positives and 0 negatives. Tier 2 reuses the tier-1 YAMLs, so correcting a pair before refinement is sufficient: now a test rather than only a docstring. F59's check read queue.jsonl alone and a campaign has queue_tier2.jsonl beside it; it now discovers every queue and names which one (D-NOB-055). Hardware hard-coding rule verified sound. Suite 459 passing, 2 skipped.

- 2026-11-04T10:34:04Z F63: lift.from_scores, the design arm's entry point used by the Design tab and run_design.sh, had no test calling it; eight added, four mutations caught. Ran tools/check_prediction.py: CDK12 half of F13 supported (44.921 to 5.278 A, bridged 0/10 to 6/10, inside the 0-20 A supporting range), RBM39 half wrong by 3.342 A as F18 recorded. F18's 'CDK12 still open' closed on the complete corrected campaign. Corrected F62's claim that all three never-run stages had been dry-run: two had. Suite 467 passing, 2 skipped.

- 2026-11-04T10:37:27Z F64: restarted the local app (Jinja does not reload with debug=False, so QC would have tested the pre-edit templates) and ran node qc/qc.mjs: 14 pages, 0 non-200, 0 console errors, 0 serious axe. Verified config/ is not rsync-excluded so F55's new scoring.significance_alpha key reaches the droplet, then deployed: nine routes 200, live page carries RECOVERED_A = 5.0 from config and styles its Pearson stat from the configured alpha, HTTPS 200 and port 80 301. Atlas unchanged (still the benchmark panel's) because the main campaign's build refuses while F47 is pending. Suite 467 passing, 2 skipped.

- 2026-11-04T10:41:59Z F65: checked the priority-ordering claim Gate G1 rests on. Tiers are emitted benchmark/Sievers/scramble, and the Sievers block interleaves labels 4:1 in every quarter, so the matched-control ROC is computable at job 145 (6.1%, 6.2h) and has all 24 degraded pairs at job 1495 (63.3%, 32.8h). Seven guards added. My first mutation check rewrote the live campaign's queue.jsonl and restored it: no damage (72 unique results, completed set still the queue prefix) but the wrong method, so the check is now a pure function with in-memory negative controls. Suite 474 passing, 2 skipped.

- 2026-11-04T10:45:47Z F66: tools/mutate.py widened after two hand-rolled mutation checks reached live state today. Ad-hoc --file/--find/--replace/--tests so the safe path is the convenient one, refusal to mutate live state or anything outside nobble/tools/deploy/qc, and a before/after fingerprint of 32 live-state files that exits 4 on any change (D-NOB-056). Suite 486 passing, 2 skipped.

- 2026-11-04T10:52:38Z F67: house style enforced by nothing for the whole build; now swept (em dashes, forbidden words, British spellings) with negative controls. Codebase complies: no forbidden word or American spelling outside the files stating the rule, and the 32 template em dashes are all empty-value placeholders (D-NOB-057). F66's harness immediately found two leaks in the new sweep: an exact-form pattern missed the inflections of two terms, and its boundary test used "shelve", which does not contain "delve"; and the British-forms control passed with its loop emptied. Both fixed. Suite 501 passing, 2 skipped.

- 2026-11-04T10:58:52Z F68: site.webmanifest set theme_color to the marcdeller.com blue that depot.css names as excluded, and background_color to white against Depot's concrete; base.html's meta tags were already right, so only the installed app would have shown it. Both now read Depot's --bg, with tests that the CSS variable, meta tag and manifest agree. Three bugs in those tests were mine (a dropped static/ path segment, and a dark-mode anchor that matched depot.css's header comment twice). F67's sweep then flagged F67's own entry: a forbidden word in straight double quotes is now a citation, with quoted phrases and adjacent unquoted uses still caught. Suite 512 passing, 2 skipped.

- 2026-11-04T11:13:24Z F69: spec 1.2's BINMAN-LM component had no UI consumer; /api/ask existed and the app fetched only /api/pair/ and /api/status. Ask panel added to the Campaign tab, Depot tokens only, degrading to one sentence where no model is configured (D-NOB-058). F70: that panel made /campaign import BINMAN to ask whether a model exists, which binds app.lm and defeats the LM tests' sys.modules fake; two tests that passed alone failed in the suite. available() now checks BINMAN_LM_URL before importing, same verdict without the side effect. Suite 524 passing, 2 skipped.

- 2026-11-04T11:17:43Z F69 deployed: QC 14 pages, 0 non-200, 0 console errors, 0 serious axe; nine routes 200 on the droplet; the ask panel is live and reads 'No model is configured' there, which is correct because the droplet serves a precomputed atlas with no request-time compute. The manifest's Depot colours are live too. Restarting the local app needed a kill by pid: the pkill pattern contained parentheses and matched nothing, so the first QC attempt measured the pre-edit templates and found no panel.

- 2026-11-04T11:21:53Z F71: D-NOB-007 was enforced by nothing. Swept every file shared with BINMAN or BoltzMaker: readme_forge.py and elementor-widget-markdown.css are byte-identical, wsgi.py and tools/hwprobe.py differ and are now allowed with reasons (D-NOB-059); hwprobe is 388 diff lines, so independent implementations rather than a fork, with the hardware half recorded as genuine duplication. Also added a drift check that README.polished.md is what the forge would produce from README.md, plus the idempotency that makes that comparison valid. Suite 536 passing, 2 skipped.

- 2026-11-04T11:29:49Z F72: ATLAS.json's redactions count was initialised to 0 and incremented nowhere, so every published atlas claimed it had withheld nothing while carrying a smiles_withheld field; on a licensing guarantee that reads as 'no PROTAC-DB chemistry was present'. Real figure is 1 (dBET57), now counted with the ligands named so a zero is distinguishable from a detection that stopped firing. Published atlas rebuilt: redactions 1. Found by sweeping 515 test functions for assertions that only run inside a possibly-empty loop; the PROTAC-DB leak check was one, and now counts what it read with empty-bundle and planted-marker controls. Suite 545 passing, 2 skipped.

- 2026-11-04T11:36:16Z F73: corrected F65's table. The matched-control ROC is computed over the Sievers arm alone and my count included the seven benchmark pairs, which carry the 'degraded' label and complete first, so the floor was reported at job 145 (6.1%, 6.2h) when the answer is job 400 (16.9%, 11.2h); every row was optimistic by about a factor of two. Both published tables corrected. The protecting test shared the error, so ROC_ARM and ROC_LABELS are now named once in layers.py and imported. Suite 547 passing, 2 skipped.

- 2026-11-04T11:39:35Z F74: matched_control_roc selected its groups with isinstance(v, (int, float)), and NaN is a float. A NaN loses every Mann-Whitney comparison rather than raising, so it is scored as a unanimous loss: one NaN among three positives takes the AUC from 1.0 to 0.667, biasing the headline towards the null. Python's json round-trips NaN through scores.jsonl, and a bool would have passed too. _finite is now the filter, _auc refuses non-finite input, and the layer reports non_finite_dropped separately from unscored. No record carries one today. Suite 556 passing, 2 skipped.

- 2026-11-04T11:41:08Z F75: tested whether pocket conditioning costs anything per token, after a conditioned job appeared 11% slower. It is a size confound: across 276 timed jobs the two conditionings agree to the fourth decimal at every token count where both exist. F61's banding by token count alone is correct; recorded in projected_hours's docstring so the factor is not added later without evidence. Campaign health verified: recorded durations match arrival gaps to within 6s, job 77 at 864s against the previous conditioned job's 902s.

- 2026-11-04T11:48:49Z F76: F74's isinstance(v, (int, float)) idiom appeared in 14 places; one rule now lives in nobble/numeric.py with a sweep that fails on a fifteenth. The two worst sites were tier2.choose_ranking_key, which directs the refinement budget, and score.run's bridge percentile median taken by index from a sorted list: one NaN leaves the whole list unsorted, giving 10 where the answer is 70 on spec 4.1's primary signal. Refactor verified behaviour-preserving (0 disagreements over 3,023 lists; 22,500 floats checked, none non-finite). percentile_of's bisect_left and lru_cache reviewed and sound. Suite 566 passing, 2 skipped.

- 2026-11-04T11:52:26Z F77: the composite's 0-to-1 clamp converted a non-finite component into 1.0, the maximum score, because min(1.0, nan) returns 1.0; an unmeasurable bridge percentile would have ranked as the best bridge in the panel. Non-finite is now absent and the weighted mean renormalises, while a genuine out-of-range value is still clamped. weights.py also carried a second Mann-Whitney estimator, never hardened when F74 hardened layers.py, and it is what the grid search maximises; the arithmetic is now shared in nobble/numeric.py with a sweep against a third copy, each caller keeping its own empty-side contract. Suite 576 passing, 2 skipped.

- 2026-11-04T11:58:45Z F78: _rmsd could return NaN (gemmi.Position accepts a NaN coordinate) and every consumer filtered on 'is not None'. pose_recovery's best, median and worst all came from a sorted list a NaN leaves unsorted, and success_rate_curve counted a NaN as a failure at every breakpoint while keeping it in the denominator. Now unmeasurable rather than numeric; 221 published rmsd fields compared before and after, none moved. The external route (a CIF carrying a NaN coordinate) is unproven and recorded as such. Suite 585 passing, 2 skipped.

- 2026-11-04T12:04:16Z F79: cost_of's tokens_per_pair (F45) and job_tokens (F61) were never passed by either call site, so the design arm kept taking the representative-job fallback F45 exists to replace. Right only by coincidence: remeasure throughput on the corrected campaign and the same scan projects 11.5h against a real 4.4. The preview now prices the exact job list build_manifest would emit (240 jobs, 32,960 tokens, 4.4h). Found by running the chain's stages on real data after a day of refactoring; nothing had regressed. Suite 592 passing.

- 2026-11-04T12:10:22Z F80: swept every optional parameter in nobble/ against every call site; 22 are never supplied, three stated a reason nothing exercised (the timeout override whose comment cites a test that did not exist, cost_of's tokens_per_pair, matched_control_roc's statistic) and are now tested. Following the timeout found tier 2's 'job_timeout_seconds * 4', an inline factor deciding when a refinement is killed: a fifth place the cutoff sweep does not look, after comparisons, module constants, default arguments and templates. Now tier2_timeout_multiple in tuning, with the uncertainty recorded: 4 is a guess, tier 2 has never run, and a timeout is reported with its value so the first campaign measures it. Suite 601 passing.

- 2026-11-04T12:17:09Z F81: plip.fingerprint's chain-map fallback appended 'treat this fingerprint as unverified' to notes and then set status ok, and run.py branches on status and never reads notes, so the match was published as a measurement. The fallback is correct for three chains and wrong for the four a structural zinc gives, where it hands the ligand slot to the ion; the Sievers arm is 120 zinc-finger pairs beginning at queue position 100 and the campaign is at 78. An unparsed map now refuses. All 20 real fingerprints so far parsed the map, so this has never fired. Also removed the superseded design campaign (pre-F56 cofactor reason, 0 of 240 run). Suite 601 passing.

- 2026-11-04T12:20:37Z F82: verified the four-chain fingerprint path before the Sievers arm reaches it. A real ternary with a zinc inserted as chain Z parses as A-A, P-B, Z-C, L-D; the glue is identified as chain D, the ion's row is excluded, and real contacts survive. So F81's refusal is a floor rather than a behaviour change, and F14's ion exclusion is confirmed on four chains for the first time. The assembler's A,P,Z,L order was read from a real Sievers YAML rather than from the comment asserting it. Suite 605 passing.

- 2026-11-04T12:23:36Z F82 corrected: the four-chain fingerprint path had already been covered by test_plip_ions.py against a real prediction in campaigns/smoke_sievers (sv_neg_ZN346_d5063d, chains A P Z L). My claim that it had not been exercised was wrong, and the structure I constructed was unnecessary. I checked zinc_probe, found peptide-only predictions and generalised. The test now uses the real prediction and keeps the one genuinely new assertion: the mapping itself, Z to C and L to D, which the existing tests do not pin because they assert the consequence instead. Suite 605 passing.

- 2026-11-04T12:30:38Z F83: verified Delta-ipTM's chain arithmetic on a real four-chain Sievers prediction before the arm runs: iptm_min_ternary 0.952 and binary 0.856, the receptor-to-peptide values. The matrix is asymmetric, so the ion is a zero target and an ordinary source: reading it as the peptide gives 0.0, as a receptor segment gives 0.99. All 2,160 zinc jobs are one-segment CRBN_CULT, now asserted. F84: tools/mutate.py counted a SKIPPED mutation as caught, so a sweep with stale anchors reported 'N of N caught' and exited zero, a false all-clear from the tool built to find false all-clears. Skips are now counted, named and non-zero; the five fixed anchors were checked and none is stale. Suite 611 passing.

- 2026-11-04T12:35:52Z F85: swept the four sites with arithmetic inside report strings. Two correct and now pinned (runner.py's 1-based unrun count, inputs.py's truncation count). One wrong and mine: pose_recovery's note explained every missing pair as 'jobs have not completed' while F78 had given it a second cause, an unmeasurable RMSD; counted apart now with a live check that the notes account for exactly the missing pairs. Two of my own tests in this batch were also wrong: one grepped for a sentence split across f-string lines (F50's shape), and F84's harness test failed whenever the tree was dirty rather than skipping on the harness's own correct refusal. Suite 616 passing.

- 2026-11-04T12:39:05Z F86: reviewed spec 4.2's lysine component and found nothing to fix; it is among the more careful modules. The fitter deliberately includes the unvalidated component and caveats it rather than excluding it, which is the right call and now recorded. The caveat is read by about.html but had never rendered, the composite never having fitted, so the fitter-to-page path was established by inspection; now driven with a synthetic fitted result, and a clean fit is checked to show no caveat block. Done now because the composite needs negatives and the Sievers arm starts in 21 jobs. Suite 621 passing.

- 2026-11-04T12:46:21Z F87: spec 4.4's convergence scale was a bare 10.0 inside the score expression, the same fifth place as F80; now scoring.convergence_scale_a with a test that changes it and requires the score to follow. The filter feeding it is finite rather than is-not-None, making F78's guarantee local. The second half of this finding was wrong: I claimed the ipTM minimum admitted a NaN, and the mutation harness showed reverting that filter fails no test, because _pair_iptm already requires finite per cell (F76). The change stays as defence in depth with the comment saying it is redundant. F84's skip-reporting fix also paid for itself: the first attempt at that mutation was skipped on a duplicated anchor and said so. Suite 627 passing.

- 2026-11-04T12:48:16Z F88: diffed the published atlas against a rebuild with today's code, leaf by leaf. 10,969 values compared, 2 moved, both F79's design-cost repricing (4.2 to 4.7 hours, representative-job basis to banded); every RMSD, ipTM, bridge percentile and the comparison report identical. One false alarm: 34,720 tokens against the 32,960 I had measured is a different parent, GSPT1 for the atlas preview and IKZF1 for the assembled scan, both 15-mers emitting 240 jobs. Suite 627 passing.

- 2026-11-04T12:53:57Z F89: build_atlas.py never configured a campaign before building the design report, so data.scores() was empty, the measured ranking saw nothing and every published atlas chose its scan target by the length fallback the ranking exists to replace. The site said GSPT1 and the chain assembles IKZF1 (+0.316 delta-ipTM). Both now read the same ranking; rebuilt and deployed, published parent IKZF1 at 4.4h. The cost also names its parent now, since two 15-mers emit the same job count and different token totals. Found by following up F88's false alarm rather than leaving it explained. Suite 632 passing.

- 2026-11-04T12:56:44Z F90: F89's configure call sat immediately above the section that needed it, leaving the benchmark and About sections depending on not needing the data layer. Moved to the top of main() where the campaign is resolved; 11,002 leaf values compared against the published atlas and none moved, with benchmark.json and about.json byte-identical. The test asserts position rather than presence, since a call somewhere in the file is what was true while the bug existed. Suite 634 passing.

- 2026-11-04T13:01:20Z PROGRESS.md brought current: it was last accurate at F73 and had drifted through seventeen findings. Records the F74-F90 scoring review as one group, the four-times-asked NaN question, the tooling fix that found two of them, and the four false alarms. QC re-run after the atlas content change: 14 pages, 0 non-200, 0 console errors, 0 serious axe. Suite 634 passing.

- 2026-11-04T13:05:41Z F91: campaign.seeds in tuning.toml was read by nothing; two hard-coded SEEDS tuples in manifest.py and corrected.py decided the behaviour, so editing the configured value changed nothing. Now derived once from config and imported by corrected.py, which matters because a corrected campaign with a different seed count from its benchmark breaks the comparison's premise. Behaviour-preserving (same tuple, jobs_per_pair still 15, live queue seeds asserted). Module-level numeric collections are a sixth place the cutoff sweep does not look, after comparisons, constants, default arguments, templates and arithmetic. Fifth false alarm: ten 'extra' manifest jobs were the assembler's recorded conditioned_jobs_dropped_no_pocket = 10. Suite 640 passing.

- 2026-11-04T13:09:05Z F92: tools/status.sh gained a provenance section (tools/provenance.py) printing the three facts my five false alarms each turned on: jobs emitted against conditioned dropped for having no pocket, stale inputs and therefore whether the atlas build refuses, and the design target the ranking chooses against the one the site publishes, with the disagreement marked. The marker is tested by feeding it a published file naming a different parent. Suite 645 passing.

- 2026-11-04T13:18:51Z F93: corr05_CSNK1A1_CRBN submitted a 269-residue substrate domain and the plan now specifies 219 (P48729 17-235, the shorter a strict substring), and the corrected campaign recorded no substrate plan so nothing noticed. CSNK1A1 is one of the six pairs in the published improved list (12.24 to 6.189 A) and the published plan is recomputed at build time, so plan and result described different constructs. superseded_substrates compares the YAML against the plan, which stale_inputs cannot since both its sides come from one assembly; the caveat is on the conclusion because that is the line that gets quoted, and it says the measurement stands. My own guard's len < 30 was caught by the cutoff sweep and replaced by matching the curated fragment sequences. Suite 650 passing.

- 2026-11-04T13:21:55Z F94: corrected.assemble() now records the substrate plan it ran under, including the InterPro or PFAM entry each boundary came from, which is the part that moves. Writing it down showed that five of six folded domains resolve from IPR entries and CSNK1A1 from PF00069, and CSNK1A1 is the one that moved: recorded as a signal rather than a cause, with the PFAM-sourced set pinned at exactly CSNK1A1. The published plan still describes current intent and the comparison beside it carries the caveat, which is deliberate. Suite 654 passing.

- 2026-11-04T13:25:37Z F95: swept every paths.thresholds() and paths.tuning() key chain in the project against the real TOML. 89 chains, all resolve. Kept despite finding nothing because an indexed miss raises loudly while a .get miss returns None silently and flows on; both forms are swept. The other direction of F91, which found a configured key nothing read. Mutation-checked with a typo in each form. Suite 657 passing.

- 2026-11-04T13:29:36Z F96: F93's superseded-substrate caveat was written, tested and committed, and had not reached the page: comparison.json is built by the atlas and the atlas had not been rebuilt, so both the live site and the local bundle ended the conclusion before it. The same shape as F81, a warning nothing downstream read. Rebuilt and deployed, nine routes 200, live conclusion now carries it. Found by re-running the chain's six stages end to end after a day of changes to eight modules; everything else still runs. Suite 656 passing.

- 2026-11-04T13:35:21Z F97: closed the gap F96 named. tools/atlas_drift.py rebuilds from the campaign the published atlas names and compares leaf by leaf (11,008 values, 4s); deploy.sh refuses before the rsync rather than rebuilding silently, and status.sh reports it. The exclusion list is tested in both directions: build-time facts excluded, and redactions, conclusion, median_rmsd and auc asserted not excluded, since F72's count was misreported. The control is the F96 case itself, strip the caveat and confirm the check names the field, with a restore check after. Both mutations caught. Suite 662 passing.

- 2026-11-04T13:39:59Z F98: checked D-NOB-035 rather than re-opening it. The Sievers arm carries no MSA and the recorded reason is the ROC, not the cost: the matching was on length and composition, not on how well studied the parent gene is, so alignment depth could correlate with the label. Nobody had checked the arm against that description. All three premises hold in the queue: 24 degraded from 24 distinct genes, 96 controls from 86, both median length 23 (range 23-26), composition matched within two points on every class. No change made; tests/test_sievers_matching.py pins the numbers, the msa: empty, and the decision. Suite 668 passing.

- 2026-11-04T13:49:05Z F99: tier 2 has never run, so I checked it. The Boltz flags are valid. One layer down, _read_outputs asked for the structure by rank and the confidence by directory order, which agree at one diffusion sample and not at twenty-five: replaying the old code on a fresh 25-sample directory gave structure rank 0 with confidence rank 14. All ten tier-2 jobs would have differenced ipTMs belonging to poses nobody scored. Confidence is now derived from the chosen structure filename rather than searched for, with a named reason when it is absent. The replay also caught an unpadded-rank sort picking _model_10 over _model_3, in my own replacement as well as the original; structure choice is now by numeric rank. Tier 1 unaffected and verified on a real output directory; tier2.sh spawns a fresh runner so no restart is needed. Suite 675 passing.

- 2026-11-04T14:03:41Z F100: tier 2 timeout was a global cap times a guessed multiple of 4, applied per attempt with one retry. Tried to measure the scaling from BoltzMaker: 146,761 runs, every recycling_steps and sampling_steps null, so no such data exists anywhere. Bounded it instead from config ratios plus a potentials allowance, deliberately double-counted so it is an upper bound at any trunk/diffusion split. Against the live campaign six of seven pairs had 4.6x to 10x headroom and bench06_RBM39_DCAF15 had 0.83x: the DCAF15 assembly is 1,223 tokens by construction and its bound is 7.2h against a 6.0h cap. Each refinement now carries a budget sized from its own pair measured tier-1 cost with the cap as a floor, and the budget is per job not per attempt, so a crash retries with the remainder and a timeout does not retry. D-NOB-060 records the trade-off. Suite 690 passing.

- 2026-11-04T14:10:23Z F101: F97 excluded throughput from the atlas drift check and not the values computed from it, one line away in the same tuple. Thirteen jobs later the check reported 63 drifted values, all design preview costs moved by remeasured token bands (0.663 to 0.7375 s/token on the 800-1600 band as the DCAF15 jobs landed). Nothing was wrong, but deploy.sh refuses on drift and the report prints six rows then "and 57 more", so a real difference like F96 would have been in the 57. Third instance of the same habit after F74, F78 and F89, and the first in my own code from an hour earlier. Drift now returns two categories, moved and recomputed, matched on whole leaf names so the second cannot widen; the control strips the published conclusion and confirms it is still reported, still fails, and still prints in the first six rows. The count reaches status.sh. Suite 696 passing.

- 2026-11-04T14:13:59Z F102: Boltz reports ligand_iptm for whichever het group is in the job, so on a Sievers pair it is the structural zinc. The arm reached job 100 and the first completed result gives ligand_iptm 0.9946, exactly the zinc row of pair_chains_iptm, on a binary job containing no glue. Nothing reads it and it is not published, so this is a note with a test that fails if any module starts reading it. Verified on real output while there: the zinc is in the binary arm (chains A 109, P 26, Z one ZN) as D-NOB-034 requires, and pair_chains_iptm is more asymmetric than the smoke test showed, 0.8561 one way and 0.9274 the other, with the zinc column 0.0 and its row 0.9946; _pair_iptm already takes the minimum and the metric uses receptor chains only, giving 0.8561. Suite 700 passing.

- 2026-11-04T14:27:44Z F103: audited pose recovery because the live median of 17.14 A with 0 of 65 within 3 A is either Gate G6 or a measurement bug. Ruled out both: the receptor anchors at 1.751 A over 436 atoms, all seven reference chain pairs are genuine interfaces (minimum interatomic distance 1.84 to 2.80 A), and residue identity matches in all seven including GSPT1 at 138 residues from canonical. So the number is real, and F6 had already diagnosed it as the cost of a 15-mer cut from a folded domain, with the benchmark page already showing the domain comparison beside it and IKZF1 named as the control. No gate. The gap was that nothing asserted any of it, on the layer that decides whether the positive controls work; the residues are now compared and the RMSD withheld when too few agree, with a control that shifts the frame by fifty residues. My first version used exact equality and refused CDK12 in the corrected campaign over 293 of 294, a single K to R where 6TD3 differs from Q9NYV4: the floor is now in thresholds.toml at 0.9, which separates variation from misalignment by a wide margin. Corrected first-seed recoveries measured while there: 1.118, 1.46, 16.152, 5.357, 6.122, 0.659 and 2.367 A. Suite 707 passing.

- 2026-11-04T14:36:01Z F104: two labels describing the wrong data. The throughput note read "Measured on the benchmark panel" as an unconditional literal, true for 100 jobs and false from job 100 where the Sievers arm begins, with the two arms differing in per-job cost by a factor of 26; it is published in the atlas where throughput is excluded from the drift check, so nothing would have caught it. It now counts the arms. And the weight fit said nothing about a comparability it inherits: delta_iptm takes a minimum over 10 ternary jobs against 5 binary for every pair, which D-NOB-023 states the principle for but only applied across tiers. No effect on the ROC, which is scoped to the Sievers arm where all 120 pairs share one shape and which already refuses on unevenness, and measured at 0.0014 on the first complete pair against a delta of 0.179. The fit now reports its seed-shape composition, computed before the floor returns early, and caveats the two of 158 panel pairs whose conditioned arm was dropped for having no pocket. Four-chain path confirmed on real output: A 109, P 26, Z one ZN, L one Y70, four by four matrix. Suite 719 passing.

- 2026-11-04T14:45:35Z F105: the design page said the composite is not validated in three places and derived it in none. score_validation read data/atlas/validation.json, a path that has never existed, guarded by if exists() so it returned {} on every build; the caveat was a Python literal asserting the ROC reports not_computed, which becomes false the moment the Sievers arm lands; and design.html checked the caveat field then rendered a literal of its own, so a derived sentence would have been computed, published and never shown. F96 inverted, three times over, in the panel whose job is to stop a scan reading as a prediction. Status now read from the campaign with the published atlas as fallback, an unreadable status falling back to not validated, the sentence derived and naming the AUC and CI, and the template rendering it at 20 words against a budget of 40. Two of my own mistakes caught by reading output: a local variable named campaign shadowed the argument I added, and the diagnostic published an absolute home-directory path that differed between relative and absolute invocation so the drift check could never settle. Added a check that no published JSON carries a local filesystem path, which nothing had alongside the PROTAC-DB redaction check. Atlas rebuilt, drift in step across 11,014 values.

- 2026-11-04T14:50:48Z F105 deployed. Atlas rebuilt from benchmark_20261103T192126Z, drift in step across 11,014 leaf values with 62 costs recomputed from new timings, nine routes 200, and the live design panel now carries the derived sentence rather than the template literal. Suite 734 passing.

- 2026-11-04T14:56:37Z F106: the composite has five components under two sets of names, the fitter naming each after the column it reads and the UI after the signal. Four agree; lysine_reach_exposed_fraction against lysine_reach does not, so a join by key loses one of five and fitted_w.get(key, default) renders the miss as a plausible 0.0. Already fixed in the JavaScript, which builds an alias map and says why, and not in the Jinja that renders the same slider initial value, so the two layers disagreed and the right one was the one that ran second. Latent only because the fit reports not_fitted with no weights; it would bite when the fit lands at the end of the campaign. The map now lives in data.py with a fitted_weight function, the route passes both, and three of nine tests hold the invariant rather than the instance. Found by sweeping templates for asserted rather than derived state after F105; the sweep also confirmed about.html and campaign.html derive theirs correctly, so F105 was an instance and not a class. Suite 743 passing.

- 2026-11-04T15:15:23Z F107: the question PROGRESS listed as unanswered was a bug. domain_context returns every enclosing annotation and benchmark_substrate_constructs submits domains[0], from a list in InterPro response order that was never sorted, so the submitted construct depended on how the API had ordered its records: the library manifest names IPR000719 for CSNK1A1 and the same call today returns PF00069 first. The kinase question has an answer and three lines agree: CDD 16-281, SMART 17-283 and the PROSITE profile 17-285 all match IPR000719 17-285 against PF00069 17-235, and 5FQD chain C resolves 10-303 continuously with no gaps, so the 50 residues PF00069 drops are ordered structure. Ordered now by D-NOB-061, longest domain-level entry with InterPro preferred on a tie; one of seven constructs moves, CSNK1A1 to 269, which is what the campaign ran. The superseded-substrate caveat comes off the published conclusion, no substrate is PFAM-sourced any more, and the test that pinned that anomaly was pinning the bug. Also fixed: the note and the plan reason quoted max_coverage, which belongs to the smallest enclosing domain, beside a different domain name on 7 of 121 substrates. Running campaign unaffected. Three near-misses of mine recorded. Suite 756 passing.

- 2026-11-04T15:19:38Z F108: the same unsorted-list-read-by-index defect on the receptor side, inside domain_by_accession, whose docstring describes F41 having fixed it. F41 required the caller to name an occurrence "counted from the N-terminus" and then indexed the response list, so it replaced whichever InterPro listed first with whichever InterPro listed Nth. Latent because response order and N-terminal order agree for FEM1B today, [0] 5-301 and [1] 424-610, so FEM1B_ANK gets the 297-residue region it declares; the day they stopped agreeing a benchmark E3 receptor would silently become the 187-residue C-terminal one, which is exactly what happened to CSNK1A1 on the substrate side. Sorted by start before indexing, so the contract the docstring already stated is now kept. Tested by handing back the two annotations reversed, which fails against the old code. Both consumers of the raw list are now ordered. Suite 759 passing.

- 2026-11-04T15:24:20Z F109: tools/rerun_pair.py --apply is the pending F47 correction, it runs once by hand against a campaign holding days of compute, and it had no test; the only mentions of it in the suite were comments in other tests saying it was pending. Its matching rule is careful, exact pair_id or job_id prefixed with the __ separator, and it keeps unparseable lines and takes a .bak. The write was not atomic: write_text truncates first and state.jsonl is how a 2,360-job campaign knows what it has run, so a kill in that window leaves a partial record and the campaign re-runs whatever was lost. Now written to a sibling and renamed. Ten tests added covering the matching rule, the prefix case, a running row with no pair_id, a torn line, the no-match case taking no backup, the backup not being overwritten on a second run, and a kill inside the rename leaving the original intact. Suite 770 passing.

- 2026-11-04T15:29:29Z F110: the sweep after F109 found three more non-atomic writes, all caches. The InterPro cache is JSON so damage fails to parse, which is the subtle case: _fetch keeps it because it exists() and never re-fetches, and domain_context swallows the parse error into interpro_unavailable, dropping a substrate from its folded domain to the 15-mer, which is the F6 experiment independent variable changed silently and permanently by one kill. The UniProt sequence cache is plain text and worse: a truncation is still a valid-looking protein with no parse step to fail at, so every domain slice taken from it is quietly short. All four writes now go through paths.write_atomic, renaming a sibling into place, with the temporary beside the target because the guarantee does not cross filesystems. The sequence cache also refuses an empty or non-residue file and names the path to delete; a clean truncation is still valid residues and is not caught, which is why the write is atomic rather than merely checked. Live caches measured intact, 1,201 responses parsing and 16 sequences between 102 and 1,490 residues. Suite 779 passing.

- 2026-11-04T15:31:11Z F108 corrected. The write-up said "FEM1B is a benchmark E3". It is not: the benchmark E3s are CRBN, DCAF15, DDB1 and VHL, and the main campaign submits CRBN_CULT on 2,270 jobs with VHL_VCB, DCAF15_DDB1_DDA1 and DDB1_BPC on 30 each. FEM1B_ANK and KEAP1_KELCH are declared, budgeted and tested and submitted by no job in any campaign, so interpro_occurrence is used by one construct and that construct is unused. The broken contract is real and its blast radius today is nothing. Found by comparing E3_TO_CONSTRUCT values against the constructs the queues name.

- 2026-11-04T15:41:21Z F111: the runner appends results.jsonl a row at a time and may be killed at any moment, and its own state.jsonl reader has always tolerated a torn final line. Seven other readers of the same append-only files did not: metrics.aggregate, score/run, write_throughput, the pose-recovery and ROC layers, design/lift and the tier-2 selection, which between them are every stage that runs after the compute. A kill at the wrong moment made them raise instead of processing the complete records. scores.jsonl is in the same position by another route, written in one pass so a kill truncates it. One shared paths.read_jsonl now, with tolerate_torn named per call site; the six queue and manifest readers stay strict on purpose, because a damaged input is not a torn tail and skipping it would run 2,359 of 2,360 jobs in silence, and a test holds that they do not acquire the flag. paths.torn_lines counts them so a tear can be reported rather than swallowed. Suite 787 passing.

- 2026-11-04T15:45:01Z F111 completed. The six strict readers now call read_jsonl(path) explicitly, because my own strict-side test was vacuous: it inspected lines containing read_jsonl and the queue readers were still bare comprehensions, so nothing matched and the loop never ran. Found by asking what a mutation would have to hit. It now counts what it inspected and requires at least five, and a behavioural test drops a torn line into a real queue and confirms run_campaign raises. The tolerant half is confirmed load-bearing by tools/mutate.py: reverting metrics.aggregate to the bare comprehension is caught. Suite 790 passing.

- 2026-11-04T15:46:39Z Re-ran the browser QC against the live site after the F105 and F106 template changes, since a page returns 200 with a broken script and dead sliders. node --check parses the 155 KB inline script, and qc/qc.mjs reports 14 pages captured, 0 non-200, 0 console errors and 0 serious axe violations at both viewports. The previous report predated both changes.

- 2026-11-04T15:52:31Z F112: nobble/execute/watchdog.py exists because F20 cost most of a night to a stalled campaign that looked alive, and it was reachable only from tools/status.sh, which the chain calls on its last line. So across the forty-seven hours a stall is possible nothing consulted it, and it spoke once when the answer could no longer matter. Armed in run_chain.sh now for the length of the chain, every 600s by default, keyed on the exit code rather than the printed verdict because grepping "   ok  " would couple the chain to a status line layout as F54 did. Verified read-only first: the only kill in it is prose, it runs no subprocess and writes no file, and a test strips comments and docstrings to hold that. Replaced by rename because the chain is running and bash reads a script by byte offset, which is F57 applied to its own fix; a separate watch is armed for the current campaign since it executes the old inode. Suite 797 passing.

- 2026-11-04T15:58:34Z F113: F100 and F107 were written under decision ids that already existed. I grepped ^## D-NOB-03[0-9], saw 039 as the highest and took 040 and 041, which are "the design scan picks its target after the main campaign" and "the site is not republished while a campaign is running", the second cited by name in run_chain.sh. Renumbering to 050 and 051 collided again. Same cause as F107 and F108: a fact about a collection inferred from a pattern that did not cover it. Measured instead, 53 headings and 51 distinct numbers with 59 the highest, and mine are now D-NOB-060 and D-NOB-061, above the highest rather than into a gap. tests/test_decision_ids.py holds that no number is used twice and that every citation in the code or the logs resolves. Its own first version matched only ## headings and reported 1 to 7 as unused; they are the spec table rows at the top of DECISIONS.md, where CLAUDE.md own citation of D-NOB-007 resolves, so it reads both forms now and there is one real gap, 45. Suite 803 passing.

- 2026-11-04T15:58:59Z Checked the findings log for the same collision F113 found in the decisions: 113 entries, no gaps, no duplicates. The three apparent collisions are the deliberate F2b and F4a sub-entries and F82 with its original text preserved beside the correction, which a regex matching ^## F(digits) reads as the parent number. No test added, because unlike the decision ids no collision has happened in 113 entries.

- 2026-11-04T16:03:28Z F114: F103 changed recovery_against_crystal, and the README leads with three numbers that come out of it: GSPT1 29.22 to 1.17, BRD4/VHL 19.23 to 1.71, and the IKZF1 control moving exactly 0.00 because it keeps its 15-mer in both campaigns. Recomputed over all ten seeds each: 29.221 to 1.171, 19.235 to 1.711, and 5.357 in both so 0.000 between them. Every figure holds, so nothing was wrong; what was wrong is that nothing would have said so, and the only thing between a published claim and a silent change to it was my noticing. tests/test_readme_figures.py recomputes all three from the campaigns rather than from a fixture, with the control as its own test since it is the claim the other two rest on, and one test asserting the README still quotes the figures, because a pin guarding a reworded sentence keeps passing. Suite 808 passing.

- 2026-11-04T16:04:17Z Checked the icon deliverables: nobble_icon.svg and the 300px render for the blog mark, nobble_favicon.svg as master plus the generated favicon.ico, favicon.svg, apple-touch-icon.png, icon-192, icon-512 and site.webmanifest, all present in nobble/app/static/img and all six serving 200 live. The two specifics the skill calls out both hold: the manifest paths resolve to the served locations, and apple-touch-icon.png is RGB with no alpha channel, so iOS has nothing transparent to composite to black. Theme and background are Depot palette E9EAE5 rather than the house blue, which is correct for the app UI.

- 2026-11-04T16:08:41Z F115: percentile_of bisects the atlas distribution, and every comparison against a NaN is false, so bisect_left returns 0 and a non-finite dSASA would be reported as bridge percentile 0.0: not a refusal but the lowest real value, on spec 4.1 primary signal and the key tier-2 ranks on. Unreachable, and that is the finding: BINMAN find_bridges admits a half only when dsasa >= min_dsasa, NaN >= x is false, and dsasa_total is the sum of two qualified halves. Verified rather than argued, and every bridge percentile in every scored campaign is finite and in range. Pinned anyway because the protection is one line in another repository and the equivalent rewrite not (dsasa < min) reads identically and accepts NaN, with a control that the floor is applied at all so the NaN rejection cannot pass for the wrong reason. Note the asymmetry: the same function treats a missing reference distribution as NaN and would treat a missing value as zero. Sixth unreachable concern this build. Suite 813 passing.

- 2026-11-04T16:14:05Z F116: spec section 4 read against the code, the audit F52 did for section 5. Most holds: 4.5 calibration note on About, 4.2 lysine substitution recorded as D-NOB-024, 4.8 sliders, 4.1 percentile against the 285,996. One clause did not, in the view the spec calls the headline: the Delta scatter plotted bridge_percentile === null ? 0, so a pair with no measurable bridge was drawn on the axis among pairs with a genuine weak bridge, and the hover turned the plotted position into "bridge percentile 0.0". CDK12 is that pair, all ten seeds rejecting as single_chain. The campaign table already blanked the cell and named the reject reason, so one surface distinguished absent from worst and the headline did not. Same hazard as F115 arriving by presentation rather than arithmetic. Those points now sit in a labelled band below the axis with the hover reading from customdata, kept in the chart because a pair that vanishes is worse than one drawn wrongly. Suite 820 passing.

- 2026-11-04T16:20:56Z F117: build_atlas verifies that no PROTAC-DB chemistry reaches the published bundle, and nothing verified the other direction, that every SMILES which is published has a source permitted to be. Read record by record off the live bundle: seven ligand records, six sourced deposited_ternary from the PDB entries and published, one dBET57 sourced protacdb and withheld, and UbiBrowser and BioLiP2 appearing only as availability booleans in about.json rather than as rows. The constraint holds in both directions now, with four tests including one that no restricted source name carries structured content, which is the shape a leak would take. My first assertion was wrong and the data corrected it: a withheld record keeps the smiles key set to null beside smiles_withheld, which is the better shape, so the test asserts no value rather than no key. Suite 825 passing.

- 2026-11-04T16:22:21Z F118: spec sections 2 and 3 read against the code, the audit F52 did for section 5 and F116 for section 4. All clean. 2.2 holds both clauses, CCD over SMILES with the fallback flagged and affinity_unavailable recorded rather than failing the job. 2.3 is covered from two sides, manifest.validate erroring on a missing residue type and stale_inputs comparing YAML modifications against the queue row, which I checked is symmetric in all four cases rather than assuming. 3.4 records the reduction ratio 0.0062 and the clustering parameters in the library manifest, 25,519 candidates to 158 selected. That explained the empty esm2 cache: diverse is 0 because the mandatory sources contribute 127 of a budget of 156 and the full mandatory set is 158, so embed() was called on no optional candidates. An empty cache is the consequence of a budget rather than a stage that did not run. 3.5 was already audited: ESMFold is unused because none of its three cases arose, and the disorder prefilter the spec warns about does not exist.

- 2026-11-04T16:24:17Z Re-ran the chain end to end on its non-GPU stages after a day of changes to eighteen modules, which is how F96 was found. All ten clean: preflight on the main campaign ok true, scoring the corrected campaign exit 0, the three validation layers with pose_recovery computed and the other two correctly not_computed, compare giving seven comparisons and zero superseded substrates so F107 fix holds, the design report building 31 parents with a derived caveat read from a real file, tier-2 selection returning one pair, the atlas build verifying no PROTAC-DB chemistry, drift in step across 11,008 values, provenance reporting all four lines, and check_prediction exit 0. The GPU stages are being exercised by the running campaign.

- 2026-11-04T16:25:15Z Verified today fixes with tools/mutate.py, the project own primary defect-finding tool, rather than trusting that my tests covered them. Eight mutations, eight caught: F99 the confidence derived from the chosen structure reverted to a first-glob hit, F100 the attempt given the full budget rather than the remainder, F105 the caveat replaced by the literal it used to be, F106 the alias resolution removed so the fitted weight lands on no slider, F107 the enclosing-domain sort removed, F108 the N-terminal sort of an entry occurrence removed, F110 the atomic rename replaced by write_text, and F111 the tolerant reader reverted to a bare comprehension. Each named a specific failing test. The fixes are load-bearing and the tests are real.

- 2026-11-04T16:34:13Z F119: config says significance_alpha = 0.05 is "the only significance level this project applies", and it was also written in four other places: the ROC bootstrap bounds as int(0.025 * rounds) and int(0.975 * rounds), the layer prose "at 95 per cent confidence", about.html printing "95% CI", and the design caveat I wrote this morning. All agreed with config by coincidence, so turning alpha to 0.01 restyled one chart and left the headline interval at 95 per cent with three surfaces saying so. All four derive from it now, with confidence_level reported beside ci95 so no surface needs to know what alpha was at build time, and rounds moved to scoring.bootstrap_rounds. Recorded as D-NOB-062 because it widens what alpha governs: it now sets the interval width and therefore whether interpretation reads above chance. How it was missed: the cutoff sweep examined this function and its allowlist carried _bootstrap_interval.rounds with a written reason, so the signature was read and the default correctly waved through, while two percentile literals sat one line below inside the return statement, which F80 had already recorded the sweep cannot see. An allowlist entry is evidence a line was looked at, not that the lines around it were. Suite 831 passing.

- 2026-11-04T16:41:28Z F120: reading the bootstrap for F119 meant reading what consumes it. The matched-control ROC turned its interval into "above chance" if low > 0.5 else "not distinguishable from chance", which reads as exhaustive and is not: an interval entirely below 0.5 separates the classes in the direction opposite to the prediction, so an AUC of 0.15 with interval 0.08 to 0.24 would have been reported as indistinguishable from chance. Spec 4.3 asks for that case by name and D-NOB-024 already reports BINMAN reach window as at or below chance and slightly inverted, so the project knows how to say it while the headline curve could not say it about itself. Three branches now in a named function rather than a conditional expression, since A if cond else B invites reading B as everything-else, with both boundaries strict so an interval touching 0.5 claims nothing. The estimator underneath checked rather than assumed: 1.0, 0.0, 0.5 and 0.875 on known cases. The cutoff sweep caught the new comparison and it is allowed separately from low > 0.5 rather than folded in, on F119 lesson. Suite 840 passing.

- 2026-11-04T16:46:10Z F121: same shape as F120, found by looking for it. check_prediction returns four verdicts, "not yet testable" then WRONG, supported or unclear, and the summary counted two of the three testable ones, so tested could exceed supported + wrong with nothing naming the unaccounted prediction. It adds up today, one and one of two, and would not the first time a prediction landed between its falsification and its supported interval, which is what unclear exists to name. The per-pair lines printed every verdict; the sentence that gets quoted could not. Counted and printed now with an assertion in main that the three add up to the number the sentence opens with, a test holding that against the real campaigns, and a synthetic three-verdict case because the invariant on todays data is satisfied by there being nothing to miss. Suite 846 passing.

- 2026-11-04T16:47:07Z The verdict sweep that produced F119, F120 and F121 is exhausted. Asked of every piece of code that turns a number into a sentence: what does it do with the case it does not mention. compare.py is complete, six computed verdicts including the control identified by gene and checked against a configured tolerance, five conclusion branches covering not concluded, not trustworthy, supported, not supported and mixed, with both margins read from thresholds.toml and an incomplete caveat appended separately. The seed-balance verdict is complete at five branches. Its conclusion does not state how many pairs were unchanged, which is incomplete rather than wrong since the sentence prints no total and the report carries the denominator, so it is left alone rather than widened.

- 2026-11-04T16:55:16Z F122: probed the public app with input it does not expect, unknown ids, encoded traversal, an over-long parameter, a GET on a POST route. No 5xx, no raise, and both structure endpoints refuse a traversal by matching against the campaign records rather than sanitising a path. One inconsistency: /api/pair/<id> 404s an unknown pair while /api/pair/<id>/structures returned 200 with an empty list, asserting the pair exists and produced nothing, which is a state the project separates everywhere else. Existence now judged on results, tier 1 or 2. My first fix used the sibling scores-based check and 404s every pair for the length of a campaign, since scoring runs after it; test_tier2_catalogue writes an empty scores.jsonl for exactly that reason and caught it three times over. My test for the fix was then wrong twice, asserting the wrong check and configuring a bare directory that does not pin. Three wrong attempts at one twelve-line change, each caught immediately. Suite 873 passing.

- 2026-11-04T17:01:44Z F123: spec 4.8 composite is computed twice, in weights.apply for the stored nobble_score and in nobble.js for the live sliders. Checked by running both rather than reading both: qc/composite_harness.mjs loads nobble.js under node with minimal stubs and calls its real composite on the same rows and weights, matching Python to 5e-5, which is Python round to four decimals. What they did not share is coverage. The JavaScript returns components, requested and complete beside every score because, in its own words, a score built from two components should not sit in the same ranked column as one built from four, and RBM39 ranked second that way on a composite that never saw its pose convergence. weights.apply returned a bare float and run.py stored it with the fit provenance and no coverage, so a reader of scores.jsonl or the API or BINMAN-LM sorting on nobble_score would compare a three-component score against a four-component one. Two of seven benchmark pairs are incomplete: RBM39 three of four and CDK12 two. weights.coverage reports it now and run.py stores it as nobble_score_coverage, taking effect when the fit lands. Suite 880 passing.

- 2026-11-04T17:02:49Z Verified spec 4.7 forced veto end to end: Python computes forced from a configured disagreement threshold, campaign.html renders a forced badge with a detail tooltip and offers a "forced poses only" filter, the Delta chart styles and labels them separately, and tier2.py excludes them from the refinement ranking, which is the "never in the headline ranking" clause. My first grep appeared to show no handling in campaign.html and that was head -8 truncating the output to the other file matches: a self-inflicted false signal, and the seventh near-miss this build avoided by checking before writing.

- 2026-11-04T17:10:46Z F124: D-NOB-007 says shared code is widened in place and never forked, and F71 built test_shared_code.py to enforce it for files at the same relative path, with SKIP_PARTS skipping app as each project own. Compared by content instead, twelve files are byte-identical to a peer copy at a different path: nine are vendored libraries the rule does not reach, and three are project code. molstar-bridge.js is 991 lines of BINMAN viewer filed under NOBBLE vendor/, so the directory name keeps every sweep away including mine and the project own, and SKIP_PARTS would have skipped it anyway: the largest shared file in the project, outside the check twice over, and referenced by no test before today. depot.css is BINMAN stylesheet under a different name, which defeats a same-path comparison completely. All three identical today with nothing holding them to it. SHARED_AT_A_DIFFERENT_PATH names them with what to do instead, and three further tests hold the map honest. Verified by divergence: one appended comment line fails the check, restore confirmed by matching md5s. The bridge content is sound, its literals being the standard AlphaFold pLDDT bands and gathered presentation tuning. Suite 883 passing.
