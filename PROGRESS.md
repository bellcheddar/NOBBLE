# NOBBLE progress

Rewritten after every phase and at least every 30 minutes during long compute. Last rewritten 2026-11-07T02:52:00Z.

## Gate G6 answered: the headline is a negative result, and publication is held

**The campaign is complete and unpublished.** 2,360 of 2,360 jobs, scored,
both computable validation layers computed. The atlas build refused for two
days on `bench02_BRD4_VHL`'s stale F47 hydroxyproline, exactly as designed.
The correction has now run and the atlas builds; nobble.mdeller.com still
serves the 100-pair benchmark bundle, now because publication is held
(D-NOB-076) rather than because the build refuses.

**The correction changed no number, because it corrected nothing.** All
fifteen re-run jobs returned ipTM bit-identical to sixteen significant
figures. Boltz caches the featurised input under each job's output directory
and reuses it, so the re-run spent 163 s a job re-folding a cache dated two
days earlier: `processed/structures/*.npz` holds chain P residue 1 as HYP
while the corrected YAML says PRO (F219). The hydroxyproline is still in the
campaign's bench02 poses.

Worse than F47 itself, which every check reported as wrong. This is the same
wrong input with every check reporting it as fixed, because they all read the
YAML. `tools/stale_featurisation.py` now reads what was folded instead, the
build refuses on it, and `tools/rerun_pair.py` removes the cached output so
the next correction takes. The correction has to be run again once the GPU is
free; the chain has already passed that stage, so it waits rather than
competing for the device. Rehearsed without it: `tools/rerun_pair.py` with no
`--apply` now reports that 0 of the 15 YAMLs differ from their reference, so
6 November did correct those, and that all 15 cached featurisations still
disagree, so the cache is the only thing left to clear (F221). The one question F217 left open, whether Boltz
wanted the `modifications` block elsewhere in its schema, is now closed from
the parser source rather than the GPU: it is read from inside the entity dict
as `position` and `ccd` pairs, which is what was emitted, so the cache is the
whole cause (F220).

**The matched-control ROC is a null**: AUC 0.4583, 95 per cent CI 0.3316 to
0.5842, over 24 positives and 96 matched negatives from the Sievers screen,
which the code itself reads as "not distinguishable from chance".

**But the pose-recovery positive control has failed** (F212), so that null
cannot be interpreted. 0 of 65 poses within 3 A, 1.5 per cent within 5 A,
median 17.54 A. The measurement is sound and was checked before it was
believed: receptor anchors superpose at 0.539 to 1.883 A over 424 to 1,240
backbone atoms, and peptide sequence identity is 1.0 on all seven pairs. So
the poses really are 5 to 44 A out, while ternary ipTM reads 0.887 to 0.933.
A Delta-ipTM that fails to separate glue from matched control is
indistinguishable from a Delta-ipTM computed over poses in the wrong place.

Two rungs of the ladder are already read off structures on disk: pocket
conditioning does nothing (14.95 A against 17.92 A median, under 0.5 A per
pair on six of seven), and tier 2 could not test the question at all, because
the decile held no pair with a deposited structure.

### What the gate measured

Marc chose, on 2026-11-06, to refine the seven benchmark pairs and read the
answer off them. Five finished before tier 2 was stopped:

```
pair                         n    tier1    tier2     move  anchor
bench01_GSPT1_CRBN          10    29.14    24.91    -4.98  stable
bench03_BRD4_CRBN            5    20.40    17.40    -2.70  stable
bench04_IKZF1_CRBN          10     5.35     4.96    -0.39  stable
bench05_CSNK1A1_CRBN        10    12.21    12.27    +0.03  stable
bench07_CDK12_DDB1           7    44.92    44.66    -0.25  stable
```

Two pairs move past the 2.0 A `campaign_change_margin_a` and both still land
17 to 25 A from the deposited peptide; the receptor anchor is stable on all
five, so the moves are moves and not a change of frame. **Refinement sharpens
the poses and does not recover them** (F215). More compute is not the remedy.

### What was decided

**Publication is held** (D-NOB-076), and held by the scripts rather than by a
note: `config/publication_hold.toml` is read by `tools/publication_hold.py` as
the first pre-flight step of `deploy/deploy.sh` and again before the chain's
deploy stage, because the chain's last line is a deploy. A missing hold file
reads as held, and releasing it must name the authorising decision. No success
radius was invented to decide it, and a test asserts none appears in
`thresholds.toml`.

Publishing with the failure stated plainly was offered and declined, as was
publishing the ranking and ROC with the pose views stripped out.

### Running now

The D-NOB-069 chain rerun, in tmux `nobble-chain` under `caffeinate -dimsu`,
logging to `logs/chain_rerun_20261106.log`. It carries the F47
`bench02_BRD4_VHL` correction and the Tier B stage, neither of which the
4 November process ever had, and it resumes the stopped tier-2 queue at its
third stage. Its progress is not written here, because it changes as a
consequence of the work and would be stale before the file was saved (F168):
`bash tools/status.sh` reports it.

It ends by consulting the hold and leaving the atlas local.

## Phases

