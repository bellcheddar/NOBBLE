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
