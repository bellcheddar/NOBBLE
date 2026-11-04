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
  Final measured throughput over 100 timed jobs: median 0.4551 s/token, giving
  146 affordable pairs in the 48-hour target
- **Corrected-construct campaign**: running in tmux `nobble-corrected`, chained
  automatically behind the benchmark queue (D-NOB-030)
- **The chain**: `tools/run_chain.sh` is armed in tmux `nobble-chain`,
  waiting for the GPU. It runs the corrected comparison, then the main
  campaign, then tier 2, then the design scan (D-NOB-039). Each stage is
  resumable, so a kill anywhere is recovered by rerunning the script
- **Main campaign**: assembled and ready, not yet started.
  `campaigns/campaign_20261104T004632Z`, 158 pairs (7 benchmark, 120 Sievers,
  31 scrambles), 2,360 jobs. Projects to 51.8 hours at the measured rate: over
  the 48-hour per-run target by 3.8, far under the 96-hour Gate G1 threshold,
  so no gate opens and the priority ordering absorbs the overrun
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

## Gates open

- **No gate is currently open.** All six are closed.
- **G3 Deploy**: closed, satisfied and verified, not merely approved.
  `nobble.mdeller.com` serves the app over HTTPS behind its own nginx vhost,
  the certificate is issued to `nobble.mdeller.com` (not the ALPHABETTI
  certificate that was being presented before), it verifies cleanly and runs
  to 2027-02-01, and port 80 returns a 301 to HTTPS. `deploy/deploy.sh`
  re-checks all eight routes on every deploy and refuses to report success
  unless each returns 200.
- **G4 Publish**: closed, granted and used. `github.com/bellcheddar/NOBBLE`
  is public. PROTAC-DB SMILES were removed from the history before the first
  push, and `deploy/build_atlas.py` re-verifies the redaction on every build
  rather than trusting that the first pass held.

## Known degradations

- Degronopedia and ProtCID were never acquired (BINMAN's own Gate G7). The
  ProtCID packing-only veto of spec 4.7 will report `furniture: null` with status
  `not_computed: protcid_unavailable`, never `false`. See D-NOB-010.