| Phase | State | Detail |
|---|---|---|
| 0 Probe | **complete** | Apple M2 Ultra, 16 performance + 8 efficiency cores, 128 GB unified memory, 60 GPU cores, 535 GB free (`config/hardware.toml` records 507.0, which is that figure in gibibytes under a gigabyte name: the probe divided by 1024**3 while the G5 gate divides by 1e9, fixed in F179, and the file corrects itself at the next probe), MPS on torch 2.10.0. `config/hardware.toml` and `config/tuning.toml` written |
| 1 Curation and manifest | **complete for selection, Tier B execution at Gate G1** | All phase-1 gates pass. Tier A 17, Tier B 15 (frozen, and not paired into any campaign: F134), 25,519-candidate library reduced to 158 selected (`reduction_ratio` 0.0062, and `diverse: 0`: the mandatory benchmark and Sievers members plus their scrambles cost 158 against a budget of 156, so this campaign is calibration only and three of spec 3.4's five peptide sources contribute nothing to it), 11 MSAs cached, manifest emitted with 0 errors |
| 2 Execution | **main campaign complete, chain rerun in flight** | Benchmark queue finished 99/99, exit 0, zero failures across the whole run. The corrected-construct campaign started automatically in tmux `nobble-corrected`. The main campaign finished 2,360 of 2,360 in tmux `nobble-chain`: `campaigns/campaign_20261104T004632Z`, 158 pairs. Tier 2 ran in tmux `nobble-tier2` carrying the seven recovery controls ahead of the decile remainder (D-NOB-075) and was stopped with 89 jobs unrun once G6 was answered (D-NOB-077); 136 results are kept and the chain resumes the same queue. The D-NOB-069 chain rerun now runs in tmux `nobble-chain`, carrying the F47 correction and the Tier B stage. Its progress is not written here, because it changes as a consequence of the work and would be stale before the file was saved (F168): `bash tools/status.sh` reports it |
| 3 Scoring and validation | **complete; the pose-recovery control has failed (F212) and refinement does not fix it (F215)** | Every component, the three validation layers and the composite weight fitter are built and running. The composite is now fitted and the matched-control ROC is computed. Pose recovery is computed and **fails**: 0 of 65 poses within 3 A, median 17.54 A, in verified-correct frames. Tier-2 refinement moves two of five measured pairs past the 2.0 A margin and neither closer than 17 A, so it sharpens the poses without recovering them (F215). Gate G6 is answered: publication is held (D-NOB-076) |
| 4 Application | **complete** | Seven tabs on the Depot system (the seventh is the design arm, DESIGN_ARM.md, which is an addition rather than part of the spec), Mol* wired, BINMAN-LM query head with a deterministic executor. Playwright: 14 captures at two viewports, 0 non-200, 0 console errors, 0 serious axe violations |

## Gate G1 closed: Tier B is assembled and queued

Both halves of it. Spec 3.3 selected fifteen ligandable-unproven ligases and
named no receptor construct for any of them, so the arm was selected,
frozen, gate-passed and unrunnable.

**The constructs.** Marc named a substrate-binding domain for eleven and
excluded four, on 2026-11-05, against the candidate evidence in
`tools/tier_b_candidates.py` (D-NOB-072). The four are KCNC1 and KCND2,
potassium channels that passed spec 3.3's druggability filters without
having a substrate interface, RAG1, whose every ordered domain binds DNA,
and RNF175, which annotates nothing but its RING and its membrane span.
Eleven clears spec 3.3's `min_ligases_for_gate` of 10 by one, and
`tier_b_constructs.report()` now checks that rather than assuming it.

**The compute.** Marc lifted `max_compute_hours` from 96 to 240: his own
machine, free compute, and the figure was an arbitrary spec number. Changed
in `tools/hwprobe.py` as well as `config/tuning.toml`, because the probe
writes that file.

**The arm.** `campaigns/tier_b_20261105T202811Z`: the eleven receptors
against the seven proven glue-degron pairs from the benchmark panel, each
with that degron's composition-matched scramble. 154 pairs, 1,540 jobs, 10
per pair over 5 seeds and two arms, 38.9 hours priced from the real
construct and glue sizes. Preflight passes. Queued in `tools/run_chain.sh`
as stage 4b, after the design scan.

A pair holds a known-working glue and degron together and swaps only the
receptor, so the benchmark panel is a matched positive control that costs no
jobs, and the scramble is an internal negative (D-NOB-073). Conditioning
does not apply: a Tier B receptor has no deposited structure, and the pocket
in the pair it borrows from belongs to a different protein.

Every receptor sequence now has a cached MSA, fetched on 2026-11-05. Without
them the arm would have run single-sequence against a panel predicted with
MSAs, which is not a comparison.

**What the arm can show.** Every pair is expected to fail: these ligases
have no known glue. A hit is a hypothesis, and a uniform absence of hits is
the likely result and still informative, because it says the chemotypes that
work on CRBN and VHL do not transfer.

## Waiting on Marc

Two items, neither blocking anything else, plus a third that is now
answered and kept here for the record. The chain and every other phase
continue.

Publication itself is not waiting on Marc: he held it (D-NOB-076), and it
stays held until pose recovery passes or the headline is re-scoped.

| Item | What is needed |
|---|---|
| **G1 Compute**: Tier B has no pairs | Two things, in order. First the fifteen receptor constructs, because Tier B cannot be assembled without them: `config/tier_b_constructs.toml` is the form and `PYTHONPATH=. python tools/tier_b_candidates.py` now prints each candidate's mean pLDDT and its overlap with the frozen best window, which rules some out on modelling grounds without choosing (F182). KCND2's IPR024587 sits at pLDDT 42 and RAG1's importin-binding region at 59, while CCNF's cyclin boxes run 94 to 97 against a whole-model 71.5. Then the compute decision: a separate campaign, a larger `max_compute_hours`, or a GPU. Measured cost above |
| **G4 Publish**: answered | `Bash(git push:*)` is in `.claude/settings.local.json` as of 2026-11-06, so end-of-phase commits reach the remote without a per-push question (D-NOB-078). For what is still local, `git rev-list --count origin/main..HEAD`: the figure changes with every commit, so a number written here is wrong by the time it is committed, which is how F167's own fix failed its own test (F168). `origin/main` still carries the absolute project paths F128 removed, which a push does not clear from history; `git grep -c /Users/dellboy origin/main -- deploy/atlas` counts them |
| **F132**: static assets and structures uncompressed | `bash deploy/enable_gzip.sh`. A direct ssh to the live vhost is declined to me, so the script is written to be read first. Measured against production: `molstar.js` serves 5,227,830 bytes and `plotly.min.js` 4,558,696, both with no `content-encoding` when gzip is offered. The pages themselves were never the problem, because nginx compresses `text/html` whatever `gzip_types` says, which is a claim F174 got wrong and F189 corrected. The script now also carries `chemical/x-mmcif`, the largest type it can compress: mmCIF compresses 3.5 times, so a pose download drops from 243 KB to 37 and the campaign-scale bundle from 265 MB to 75 |

## Phase 1 gates: all passing

| Gate | Result |
|---|---|
| All seven benchmark pairs resolve to deposited structures | **pass** (7/7) |
| Degron Scan independently recovers GSPT1 domain II hairpin and IKZF1 ZF2 | **pass** (2/2, scan tip residue exactly matches the deposited degron in both) |
| Every job under 400 tokens, or a declared exception | **pass** (6 constructs, 2 declared exceptions) |
| Queue survives a kill and resumes without duplicating or dropping a job | **pass** (`tests/test_resume.py`, 8 tests). Seven cover the state machine: torn writes, killed mid-flight, repeated restarts, failed jobs. The eighth runs it against the real assembled campaign, 2,360 jobs, with half marked done, one left recorded as running and a torn final line: nothing dropped, nothing re-queued that had finished, the interrupted job re-run. Observed once end to end on the live queue as well. A deliberate forced kill of a production run was still not performed |
| Zero manifest validation errors | **pass** (7 pairs, 105 jobs, 0 errors, 10 warnings, all `smiles_fallback` for dBET57) |
| Tier B set present, at least 10 ligases | **pass** (15 ligases; DCAF8L1, CCNF, ASB8 at ranks 1-3 as spec 3.3 predicts). The gate is worded about the manifest and the manifest holds the set. It does not ask whether any Tier B pair was ever run, and none was: see Gate G1 below (F134) |

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
- **Main campaign: running**, 323 of 2,360 at 21:10 UTC on 4 November. The
  benchmark block is behind it and the Sievers arm began at job 100 as
  planned, so the first zinc-bearing jobs have now run: the paths they take
  were verified ahead of them in F82, F83 and F86, and F102 confirmed on a
  completed prediction that the cofactor really is in the binary arm, which
  is what D-NOB-034 requires and what preflight could only check in the YAML.

  Throughput by band, remeasured on 180 timed jobs, 100 from the benchmark
  block and 80 from the Sievers arm: 0.484 s/token under 200 tokens, 0.3501
  in the 200 to 400 band, 0.3658 in the 400 to 800 band and 0.7375 in the
  800 to 1600 band. The 2,175 jobs remaining project to **47.0 hours**,
  inside the 48-hour per-run target and 49 clear of Gate G1's 96-hour
  threshold, so the gate stays closed. The overrun is a scheduling fact the priority
  ordering absorbs rather than a budget problem: the run yields the
  benchmark panel first, then the Sievers split, and loses discovery off
  the tail.

  The arm is much cheaper per job than the block before it. A Sievers binary
  is 136 tokens and runs in 35 seconds, against 1,223 tokens and 915 seconds
  for a DCAF15 ternary, which is why the first 100 jobs took as long as they
  did and why the projection is now dominated by job count rather than by
  the few large constructs.
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
| 3 (the configured floor) | 400 | 16.9% | 11.2 |
| 10 | 1015 | 43.0% | 23.3 |
| 24 (every degraded pair) | 1855 | 78.6% | 39.9 |

Computable at about 11 hours, fully populated on the positive side at 40.
The last 21% of the campaign deepens the negative side and runs the scramble
control. Checked rather than asserted, with negative controls, because Gate
G1's reasoning rests on it (F65).

These figures replace an earlier set that was optimistic by roughly a factor
of two. `matched_control_roc` computes the curve over the Sievers arm alone
and the first count included the seven benchmark pairs, which carry the
label "degraded" and sit at the head of the queue (F73).

## Scoring review, F74 to F90

A day spent reading the scoring code for correctness rather than for a
symptom. Seventeen findings, all mutation-checked, and the published atlas
diffed leaf by leaf afterwards: 11,002 values, two moved, both deliberate.

The largest group was one question asked four times. `isinstance(value,
(int, float))` admits NaN, and NaN is neither greater than nor equal to
anything, so code that treats "not a number" as a number fails silently and
in the direction that flatters the result.

- **F74** the matched-control ROC scored a NaN as a unanimous loss: one
  among three positives takes the AUC from 1.0 to 0.667, towards the null.
- **F76** the same idiom in fourteen places, including the one that directs
  tier 2's refinement budget. One rule now, in `nobble/numeric.py`, with a
  sweep against a fifteenth. A NaN inside `sorted()` leaves the whole list
  unsorted, so a bridge percentile median read 10 where the answer was 70.
- **F77** the composite's clamp turned a NaN into 1.0, the maximum score,
  because `min(1.0, nan)` returns 1.0: an unmeasurable bridge would have
  ranked as the best in the panel. `weights.py` also carried a second
  Mann-Whitney estimator, never hardened when F74 hardened the first.
- **F78** `_rmsd` could return NaN, and `pose_recovery` took best, median
  and worst from a list a NaN leaves unsorted.

No record in any campaign carries a non-finite value, from 22,500 floats
checked, so all four were latent. They are guarded because the failure is
silent, not because it had happened.

Then the chain, the report layer and the published output:

- **F79** `cost_of`'s token arguments, added by F45 and F61, were never
  passed, so the design arm kept the fallback F45 exists to replace. Right
  only by coincidence: remeasured on the corrected campaign the same scan
  projects 11.5 hours against a real 4.4.
- **F81** the PLIP chain-map fallback appended "treat this fingerprint as
  unverified" to `notes` and set status "ok", and `run.py` reads the status
  and never the notes. **F82** then found the four-chain path already
  covered by a real prediction in `smoke_sievers`, correcting my claim that
  it was not.
- **F83** verified Delta-ipTM's chain arithmetic on that prediction before
  the Sievers arm reaches it: 0.952 ternary and 0.856 binary, the
  receptor-to-peptide values. The ion is a zero *target* and an ordinary
  source, so the peptide index is the dangerous one, not the receptor set.
- **F87** the convergence scale was a bare 10.0 inside the expression, the
  same fifth place as F80's timeout multiple: arithmetic.
- **F89** `build_atlas.py` never configured a campaign, so every atlas ever
  published chose its design scan target by the length fallback that a
  previous finding replaced. The site said GSPT1 and the chain assembles
  IKZF1. **F90** then moved the fix from the symptom to the rule.

And the tooling that found them. **F84**: `tools/mutate.py` counted a
skipped mutation as caught, so a sweep with stale anchors reported "5 of 5
caught" and exited zero. That is the tool behind every verification in this
project, and the exact defect it exists to find. It paid for itself within
the hour: the next skip it reported honestly was the one that showed F87's
second half was wrong.

Four false alarms of mine are recorded with the findings, all the same
shape: comparing two numbers without first checking they answer the same
question.

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

**What the rerun gains from today, which the running chain does not have.**
The script it executes is the file on disk, so the rerun picks all of this
up; the stages the running chain spawns as fresh processes pick up the Python
changes already.

- A watchdog armed for the length of the chain, every ten minutes, printing
  only on a non-zero exit (F112). The running chain consults it once, on its
  last line, which is after a stall could matter.
- Tier 2 sized per pair from its own measured tier-1 cost, so the DCAF15
  assembly is not abandoned at six hours on a bound of 7.2 (F100), and its
  confidence read from the structure it scored rather than from directory
  order (F99), which at twenty-five diffusion samples was giving rank 0's
  structure with rank 14's confidence.
- `tools/rerun_pair.py` tested for the first time and writing `state.jsonl`
  by atomic rename, so a kill during the correction cannot leave a partial
  record of which jobs have run (F109).
- The substrate plan deterministic (F107), so the re-assembly cannot pick a
  different CSNK1A1 domain from the one the campaign already used.
- Every stage that runs after the compute tolerating a torn final line
  (F111), so a kill mid-append costs the last job rather than the stage.

**And what the rerun gains from the work after that.** The list above was
written when `rerun_pair.py` had been "tested for the first time", which was
true of its atomic write and not of its correction. The correction did not
work (F145): `_known_good` compared an absolute glob result against the
relative campaign path the chain passes, so the campaign was never excluded
from its own search, "exactly one" was never true, and it returned nothing
for every job on every invocation the chain has made. It then cleared the
state rows anyway, so the fifteen jobs would have re-run on the same
hydroxyproline YAML and the atlas would have gone on refusing (F146).

- **The F47 correction now corrects.** All three spellings of the campaign
  path resolve to one reference, the correction is verified end to end on a
  redirected-root fixture, and it refuses rather than clearing results for a
  job whose input it could not verify. It also refuses a queue whose YAML
  paths point outside the campaign named on the command line (F144).
- **Tier 2 is priced against Gate G1 before it runs** (F135). The decile
  costs 29 to 219 hours against what is left of the budget, so
  `tier2.run` reduces it to the affordable prefix of the ranking, and
  `tools/tier2.sh` stops on exit 3 rather than refining nothing. Five of
  fifteen pairs fit at the time of writing.
- **The refined poses are readable** (F137). Tier 2's scores were published
  and read by nothing; the pose tab now shows the quantities whose shape
  survives a change of sample count and names the ones it withholds.
- **The design scan's profile follows the parent it scanned** (F147), not
  the one the report ranks first. Those are already apart, so the scan would
  have run its 240 jobs and shown no profile at all.
- **The deploy refuses a droplet that is not serving what was shipped**
  (F140). Every route answering 200 says the app works, not that it is this
  version.

**And what the rerun gains from the guards added after that.** These matter
because every one of them sits on the path between the queue finishing and
the atlas being published, and none of them had ever run.

- **The refresh can no longer say it refreshed when it did not** (F194). It
  piped the score and atlas steps into `tail`, which makes `$?` tail's, so a
  refused atlas build printed its refusal and the script then printed
  "=== refreshed. Deploy separately ===". That is exactly what the chain
  running now will do, since `build_atlas.py` returns 1 while the F47
  correction is pending: it would have logged a successful refresh after
  thirty-six hours of queue. Score and atlas gate now; throughput warns,
  because it feeds a panel and blocking a valid campaign over a timing
  summary is the wrong trade.
- **Tier 2 refines the queue this selection wrote, or nothing** (F193). It
  keyed on exit 3 alone, and exit 0 covers four outcomes of which only one
  writes a queue. Worse, the queue persisted between runs:
  `benchmark_20261103T192126Z/queue_tier2.jsonl` held ten jobs for
  `bench02_BRD4_VHL` from 3 November, so a refusal would have spent GPU hours
  on a days-old selection and logged it as a fresh decile. `run()` clears any
  previous queue before selecting and the selector prints `TIER2_QUEUE=`,
  which the shell reads instead of guessing.
- **Every runner can report failure** (F195). Four could not, one of them
  because F190 fixed its log line and not its exit status.
- **The deploy verifies every parameterised route** (F196). It checked nine
  fixed paths while `/crystal/<id>.cif` returned 500 for every pair, which
  is why the pose page's crystal overlay had never worked in production.
- **The campaign scale is no longer untested** (F174, F191, F202). The app
  was measured against a 158-pair atlas with 2,255 results rows: the landing
  page came down from 3,289 KB, a dead Tier facet was found and fixed, and a
  deliberate 404 that crashed the pose page was guarded.

**What to check when it finishes.** `bash tools/status.sh` covers most of
it; the five lines worth reading are the stale-input count reaching zero,
the atlas reporting in step, the matched-control ROC moving from
`not_computed` to a verdict, `tools/check_prediction.py` accounting for all
three of its testable outcomes, and the `G1 refine` line, which is new: it
reports what refinement costs against what is left of the budget and how
many pairs survive automatic reduction (F143). The ROC's verdict now has three branches
rather than two (F120), so an inverted result will say so rather than
reading as indistinguishable from chance.

## Gates open

- **G1 Compute is open, on Tier B.** Spec 3.3 says Tier B is in the first
  campaign and not to defer it. It is selected, frozen and gate-passed, and
  no Tier B pair exists in any campaign. After automatic scope reduction the
  smallest design that can answer a question about "any known glue
  chemotype" costs 16.5 hours against 96 `max_compute_hours` with 22.9 spent
  and the main campaign still running. See the section above and F134. The
  other five gates are closed.

  The mechanism for closing it is in place and the judgement is not:
  `config/tier_b_constructs.toml` ships empty with the 59 InterPro
  candidates that fit the token cap listed per ligase, and
  `nobble/curate/tier_b_constructs.py` validates whatever is filled in and
  reports blocked until every gene has an entry (D-NOB-068). So the gate
  closes on fifteen lines of config, not on code.

  This cell used to say "No gate is currently open. All six are closed",
  which stayed true until F134 and then contradicted the section above it
  for as long as nobody read both (F158). The bullet below it then said G1
  was closed, which F158's own test did not catch because it compared a
  blanket claim against named gates and never two bullets about one gate
  (F165).
- **G1 compute, history: the false open of 2026-11-04.** Not a statement
  of the current state, which is the bullet above. When the
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
  re-checks all nine routes on every deploy, plus one URL per
  parameterised route built from the bundle being shipped (F196), and
  refuses to report success
  unless each returns 200.
- **G4 Publish**: closed, granted and used. `github.com/bellcheddar/NOBBLE`
  is public. PROTAC-DB SMILES were removed from the history before the first
  push, and `deploy/build_atlas.py` re-verifies the redaction on every build
  rather than trusting that the first pass held.

## Known degradations

- Degronopedia and ProtCID were never acquired (BINMAN's own Gate G7). The
  ProtCID packing-only veto of spec 4.7 will report `furniture: null` with status
  `not_computed: protcid_unavailable`, never `false`. See D-NOB-010.

## Review F98 to F103, while the campaign runs

Six entries, of which two are fixes, one is a correction to code committed an
hour earlier, and three are verifications that found nothing wrong. The
verifications are recorded because the alternative is rediscovering each as a
hypothesis.

**F98, verified.** D-NOB-035 refuses the Sievers fingers an MSA on the
grounds that alignment depth would correlate with the ROC's label. Nobody had
checked the arm against that description. All three premises hold in the
assembled queue: 24 degraded pairs from 24 distinct genes, 96 controls from
86, both median length 23, and composition matched within two percentage
points on every class. No change made.

**F99, fixed.** Tier 2 has never run. Its Boltz flags are valid, but
`_read_outputs` asked for the structure by rank and the confidence by
directory order, which agree at one diffusion sample and not at twenty-five:
replaying the old code on a fresh 25-sample directory gave structure rank 0
with confidence rank 14. All ten tier-2 jobs would have differenced ipTMs
belonging to poses nobody scored. The confidence is now derived from the
chosen structure's filename. The replay also caught an unpadded-rank sort
picking `_model_10` over `_model_3`, in my replacement as well as the
original.

**F100, fixed.** The tier-2 timeout was a global cap times a guessed multiple
of 4, per attempt, with one retry. BoltzMaker's 146,761 recorded runs all
have null recycling and sampling settings, so no measurement of the scaling
exists anywhere; it is bounded from config instead. Six of seven measured
pairs have 4.6 to 10 times the headroom they need and
`bench06_RBM39_DCAF15` has 0.83, because the DCAF15 assembly is 1,223 tokens
by construction. Each refinement now carries a budget sized from its own
pair's measured tier-1 cost, and the budget is per job rather than per
attempt. D-NOB-060 records the retry trade-off.

**F101, fixed, and it was mine.** F97's drift check excluded `throughput` and
not the values computed from it. Thirteen jobs later it reported 63 drifted
values, all design preview costs, and printed six with "and 57 more", so a
real difference would have been in the 57. Drift now returns two categories.

**F102, noted.** Boltz reports `ligand_iptm` for whichever het group is in
the job, so on a Sievers pair it is the structural zinc: 0.9946 on a binary
job containing no glue at all. Nothing reads it and it is not published, so
the field stays with a comment and a test that fails if anything starts
reading it.

**F103, fixed.** The live median pose RMSD of 17.14 angstrom is either Gate
G6 or a measurement bug. Neither: the receptor anchors at 1.751 angstrom,
all seven reference chain pairs are genuine interfaces at 1.84 to 2.80
angstrom minimum separation, and residue identity matches in all seven.
F6 had already diagnosed the cause and the benchmark page already shows the
domain comparison beside it. What was missing is that nothing asserted the
correspondence, on the layer that decides whether the positive controls
work. It is asserted now, with a control that shifts the frame by fifty
residues, and the floor is in config because my first version used exact
equality and refused CDK12 over 293 of 294 identical residues.

Suite 707 passing, 2 skipped, both conditional on a campaign running and on
tier 2 not yet being selected.

## The CSNK1A1 domain question, answered

PROGRESS and F93 both listed this as open: whether the 269 residues the
corrected campaign submitted or the 219 the plan specified is the correct
CSNK1A1 domain. It is answered, and it was a code defect rather than a
judgement about the kinase (F107, D-NOB-061).

The plan's boundary came from `domains[0]` of an unsorted list in InterPro's
response order, so it depended on how the API had ordered its records. The
library manifest records IPR000719 and the same call today returns PF00069
first.

IPR000719 17-285 is correct. CDD gives 16-281, SMART 17-283 and the PROSITE
profile 17-285 for the same domain; PF00069's 17-235 is the lone outlier. And
5FQD chain C resolves residues 10 to 303 continuously with no unmodelled
gaps, so the 50 residues PF00069 drops are ordered structure rather than a
disordered tail.

The list is ordered now. One of seven substrate constructs moves, CSNK1A1 to
269, which is what the campaign already ran, so the superseded-substrate
caveat comes off the published conclusion instead of being reworded. The
running main campaign submits 15-mers for its benchmark pairs and is
unaffected.

Remaining open items are unchanged: `tools/rerun_pair.py bench02_BRD4_VHL`
when the GPU frees, rerunning `tools/run_chain.sh` once the current chain
exits, and removing the `KNOWN_DRIFT` entry in
`tests/test_cross_campaign_reproducibility.py` when the F47 correction runs.

## Review F104 to F110

Seven more while the campaign runs. The pattern that produced most of them is
the same one: a value computed in one place and read by another under a
different name, order or assumption.

**F104, fixed.** The throughput note read "Measured on the benchmark panel"
as an unconditional literal, true for 100 jobs and false from job 100. It
counts the arms now. And the weight fit was silent about `delta_iptm` being a
minimum over ten ternary jobs against five binary ones; the ROC is unaffected
and already refuses on uneven counts, and the measured effect is 0.0014
against a delta of 0.179, so the fit reports its seed-shape composition
rather than refusing.

**F105, fixed.** The design page said the composite is not validated in three
places and derived it in none: a field reading a path that has never existed,
a Python literal, and a template that checked the field and then rendered its
own sentence. It would have gone on saying so after the Sievers arm
validated it.

**F106, fixed.** Five components under two sets of names. The JavaScript
resolved the one mismatch and the Jinja beside it did not, so the right
answer was the one that ran second. One map in `data.py` now, with three
tests holding the invariant rather than the instance.

**F107, fixed, and it closes an open question.** Which CSNK1A1 domain is
correct was listed here as unanswered. It was a defect: the substrate
construct came from `domains[0]` of a list in InterPro's response order.
IPR000719 17-285 is right, corroborated by CDD, SMART and PROSITE and by
5FQD chain C resolving 10 to 303 with no gaps. One of seven constructs moves,
to the 269 residues the campaign already ran, so the superseded-substrate
caveat comes off the published conclusion.

**F108, fixed.** The same defect on the receptor side, inside the function
whose docstring describes F41 having fixed it: an occurrence "counted from the
N-terminus" indexed the response list. Latent, because the two orders agree
for FEM1B today.

**F109, fixed.** `tools/rerun_pair.py --apply`, the pending F47 correction,
had no test and rewrote a live campaign's `state.jsonl` in place. Ten tests
and an atomic rename.

**F110, fixed.** Three more caches written non-atomically. The sequence cache
is the dangerous one: plain text, so a truncation is still a valid-looking
protein with no parse step to fail at. All four writes go through
`paths.write_atomic` now.

Suite 779 passing. Atlas rebuilt and deployed three times today; the live
site carries the corrected design caveat and the conclusion without the
CSNK1A1 caveat, nine routes 200.

## Review F111 to F116

**F111, fixed.** Seven readers of append-only files would have raised on a
torn final line, where the runner's own `state.jsonl` reader has always
tolerated one. Between them they are every stage that runs after the compute.
One shared `paths.read_jsonl`, with the six queue and manifest readers left
strict on purpose.

**F112, fixed.** The stall detector built after F20 was reachable only from
`status.sh`, which the chain calls on its last line, so it spoke once when
the answer could no longer matter. Armed in the chain now, keyed on its exit
code, verified read-only first, and replaced by rename because the chain is
running.

**F113, fixed, and it was mine.** F100 and F107 were written under decision
ids that already existed, twice over, because I inferred the highest from a
grep that could not see past 039. They are D-NOB-060 and D-NOB-061 now, and
`tests/test_decision_ids.py` holds that no number is used twice and every
citation resolves.

**F114, pinned.** The README's three headline numbers come out of the
function F103 had just changed. Recomputed: 29.221 to 1.171, 19.235 to 1.711,
and the IKZF1 control 5.357 in both campaigns, so 0.000 between them. Every
figure holds, and nothing would have said so if it had not.

**F115, verified.** A non-finite dSASA would be reported as bridge percentile
0.0 rather than refused, on the primary signal. Unreachable, because BINMAN's
bridging criterion rejects a NaN before it can get there. Pinned, because
that line is in another repository and the equivalent rewrite accepts NaN.

**F116, fixed.** Spec section 4 read against the code, which nobody had done.
One clause failed, in the headline view: the Delta scatter drew a pair with no
measurable bridge at percentile 0 and read the position back as a number.
CDK12 is that pair. It now sits in a band below the axis labelled "none".

Suite 820 passing. Atlas rebuilt and deployed four times today, browser QC
clean at both viewports with no console errors, and the live Delta chart
confirmed drawing CDK12 in the band.

Six concerns this session turned out to be unreachable or already decided and
were recorded rather than acted on: D-NOB-035's premise, pose recovery's
measurement, the correlation's caveats, the LM's no-arithmetic contract, Gate
G1's wiring and the bridge percentile's NaN path.

## F117, F118 and the end-to-end re-run

**F117, fixed.** The licensing check ran in one direction. `build_atlas`
verifies no PROTAC-DB chemistry reaches the bundle; nothing verified that
every SMILES which is published has a source permitted to be. Seven ligand
records read individually: six `deposited_ternary` and published, one dBET57
`protacdb` and withheld, UbiBrowser and BioLiP2 present only as availability
booleans. Four tests hold it in both directions now.

**F118, audited clean.** Spec sections 2 and 3 read against the code, which
completes the spec: F52 did section 5, F116 did section 4, and sections 1 and
2's remaining clauses are covered by tests that already existed. 2.3's
"fail loudly" is covered from two sides and `stale_inputs` is symmetric in
all four cases, checked rather than assumed. 3.4 records its reduction ratio
and clustering parameters, which explained the empty ESM-2 cache: `diverse`
is 0 because the mandatory sources alone exceed the measured budget, so
nothing optional was ever embedded.

**The chain re-run.** Eighteen modules changed today, and the suite does not
run the chain, which is how F96 was found. All ten non-GPU stages run clean:
preflight, scoring, the three validation layers, compare, the design report,
tier-2 selection, the atlas build, the drift check, provenance and
check_prediction. The GPU stages are being exercised by the campaign itself.

Suite 825 passing.

## Review F119 to F123

One question produced four of these: what does this code do with the case it
does not mention.

**F119, fixed.** `significance_alpha` was in config and in four other places,
agreeing by coincidence: the ROC bootstrap's percentile literals, the layer's
prose, `about.html`, and a caveat I wrote this morning. Turning alpha down
restyled one chart and left the headline interval at 95 per cent. All four
derive from it now, recorded as D-NOB-062 because it widens what alpha
governs. The cutoff sweep had examined that function and allowed its `rounds`
default by name, one line above two literals it cannot see.

**F120, fixed.** The ROC's verdict had two branches for three outcomes. An
interval entirely below 0.5 is an inverted result, not an absent one, and
spec 4.3 asks for that case by name.

**F121, fixed.** The prediction scorer counted two of its three testable
verdicts, so `tested` could exceed supported plus wrong with nothing naming
the gap.

**F122, fixed.** `/api/pair/<id>` 404ed an unknown pair and
`/api/pair/<id>/structures` returned 200 with an empty list. My first fix
used the scores-based check and would have 404ed every pair for the length of
a campaign; the existing tier-2 tests caught it in a minute.

**F123, fixed.** The composite is computed in Python and in the browser. They
agree, verified by running both under node rather than reading them. What
they did not share is coverage: the page marks a score built from three
components and the stored record did not, and two of the seven benchmark
pairs are incomplete.

Also audited clean: spec 4.7's forced veto is marked with a badge,
filterable, and excluded from the tier-2 ranking; `compare.py` and the
seed-balance verdict are complete; the app returns no 5xx on unknown ids,
encoded traversal, over-long parameters or a GET on a POST route.

Suite 880 passing. Ten of today's fixes are mutation-verified.

## The push is pending your decision

`origin/main` is **150 commits behind** the local branch. PROGRESS records
G4 as "closed, granted and used", so I attempted the push; the harness denied
it as an out-of-place publication, and that is the right place for the
decision to sit rather than somewhere I route around.

**Why it is worth doing rather than leaving.** F128 found the build machine's
absolute paths in the published bundle, 307 of them across four fields, and
`origin/main` already carries 100 of those in `deploy/atlas/results.jsonl`.
The fix is in the local commits. Until they are pushed, the public tree keeps
the paths and the corrected bundle exists only here and on the droplet, which
was redeployed and now serves none.

    git push origin main

**One thing a push does not fix.** The paths stay in the repository's history
even after the current tree is clean, because they were committed. Removing
them needs a history rewrite, which is destructive to a published repository
and not something to do without saying so first. The exposure is a home
directory name rather than a credential: the credential scan is clean, the
deploy reads its four settings from the environment with `${VAR:?}`, and no
key, `.env`, PEM block or address is tracked anywhere.

## Review F124 to F131

Four of these came from one question asked of the project's own checks: what
does this check not look at. None of the four gaps had cost anything yet, and
all four boundaries had been drawn with a tool one notch too blunt.

**F124.** `test_shared_code` compares files at the same relative path and
skips `app`. By content, twelve files are byte-identical to a peer's at a
different path: nine vendored libraries the rule does not reach, and three
that are project code. The largest is `molstar-bridge.js`, 991 lines of
BINMAN's viewer under NOBBLE's `vendor/`, where the directory name keeps
every sweep away. `depot.css` is BINMAN's stylesheet renamed, which defeats a
same-path comparison outright. Named now, with the remedy: widen BINMAN's
copy.

**F125.** Every cutoff scan walked `nobble/`. `tools/`, `deploy/` and `qc/`
hold preflight, the atlas build and the prediction scorer. The only float
cutoffs there are `check_prediction`'s four, which are the one case where a
literal is required: a prediction's thresholds are part of the prediction.

**F126.** The house-style check omitted `.js` to keep the minified libraries
out, which also omitted the project's own 343-line `nobble.js`.

**F127.** `test_numeric_rule` stops at the package while `build_atlas`
publishes scipy correlations. Python writes `NaN` and `JSON.parse` rejects
it, so one non-finite number gives no page rather than a wrong figure. Every
published file and API response is strict-parsed now.

**F128, the only one that had already cost something.** The published bundle
carried the build machine's absolute paths, 307 across four fields, and
`origin/main` still does. F105's own leak test globbed `*.json` while the
paths were mostly in `.jsonl`.

**F129.** The same glob in two more tests written the same day. Fixed with
one definition in `tests/conftest.py` rather than three corrected globs, and
widening it turned out to be a parsing change: a `.jsonl` file is one
document per line.

**F130.** A NaN is truthy, so `if row.get("seconds")` admits one, and the
numeric sweep looks for the type check rather than the truthy guard. Two
modules filtered measured durations that way before taking a median by index.

**F131.** Two of my own tests rewrote `data/throughput.json`, which the app
reads. One put the benchmark's measurement where the running campaign's
belongs. Caught by `tools/mutate.py`'s protected-file list rather than by the
suite.

**The chain re-run.** Eight modules changed since the last end-to-end check,
so all ten non-GPU stages were run again: preflight, scoring, the three
validation layers, compare, the design report, tier-2 selection, the atlas
build, drift, provenance and the prediction scorer. All clean, and
`check_prediction` now accounts for all three of its testable verdicts.

**This session, F132 onwards.** Written up in FINDINGS.md; the count and
the highest number move with every finding, so they are not written here
(F168). `grep -c '^## F' FINDINGS.md` for the total.

Six themes.

*Specified and never run.* Tier B is selected, frozen and gate-passed and has
no pairs in any campaign, though spec 3.3 says not to defer it: Gate G1 is
open on it and the cost is measured above. Its ligand set, `glue_recall_set`,
selected a size bucket of 7,676 CCDs and returned fragments; it is now
compounds observed bridging a triaged ligase, 121 chemotypes, with all five
curated glues retained.

*Priced on one side only.* Refinement was never compared to
`max_compute_hours`: a per-job timeout bounds one job and the decile is 150
of them. `nobble/execute/budget.py` prices it as a range that collapses to a
measured factor once one refinement has run, and `tier2.run` reduces the
decile to what fits. The status page reported only the tier-1 half of the
gate and now reports both, with what survives reduction.

*Verification against the wrong subject.* A browser QC run reported fourteen
clean pages against a server started hours earlier. `/healthz` now reports a
source fingerprint, `qc.mjs` refuses a server that is not the working tree,
and `deploy.sh` refuses a droplet that is not serving what was shipped. Every
page answering 200 says the app works, not that it is this version.

*Published and read by nothing.* Tier 2's scores were in the atlas and no
page read them; the pose tab now shows the quantities whose shape survives a
change of sample count and names those it withholds. The design scan's
profile was computed for the parent the report ranks first rather than the
one the campaign scanned, and those are already apart. And the F47
correction, which sits on the publish path, corrected nothing on every
invocation the chain has made: an absolute glob result compared against the
relative path the chain passes.

*States nothing had been rendered in.* Browser QC had only ever seen the
benchmark campaign, where the headline panels are empty. Rendered with a
computed ROC the Delta tab was over the copy budget and its verdict was on
the About tab rather than beside its curve; rendered with a scored scan the
design tab named one peptide above another's profile. Both were states the
campaign exists to reach.

*My own work from the same day.* Seven of the nine revisions recorded in
F164 are of fixes written earlier in this session, and two review passes over
that code found a gate pricing an unmeasured campaign at zero and a deploy
check aborting on a traceback. Four checks turned out narrower than their
names, three documents quoted figures that move with the work, and twice a
commit went in on red because a shell `&&` bound to an `echo`. The rate is
recorded rather than tidied away, because it is the argument for the review
passes rather than against them.

Also: CLAUDE.md's copy budget was never measured and `/pose` had drifted to
49 words of presentation provenance; `qc/copy_budget.mjs` measures it inside
browser QC now. BINMAN-LM's Head C reported the genes the campaign *has*
under the name `missing`. The mutation harness could not tell the runner's
appends from a rewrite, so its own test failed intermittently.

Verified and left alone: the matched-control ROC computes on a realistic
fixture at AUC 0.80 with the benchmark pairs correctly excluded; the
composite fitter fits 158 labelled pairs at objective 0.923 with its
in-sample caveat; spec 1.3's MSA policy is implemented exactly, receptors
referencing cached `.a3m` files and the peptide chain `msa: empty`; the
design lift path scores 15 of 15 positions; the publish path serves refined
poses from a scratch-built atlas, all ten URLs at 200.

**Suite green**, which is what `pytest tests/ -q` says; its size is
`pytest tests/ -q --collect-only | tail -1` and changes whenever a test
is added, so it is not written here (F168). Browser QC clean on a named build:
fourteen pages, 0 non-200, copy budget within, 0 console errors, 0 serious
axe violations.

**Main campaign in flight at 650 of 2,360**, 14.97 hours spent on this
campaign and 28.1 across all three, measured from the manifests rather
than estimated. Around 36 hours remain at the observed rate.

**The running chain will not publish on its own, and that is handled.** It
is commit `2b0dc27`, established by inode rather than inferred: the shell
holds a 5,400-byte copy while the file on disk is 8,812, with its offset at
end of file, so the in-place edits never reached it. That version has no F47
correction step, `stale_inputs` still reports fifteen `bench02_BRD4_VHL`
jobs run on a YAML the fixed rule no longer emits, and `build_atlas.py`
refuses while that is true. The decision is to let it finish and then rerun
`bash tools/run_chain.sh`, which corrects those fifteen, publishes, refines
and deploys (D-NOB-069). Every stage is resumable, so the second run's queue
pass costs minutes.

**Deployed twice today, and the second deploy closed two defects that were
live.** `nobble.mdeller.com` serves `7fbe332a3de6083a`, the tree that was
shipped, verified by the droplet reporting its own fingerprint. Thirteen
routes answer 200, the nine fixed ones plus one URL per parameterised route
built from the bundle: that last part is new, and it exists because
`/crystal/<id>.cif` returned 500 for every pair while the nine fixed paths
all passed (F196). The crystal overlay on the pose page works now, and the
pair table's Tier facet offers the arms the data holds rather than `A` and
`B`, which matched nothing (F191). Both were found by asking the running
site, and both were confirmed there afterwards.

**The suite's assertions were audited, not just counted.**
`tools/vacuous_tests.py` traces the suite and reports which assertions never
execute: 2,379 of 2,392 run, and the thirteen that do not are deliberate
skips or data-dependent branches, one of them carrying a comment written for
that sweep. It also caught a test of mine that passed by looping over an
empty glob, twenty minutes after I wrote it.

**The spec's own open list is down to one item.** BUILD_SPEC.md section 9
asked Marc four questions and three were answerable from the system: the
Studio is an M2 Ultra with 128 GB probed into `config/hardware.toml`, Boltz
is 2.2.1 with `--no_kernels` because the optional kernels are a CUDA path MPS
cannot use, and `nobble.mdeller.com` is live on its own vhost rather than a
sub-route. Closed in D-NOB-070. What remains is item 3, whether the Tier B
exploratory arm publishes as a ranked list or an abstention-heavy one, which
is a presentation judgement that arrives with the construct choices at G1 and
blocks nothing.

**The publish path is measured and the correction is ready.** The atlas
build is four seconds for 100 structures, so about two minutes at 2,360, and
scoring is ten minutes; neither is hiding behind the queue. The F47
correction, which the atlas build refuses to publish without, resolves a
known-good reference for all fifteen jobs, and the reference carries no
`modifications` block while the live YAML carries `ccd: HYP` (F178). The
live site answers 200 and still serves the benchmark atlas, on a build
predating `source_fingerprint` in `/healthz`, which the chain's last stage
replaces.

**Both halves of G1 are closed, checked rather than assumed.** Tier 1
projects to 52.6 hours against a 96-hour budget, with 28.32 hours spent over
861 jobs across all campaigns. Tier 2 has never run, so its cost is bounded
rather than measured: 29.24 to 219.29 hours for 140 jobs over a decile-sized
15 pairs, judged on the upper bound against 67.68 hours remaining, and
automatic scope reduction takes it to the 5 pairs that fit. That is G1
behaving as specified rather than a gate to raise, which is the answer I
wanted before the chain reaches stage 3.

**The post-compute pipeline is about ten minutes, measured.** A full rescore
of the benchmark campaign is 25.6 s for 7 pairs over 100 jobs, which puts
158 pairs over 2,360 jobs at roughly ten minutes. The rescore was also
byte-identical in size to the file it replaced, which is the idempotence the
pipeline claims. So nothing long is waiting behind the queue except tier 2
and the design scan, both of which are compute rather than bookkeeping.

**The app has now been measured at campaign scale** rather than on the
100-job benchmark atlas it had only ever served. A 158-pair atlas, the
shape this campaign will produce, put 3,289 KB of HTML on the landing
page, 99 per cent of it in four keys neither page reads. Trimmed to
514 KB, 18 KB gzipped (F174). Memory holds at 84 MB for the whole
atlas and the projected published bundle is 265 MB of structures, both
comfortable on the droplet.

## The interface survey is finished

Every state the app can be in has now been rendered with the data that
reaches it, which is F203's method and the one that produced most of this
session's findings. The two that were left are closed.

**The weights panel with a fit** (F205). `weights.json` has reported
`fitted: false` on every campaign the project has run, so the fitted branch
had never been on screen. Fitting on the Sievers fixture selected two of five
components and the other three kept their hand-set defaults, which put the
ledger's composite column at 0.6578 for IKZF1 against the 0.6189 the pipeline
had stored, under the panel's own sentence saying the weights were fitted and
never by hand. A component the fit left out now starts at zero on both sides
of the page.

**The design tab with a completed scan** (F206). No design campaign has run.
Rendering the scan put fifteen measured lifts, three lost bridges and the
per-position profile on screen, all correct, inside a panel headed "Planned
scan" and footed with a projection of the hours the scan had already spent.
Three states now, computed in the route.

Both were one campaign away from being the first thing read: the fit needs
the Sievers arm and the scan needs the design arm, and each would have come
up wrong the moment it arrived. Neither was reachable on the live site, which
is why nothing caught them and why rendering the unreachable states was worth
the time.

## Next action, once the chain exits (unchanged)

`bash tools/run_chain.sh`, per D-NOB-069, which carries the
`tools/rerun_pair.py bench02_BRD4_VHL --campaign <campaign> --apply`
correction inside it. The chain is at 820 of 2,360 jobs. 496 GiB free, so
G5 is not near. The stall watchdog has reported nothing.

## Tier 2 has now been rehearsed, without the GPU

Tier 2 had never run, and it runs unattended when the chain exits, wrapped in
`|| true`. So a defect in it would have cost the refinement silently at
whatever hour the chain finished. Rehearsed instead, by relabelling real
benchmark outputs as tier-2 results against the benchmark's own
`queue_tier2.jsonl`, which exercises the real mmCIF rather than a fixture and
needs no GPU.

It works. `nobble.score.run --tier 2` writes `scores_tier2.jsonl` and leaves
`scores.jsonl` and `weights.json` byte-identical, which is the claim
`tools/tier2.sh` makes in its own comments. Identical poses through both
tiers return identical numbers, so the tier-2 path differs only in which
files it reads and writes. `build_atlas` publishes both tier-2 files and the
ten refined structures, 110 in all, with the licensing redaction check
passing. The pose API serves the refinement from the published bundle with
four labelled rows, and a refined mmCIF fetches at 200.

One thing that is worth stating plainly, because it is easy to read as a
fault and is not. **Tier 2 produces no Delta-ipTM and no composite.** The
selector refines ternary arms only, so there is no tier-2 binary minimum to
subtract, and `Delta-ipTM` comes out null along with the nine other
minimum-over-seeds quantities. That is correct and deliberate: a 25-sample
ternary minimum against a 1-sample binary one is the downward bias
`tier_files` warns about, and the panel withholds all ten with the reason on
screen. What tier 2 delivers is better coordinates plus the four quantities
whose shape survives a change of sample count, bridge percentile among them.

**Still never run:** the design scan (`tools/run_design.sh`). Its analysis
half is exercised by F206's fixture, which computes lifts and the profile
through the real `nobble/design/lift.py`. The inference half is not, and
cannot be without the GPU.
