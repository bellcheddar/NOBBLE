# NOBBLE progress

Rewritten after every phase and at least every 30 minutes during long compute.

## Phases

| Phase | State | Detail |
|---|---|---|
| 0 Probe | **complete** | Apple M2 Ultra, 16 performance + 8 efficiency cores, 128 GB unified memory, 60 GPU cores, 507 GB free, MPS on torch 2.10.0. `config/hardware.toml` and `config/tuning.toml` written |
| 1 Curation and manifest | **complete** | All gates pass. Tier A 17, Tier B 15 (frozen), 25,567-peptide library reduced to 220, 11 MSAs cached, manifest emitted with 0 errors |
| 2 Execution | **benchmark complete, campaign queued** | Benchmark queue finished 99/99, exit 0, zero failures across the whole run. The corrected-construct campaign started automatically in tmux `nobble-corrected`. The main campaign is assembled and waiting: `campaigns/campaign_20261104T004632Z`, 158 pairs, 2,360 jobs, 2,360 YAMLs |
| 3 Scoring and validation | **complete** | Every component, the three validation layers and the composite weight fitter are built and running. The fitter and two of the three layers correctly report `not_computed` with their reasons until the Sievers arm supplies matched negatives |
| 4 Application | **complete** | Seven tabs on the Depot system (the seventh is the design arm, DESIGN_ARM.md, which is an addition rather than part of the spec), Mol* wired, BINMAN-LM query head with a deterministic executor. Playwright: 14 captures at two viewports, 0 non-200, 0 console errors, 0 serious axe violations |

## Phase 1 gates: all passing

| Gate | Result |
|---|---|
| All seven benchmark pairs resolve to deposited structures | **pass** (7/7) |
| Degron Scan independently recovers GSPT1 domain II hairpin and IKZF1 ZF2 | **pass** (2/2, scan tip residue exactly matches the deposited degron in both) |
| Every job under 400 tokens, or a declared exception | **pass** (6 constructs, 2 declared exceptions) |
| Queue survives a kill and resumes without duplicating or dropping a job | **pass** (`tests/test_resume.py`, 8 tests). Seven cover the state machine: torn writes, killed mid-flight, repeated restarts, failed jobs. The eighth runs it against the real assembled campaign, 2,360 jobs, with half marked done, one left recorded as running and a torn final line: nothing dropped, nothing re-queued that had finished, the interrupted job re-run. Observed once end to end on the live queue as well. A deliberate forced kill of a production run was still not performed |
| Zero manifest validation errors | **pass** (7 pairs, 105 jobs, 0 errors, 10 warnings, all `smiles_fallback` for dBET57) |
| Tier B set present, at least 10 ligases | **pass** (15 ligases; DCAF8L1, CCNF, ASB8 at ranks 1-3 as spec 3.3 predicts) |

`tests/test_phase1.py`: 9 passed.

## Phase 3 components

| Component | Spec | State |
|---|---|---|
| Delta-ipTM, ipTM-min, seed aggregation | 4.3, 4.5 | working. Reads the receptor-to-peptide pair, not global ipTM (D-NOB-022), with robust companions to the mandated minimum (D-NOB-023) |
| Bridge percentile against the atlas | 4.1 | working. Reuses BINMAN's filter unchanged against 285,996 observed bridges |
| Pose convergence and docking check | 4.4 | working. Receptor-frame superposition verified at 0.23 A on 436 anchor atoms |
| Lysine geometry | 4.2 | working, reported as measurement with `not_validated` status (D-NOB-024) |
| PLIP fingerprint | 4.6 | working, with the CONECT assertion on every structure (D-NOB-025) |
| ProtCID furniture veto | 4.7 | `not_computed: protcid_unavailable` (D-NOB-010) |
| Composite | 4.8 | fitter built and tested against synthetic splits (6 tests). Refuses below 8 labelled pairs; currently `not_fitted` because the panel is all positives |
| Pose recovery | 5.1 | **computed**. Every record carries its own frame quality (anchor atoms and anchor RMSD) |
| Time split | 5.2 | `not_computed`: all seven panel depositions predate the training cutoff, so there is no blind set (F5) |
| Matched-control ROC | 5.3 | `not_computed`: no matched negatives until the Sievers arm runs |

`nobble/score/run.py` is incremental and re-runnable against a live queue.

