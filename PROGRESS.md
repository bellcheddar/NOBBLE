# NOBBLE progress

Rewritten after every phase and at least every 30 minutes during long compute.

## Phases

| Phase | State | Detail |
|---|---|---|
| 0 Probe | **complete** | Apple M2 Ultra, 16 performance + 8 efficiency cores, 128 GB unified memory, 60 GPU cores, 507 GB free, MPS on torch 2.10.0. `config/hardware.toml` and `config/tuning.toml` written |
| 1 Curation and manifest | **complete** | All gates pass. Tier A 17, Tier B 15 (frozen), 25,567-peptide library reduced to 220, 11 MSAs cached, manifest emitted with 0 errors |
| 2 Execution | **running** | Benchmark queue of 100 jobs in tmux session `nobble-bench`. Smoke test 42.5 s for 124 tokens on MPS; warm rate 31.9 s. Resume verified in practice |
| 3 Scoring and validation | **mostly built** | Metrics, geometry, poses, docking, lysine and PLIP all working and scoring live results. Remaining: composite weight fit and the three validation layers of spec 5, both of which need the full panel |
| 4 Application | **built, QC clean** | Six tabs on the Depot system, reading the campaign live. Playwright: 12 captures at two viewports, 0 non-200, 0 console errors, 0 serious axe violations. Remaining: Mol* wiring in the Pose tab and the BINMAN-LM query head |

## Phase 1 gates: all passing

| Gate | Result |
|---|---|
| All seven benchmark pairs resolve to deposited structures | **pass** (7/7) |
| Degron Scan independently recovers GSPT1 domain II hairpin and IKZF1 ZF2 | **pass** (2/2, scan tip residue exactly matches the deposited degron in both) |
| Every job under 400 tokens, or a declared exception | **pass** (6 constructs, 2 declared exceptions) |
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
| Composite | 4.8 | `null` until weights are fitted on the panel and Sievers set (D-NOB-006) |

`nobble/score/run.py` is incremental and re-runnable against a live queue.

## Phase 2 in flight

- `campaigns/benchmark_20261103T192126Z`: 100 YAMLs, queue running in tmux `nobble-bench`
- 5 conditioned jobs dropped for benchmark member 3, which has no measurable
  pocket (6BNB assembly 1 carries no PROTAC). Dropping beats emitting a
  duplicate of the unconstrained arm under a conditioned label
- First measured throughput: 0.343 s/token, sizing the campaign at 271 pairs
  against the spec's 200-250 estimate. The figure is from the smallest job and
  is optimistic: pairformer cost is superlinear in length, and the DCAF15 member
  is 1,223 tokens. `data/throughput.json` is rewritten as the queue progresses
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

Run locally: `PYTHONPATH=. python -c "from nobble.app import create_app; create_app().run(port=5055)"`.
QC: `npx node qc/qc.mjs` with the app running.

## Gates open

- **G3 Deploy**: open in advance, and not satisfied by DNS alone.
  `nobble.mdeller.com` resolves to the droplet (45.55.102.228) and answers HTTP
  200 on port 80, but with nginx's default welcome page: there is no NOBBLE
  vhost, and the only certificate presented covers `alphabetti.mdeller.com`, so
  HTTPS fails verification. Needs an nginx vhost and a certbot certificate, both
  root actions on the droplet. See D-NOB-011.
- All other gates closed.

## Known degradations

- Degronopedia and ProtCID were never acquired (BINMAN's own Gate G7). The
  ProtCID packing-only veto of spec 4.7 will report `furniture: null` with status
  `not_computed: protcid_unavailable`, never `false`. See D-NOB-010.