## Phase 2 in flight

- **Benchmark panel: complete.** 99/99 jobs, exit 0, no failures at any point.
  Measured throughput over 100 timed jobs: median 0.4551 s/token. Throughput
  has since been remeasured on the corrected campaign (0.3991 s/token over a
  different job-size mix), which is what surfaced F45
- **Corrected-construct campaign: complete.** 100/100 jobs. One job was lost
  to a kill of mine, on a healthy job misread as hung (F20); its retry
  succeeded and nothing else was affected
- **The chain: running.** `tools/run_chain.sh` released from `wait_for_gpu` at
  08:35 UTC when the corrected campaign finished. It scored and compared the
  corrected campaign, preflighted the main campaign with `ok: true` on all
  2,360 jobs, and started it. Tier 2, the design scan, the atlas rebuild and
  the deploy follow (D-NOB-039). Each stage is resumable, so a kill anywhere
  is recovered by rerunning the script
- **Main campaign: running.** `campaigns/campaign_20261104T004632Z`, 158 pairs
  (7 benchmark, 120 Sievers, 31 scrambles), 2,360 jobs, 392,400 tokens.
  Measured on its own first jobs at 0.3363 s/token, which projects **36.7
  hours**: inside the 48-hour per-run target and 59 hours clear of the
  96-hour Gate G1 threshold.

  That number had to be fixed to be trusted. `projected_hours` sized a
  campaign by multiplying its job count by a "representative job" taken from
  whichever campaign was measured last. Throughput remeasured on the
  corrected campaign, whose median job is 397 tokens, projected this one,
  whose median job is 124, at 104.3 hours and opened Gate G1 on a run that
  needs 37 (F45). The per-token rate transfers between campaigns; the job
  size does not. It now projects from the campaign's own token total and
  reports which basis it used.

  **Measured in flight at 10:17 UTC**: 71 jobs done, 0.464 s per token
  overall. The 2,289 remaining project to **51.4 hours** of compute, priced
  in the token bands they fall in. Within the budget, so Gate G1 stays
  closed, with 44.6 hours of headroom.

  The 46.8 hours reported here an hour earlier was my own arithmetic at a
  single median rate, and it was low. Seconds per token is not one number:
  on this campaign it runs from 0.211 for 200-400 token jobs to 0.663 for
  800-1600 token jobs, because attention cost does not grow linearly with
  sequence length. One median understates any campaign whose large jobs are
  a minority of the jobs and a majority of the cost, which is this one's
  shape: 2,215 of the 2,289 remaining jobs are under 200 tokens, and the 29
  jobs over 800 carry a tenth of the remaining tokens. `projected_hours`
  now prices each job in its own band, which is what its docstring had
  claimed since F45 (F61). The nine hours between
  assembly and the first result are the chain waiting for the corrected
  campaign to release the GPU, not lost throughput: the queue is at job 69
  of 2,360 and has not re-run anything, which was checked for duplicate job
  ids rather than assumed
- **One pair is held back from publication.** `bench02_BRD4_VHL`'s fifteen
  jobs ran on YAMLs carrying a hydroxyproline on BRD4 Pro379 that the fixed
  modification rule no longer asks for (F47). The queue row says no
  modification; the YAML on disk says HYP; nothing compared the two until
  F59. The atlas build now refuses while any job's YAML disagrees with its
  queue row, so the site stays on the previously published atlas rather
  than showing a figure measured on a residue BRD4 does not have. The chain
  corrects and re-runs the pair between the campaign and the publish. The
  currently running chain was launched before that change and will not do
  it, which the refusal makes safe rather than silent
- **Tier 2**: built, wired and partitioned (D-NOB-032), not yet run. Queued
  behind the main campaign in the chain, because the decile it refines is
  chosen from the ranking that campaign produces
- **Design scan**: assembled (`campaigns/design_20261104T012406Z`, 16 pairs,
  240 jobs), preflighted, queued last. Last on purpose: its own tab says the
  composite is untrustworthy until the Sievers arm runs, so earlier lifts
  would need caveating into uselessness and rerunning

## The design arm

Not part of `BUILD_SPEC.md`. Scoped in `DESIGN_ARM.md`, decided in D-NOB-037
and D-NOB-038, findings in F11.

| Piece | State |
|---|---|
| Generators (alanine scan, saturation, chemistry grouping) | built, 18 tests |
| Design lift, with refusals for mismatched conditions | built |
| Campaign assembler, parent re-run alongside its variants | built, preflight clean |
| Runner (`tools/run_design.sh`): wait, preflight, run, score, profile | built |
| Tab, 31 selectable parents, scan profile chart | built, deployed, chart verified against a synthetic profile |
| A real scan | not run: queued last in the chain |

- `campaigns/benchmark_20261103T192126Z`: 100 YAMLs, queue running in tmux `nobble-bench`
- 5 conditioned jobs dropped for benchmark member 3, which has no measurable
  pocket (6BNB assembly 1 carries no PROTAC). Dropping beats emitting a
  duplicate of the unconstrained arm under a conditioned label
- Throughput, now measured rather than extrapolated: the first figure of
  0.343 s/token came from the smallest job and was flagged at the time as
  optimistic. Over 80 timed jobs the median is **0.4738 s/token** (mean 0.4257,
  range 0.2074 to 0.7335), so the early figure was out by 38% in the direction
  predicted: pairformer cost is superlinear in length and the DCAF15 member is
  1,223 tokens. The campaign sizes itself from the measured number, giving 156
  affordable pairs in the 48-hour budget against the spec's 200-250 estimate.
  `data/throughput.json` is rewritten as the queue progresses
- Jobs per pair is **15**, computed rather than quoted: the spec gives both 10
  and 20 in different sections (D-NOB-019)

## Phase 1 complete

- `nobble/paths.py`: every path and interpreter in one place
- `nobble/curate/binman_store.py`: read-only reader over BINMAN's atlas and the 12
  curated TSVs. Row counts verified against spec 2.1 (285,996 bridges; 5,663
  Sievers zinc fingers; 3,924 MGTbind complexes; 15,502 PROTAC-DB rows)
- `nobble/curate/benchmark.py`: panel resolver, 7/7
- `nobble/curate/structures.py`: reads the seven depositions from BINMAN's
  assembly cache, so pose recovery needs no network
- `nobble/curate/numbering.py`: deposited-to-canonical frame mapping
- `nobble/curate/interpro.py`, `constructs.py`: receptor constructs from InterPro
  boundaries, with measured token counts
- `nobble/curate/degron_gate.py`: the degron recovery gate

## Resolved benchmark panel

| # | Pair | PDB | Ligand CCD | Notes |
|---|---|---|---|---|
| 1 | GSPT1 / CRBN / CC-885 | 5HXB | 85C | Numbering offset 138: see D-NOB-012 |
| 2 | BRD4 BD2 / VHL / MZ1 | 5T35 | 759 | VCB trimer receptor |
| 3 | BRD4 BD1 / CRBN / dBET57 | 6BNB | (PROTAC absent from assembly 1) | |
| 4 | IKZF1 ZF2 / CRBN | 6H0F | Y70 (pomalidomide) | No deposited lenalidomide ternary for IKZF1 |
| 5 | CK1alpha / CRBN / lenalidomide | 5FQD | LVY | |
| 6 | RBM39 RRM2 / DCAF15 / indisulam | 6Q0W | EF6 | |
| 7 | cyclin K / DDB1 / CR-8 | 6TD3 | RC8 | Peptide comes from CDK12: see D-NOB-016 |

## Receptor constructs, measured

| Construct | Residues | Tokens | Verdict |
|---|---|---|---|
| CRBN_CULT | 109 | 154 | within cap |
| VHL_VCB | 370 | 415 | declared exception |
| DCAF15_DDB1_DDA1 | 1,184 | 1,229 | declared exception, 37 per cent over the spec's own estimate (D-NOB-015) |
| DDB1_BPC | 310 | 355 | within cap, no exception needed (D-NOB-013) |
| KEAP1_KELCH | 316 | 361 | within cap |
| FEM1B_ANK | 297 | 342 | within cap (ankyrin, not TPR: D-NOB-014) |

## Phase 4 application

| Tab | State |
|---|---|
| Campaign | ledger with filters, sorting, pin-on-click and browser-side re-weighting |
| Pose | per-seed geometry table and viewer controls. Mol* structure loading still to wire |
| Interactions | PLIP heatmap, canonical fingerprint comparison, CONECT integrity shown |
| Delta | Delta-ipTM against bridge percentile with lasso to pin, distribution panel, matched-control ROC (reports honestly that it is not computable until the Sievers arm runs) |
| Benchmark | seven cards, scored or queued, with colour-coded stats and tooltips |
| About | calibration caveat, the two unvalidated signals with their AUCs, construct budget, data licences |

BINMAN-LM is optional: the head translates a question into a query object and
the executor runs it in Python, so the model never emits a number. With
`BINMAN_LM_URL` unset every tab still works and `/api/ask` reports
`unavailable` rather than guessing.

Run locally: `PYTHONPATH=. python -c "from nobble.app import create_app; create_app().run(port=5055)"`.
QC: `npx node qc/qc.mjs` with the app running.

## What a truncated run keeps

The priority ordering is benchmark (jobs 0-99), Sievers (100-1899),
scrambles (1900-2359), and the Sievers block interleaves its labels at a
constant four not_degraded to one degraded. So the matched-control ROC, the
project's falsifiable test, does not need the whole campaign:

| complete pairs per side | job | share | projected hours |
|---|---|---|---|
| 3 (the configured floor) | 145 | 6.1% | 6.2 |
| 10 | 400 | 16.9% | 11.2 |
| 24 (every degraded pair) | 1495 | 63.3% | 32.8 |

Computable at 6 hours, fully populated on the positive side at 33. The last
37% of the campaign deepens the negative side and runs the scramble control.
Checked rather than asserted, with negative controls, because Gate G1's
reasoning rests on it (F65).

## Next action, once the chain exits

The chain running now (PID tracked in `logs/chain.log`) was launched at
01:02 UTC and bash reads a running script by byte offset, so the corrected
`tools/run_chain.sh` was put in place by rename and the running instance is
still executing the old copy from its open file descriptor. It will not run
the F47 correction, and the atlas build refuses while that correction is
pending, so it will finish having published nothing new.

**Rerun `bash tools/run_chain.sh` once the current one exits.** It is
idempotent: every stage skips what is already done, so it corrects
`bench02_BRD4_VHL`, runs the fifteen jobs that clears, scores, runs tier 2
and the design scan if they have not run, rebuilds the atlas and deploys.
`run_queue.sh` now waits for the GPU itself (F60), so launching it early
blocks rather than competing, but waiting for the old chain to exit avoids
two chains interleaving their later stages.

## Gates open

- **No gate is currently open.** All six are closed.
- **G1 compute: closed, and was briefly reported open in error.** When the
  chain remeasured throughput on the corrected campaign, `projected_hours`
  applied that campaign's 397-token representative job to the main campaign's
  124-token jobs and returned 104.3 hours against the 96-hour threshold. The
  main campaign is measuring 0.3363 s/token on its own jobs, which is 36.7
  hours. The projection, not the campaign, was wrong (F45). Recorded here
  because a Gate reported open stops an unattended build, so a false one is
  as costly as a missed one.
- **G5 Disk**: closed and now actually enforced. The 50 GB floor had sat in
  `thresholds.toml` since Phase 1 with nothing reading it, so the gate
  existed on paper. `runner.disk_gate()` checks it before every job and
  stops the queue rather than filling the volume: 543 GB free, and the
  remaining campaigns need about 7 GB (2.7 MB per job, 2,610 jobs).
- **G3 Deploy**: closed, satisfied and verified, not merely approved.
  `nobble.mdeller.com` serves the app over HTTPS behind its own nginx vhost,
  the certificate is issued to `nobble.mdeller.com` (not the ALPHABETTI
  certificate that was being presented before), it verifies cleanly and runs
  to 2027-02-01, and port 80 returns a 301 to HTTPS. `deploy/deploy.sh`
  re-checks all nine routes on every deploy and refuses to report success
  unless each returns 200.
- **G4 Publish**: closed, granted and used. `github.com/bellcheddar/NOBBLE`
  is public. PROTAC-DB SMILES were removed from the history before the first
  push, and `deploy/build_atlas.py` re-verifies the redaction on every build
  rather than trusting that the first pass held.

## Known degradations

- Degronopedia and ProtCID were never acquired (BINMAN's own Gate G7). The
  ProtCID packing-only veto of spec 4.7 will report `furniture: null` with status
  `not_computed: protcid_unavailable`, never `false`. See D-NOB-010.
