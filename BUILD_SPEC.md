# NOBBLE

**N**eosubstrate and **O**ligopeptide **B**inder **B**enchmarking for **L**igase **E**ngagement

Four-phase unattended build spec. Version 0.1, 2026-11-03.

Author: Marc C. Deller. Target machine: Apple Studio (MPS). Execution model: Claude Code, unattended, four sequential phases with gated acceptance criteria.

---

## 0. What NOBBLE is

NOBBLE generates and scores peptide poses against curated targeted-protein-degradation (TPD) machinery using Boltz-2 ternary co-folding, and asks one primary question of every pair:

> Does the presence of the glue or degrader change the predicted interface, and does that change separate experimentally degraded substrates from experimentally non-degraded ones assayed in the same screen?

The headline metric is **Δ-ipTM**, the difference in interface confidence between the ternary complex (E3 domain + peptide + small molecule) and the binary complex (E3 domain + peptide). Everything else in the pipeline exists to make that number trustworthy or to explain it.

NOBBLE is not a new standalone stack. It is a campaign preset on BoltzMaker plus a fifth module on BINMAN.

### Division of responsibility

| Component | Owns | Reused from |
|---|---|---|
| Execution | YAML manifest generation, MSA cache, job queue, MPS crash recovery, post-run parsing | **BoltzMaker** (`github.com/bellcheddar/BoltzMaker`) |
| Curation and scoring | Target selection, peptide library construction, geometry scoring, lysine reach, DuckDB store | **BINMAN** (`github.com/bellcheddar/BINMAN`) |
| Interaction analysis | CIF to PLIP conversion and fingerprinting | `cif_to_plip.py` (vibe-coding portfolio) |
| Serving and UI | Flask, Mol*, D3 lens graph, Plotly | **BINMAN** Depot design system |
| Natural language | Query translation, evidence triage, abstention | **BINMAN-LM** (`binman-qwen-2.5-3b-4bit-round15`), no new heads |

Where a BINMAN or BoltzMaker module does the job, import it. Do not reimplement. If a module needs widening (for example, BoltzMaker's YAML generator needs a ternary ligand chain and a pocket constraint block), widen it in place in that repository and consume it here, rather than forking.

---

## 1. Governing constraints

### 1.1 Compute

Single Apple Studio, MPS backend, no horizontal scaling. Boltz 2.2 or later with optional kernels (the non-Linux path). There is no CUDA fallback and no cloud tier in this build.

**Token count per job is the governing cost.** Pairformer cost scales poorly with sequence length, so the campaign is sized by tokens, not by job count.

| Construct | Approximate tokens | Tier-1 eligible |
|---|---|---|
| CRBN TBD (~320 aa) + 15-mer + glue | ~340 | Yes |
| KEAP1 Kelch (~300 aa) + 15-mer + glue | ~320 | Yes |
| FEM1B TPR (~360 aa) + 15-mer + glue | ~380 | Yes |
| VHL β-domain + ElonginC + ElonginB + 15-mer + ligand | ~490 | Yes, declared exception |
| DCAF15 + DDB1(BPA-BPC trim) + DDA1 + 15-mer + ligand | ~900 | Yes, declared exception |
| Full DDB1:CRBN:DDA1 assembly + peptide | ~1,300 | No |

**Hard cap: 400 tokens for tier 1, with two named exceptions (VHL and DCAF15).** Both exceptions are structurally obligatory, not convenience:

- VHL does not fold in isolation. It requires ElonginB and ElonginC for stability, so a VHL-only receptor model is physically wrong regardless of what the confidence metrics say. Include the VCB trimer.
- DCAF15 does not engage RBM39 without DDB1 and DDA1. Use a DDB1 BPA-BPC truncation (drop BPB) to keep the job under 1,000 tokens.

Every other receptor is the substrate-binding domain alone.

### 1.2 Campaign budget

Target: 300 to 500 tier-1 jobs per unattended run, each run completing inside 48 hours wall clock. Tier 1 runs ternaries and retains full scoring (decision D-NOB-001). Tier 2 re-runs the top decile at higher sampling.

| Tier | Recycles | Diffusion samples | Seeds | Potentials | Purpose |
|---|---|---|---|---|---|
| 1 | 3 | 1 | 5 | off | Triage and Δ-ipTM, full scoring retained |
| 2 | 10 | 25 | 5 | on | Pose refinement on top decile |

Each tier-1 pair is two jobs (binary and ternary) across five seeds, so a 400-pair campaign is 4,000 inferences. Size the pair list accordingly: expect roughly 200 to 250 pairs per 48-hour run at current MPS throughput. Measure the real rate in Phase 2 benchmarking and let the manifest generator size itself from the measured number rather than the estimate above.

### 1.3 MSA policy

Generate one MSA per trimmed receptor construct, offline, once, before the campaign starts. Cache as `.a3m` under `data/msa/`. Reference the cached file in every YAML. Peptide chains and ligand chains get no MSA. Never call an MSA server during a campaign.

With approximately 40 receptor constructs this is 40 MSA jobs, not 40 per peptide.

### 1.4 House style

British English. No em dashes anywhere in code comments, documentation or UI copy: use colons, semicolons or parentheses. Forbidden-word list applies (groundbreaking, revolutionary, paradigm-shifting and the rest of the standard set). Depot design system colours and typefaces, consistent with BINMAN.

---

## 2. Data layer

All sources are already acquired, licensed and pinned by BINMAN. NOBBLE consumes BINMAN's DuckDB store rather than re-acquiring. Licence terms carry over unchanged: PROTAC-DB stays internal-use-only and is never redistributed; UbiBrowser ships as derived counts only; BioLiP2 annotations are not redistributed.

### 2.1 Source roles

| Source | Rows | Role in NOBBLE |
|---|---|---|
| `sievers_zf_screen` | 5,663 | Primary calibration set: zinc fingers degraded and not degraded under IMiD treatment in the same screen. Matched positives and negatives, which is what makes the Δ-ipTM ROC meaningful |
| Słabicki 2025 (Mol Cell) | per-compound | Graded degradation labels, alanine scan, 29-analog panel. Converts a binary readout into a dose-like one |
| `mgtbind_ternary` | 3,924 | Pose ground truth: the only curated source carrying PDB entries. Supplies the benchmark ternaries and the RMSD target set |
| `mgtbind_compounds` | 3,093 | Glue chemistry with InChIKeys, used for CCD matching |
| `mgdb_glues` | 10,263 | Glue recall set 1 |
| `molgluedb_glues` | 1,840 | Glue recall set 2 |
| `ubibrowser_literature_e3` | 3,158 | Curated E3-substrate pairs: tile each substrate around its annotated degron |
| `ubibrowser_predicted_e3` | 113,656 | Exploratory arm, reported separately and never merged with the curated arm |
| `degronopedia` | — | Degron motif class assignment and cross-reference |
| Koren 2018 C-degron rules | — | Systematic C-terminal degron peptide generation |
| `protacdb_protacs` | 15,502 | Bivalent class. Not an exclusion here (unlike the Glue Atlas): NOBBLE explicitly runs PROTAC ternaries, see the BRD4 benchmark below |
| `protcid_interfaces` | — | Packing-only veto: a predicted interface matching a ProtCID crystal-packing motif is furniture |
| `digly_sites` | 976 | Lysine reach window, fitted against observed ubiquitylation sites rather than assumed boundaries |
| AFDB / UniProt / InterPro | — | Receptor models, accession mapping, family and domain boundaries |
| Open Targets | — | Tumour enrichment and expression breadth for Tier B ranking |

### 2.2 Ligand chain encoding

Prefer CCD codes over SMILES. `mgtbind_compounds` carries InChIKeys, so resolve InChIKey to CCD via the Chemical Component Dictionary and use `ccd:` in the YAML. Fall back to `smiles:` only when no CCD match exists, and flag those jobs in the manifest so the difference is visible in the results table.

Boltz v2.2.x caps affinity-head ligands at 128 heavy atoms. Several PROTACs exceed this. Where a ligand is over the cap, run the structure prediction normally and record `affinity_unavailable` rather than failing the job.

### 2.3 Post-translational modifications

Non-negotiable for several degron classes, and the reason ESMFold cannot do the peptide side:

| Degron class | Modification | CCD |
|---|---|---|
| VHL / HIF-1α | hydroxyproline | `HYP` |
| β-TrCP (DSGxxS) | phosphoserine | `SEP` |
| FBXW7 (CPD) | phosphoserine / phosphothreonine | `SEP` / `TPO` |

Any peptide whose degron class requires a modification and which is submitted without one is a manifest error, not a low-scoring result. Fail loudly at manifest validation.

---

## 3. Target selection

### 3.1 Benchmark panel (mandatory, runs first, every campaign)

Seven pairs with published crystallographic ternaries. These exist to prove the pipeline works before any discovery claim is made. **GSPT1 and BRD4 are required members** as community benchmark standards.

| # | Substrate | E3 | Small molecule | Modality | Role |
|---|---|---|---|---|---|
| 1 | **GSPT1** (eRF3a), G-loop β-hairpin, domain II | CRBN | CC-885 | Glue | Canonical glycine-degron glue benchmark. The highest-value single test in the panel |
| 2 | **BRD4** BD2 | VHL (VCB) | MZ1 | PROTAC | Canonical bivalent ternary benchmark. Tests that the pipeline handles a linked degrader correctly rather than treating it as a glue |
| 3 | **BRD4** BD1 | CRBN | dBET-class | PROTAC | Second BRD4 arm, different E3, tests E3 swap on the same substrate |
| 4 | IKZF1 ZF2 | CRBN | lenalidomide | Glue | Founding IMiD neosubstrate observation |
| 5 | CK1α | CRBN | lenalidomide | Glue | Same glue, different neosubstrate: tests specificity, not just recall |
| 6 | RBM39 RRM2 | DCAF15 (+DDB1/DDA1) | indisulam | Glue | Aryl sulfonamide arm, exercises the DCAF15 token exception |
| 7 | Cyclin K | DDB1 | CR8 | Glue | Glue acting without a substrate receptor at all |

**Resolve PDB accessions, chain identifiers and degron residue ranges programmatically from `mgtbind_ternary` and the PDB rather than hardcoding them in the spec.** Hardcoded accessions rot and are a known source of silent error. The manifest generator should query for each (substrate, E3, ligand) triple and fail the build if any benchmark member cannot be resolved to a deposited structure.

Note on GSPT1: the degron is the glycine-tipped β-hairpin in domain II. Let BINMAN's existing Degron Scan geometry module (DSSP hairpin detection, tip residue, relative SASA, geometry score) identify it from the structure rather than asserting residue numbers here. If the Degron Scan does not recover the GSPT1 hairpin independently, that is a Phase 1 blocker and a bug in the scan, not a reason to hardcode.

Note on BRD4: a PROTAC is a single ligand chain bridging two proteins, so the YAML topology and the Δ-ipTM calculation are identical to the glue case. The distinction is semantic (and matters for interpretation and for the Glue Atlas exclusion logic), not structural. Both BRD4 entries carry `modality: protac` in the manifest so the results view can facet on it.

### 3.2 Tier A, calibration (chemically validated E3s)

CRBN, VHL, DCAF15, DCAF16, KEAP1, MDM2, cIAP1, XIAP, FEM1B, DCAF11, RNF114, DDB1.

Source: BINMAN E3 Triage, filtered to `status = chemically validated`.

### 3.3 Tier B, discovery (ligandable unproven)

**Tier B is in the first campaign** (decision D-NOB-002). Do not defer it.

Selection function, applied to the 650 triaged ligases in BINMAN E3 Triage:

1. `status = ligandable unproven`
2. fpocket druggability score ≥ 0.85
3. Structural coverage of the substrate-binding domain present in PDB or AFDB with mean pLDDT ≥ 80
4. Open Targets tumour enrichment above the repertoire median
5. Rank by the existing E3 Triage composite, take the top 15

The current top of that ranking (DCAF8L1, CCNF, ASB8) should appear. Record the selected set and its scores in `data/tier_b_selection.parquet` at build time so the campaign is reproducible against a frozen ranking.

Tier B pairs are run against the **glue recall sets** (MGDB, MolGlueDB, MGTbind compounds) rather than against bespoke chemistry: the question is whether any known glue chemotype shows a Δ-ipTM signal against an unexploited ligase.

### 3.4 Peptide library construction

Per receptor, build the peptide set from:

- **Curated degrons**: UbiBrowser literature substrates tiled as 15-mers at step 3 across the annotated degron region ±20 residues
- **Sievers zinc fingers**: the degraded set and the matched non-degraded set, as ZF domains rather than tiles
- **C-degrons**: generated per the Koren 2018 rules for the relevant E3 class
- **Benchmark degrons**: the seven panel members above
- **Negatives**: composition-matched scrambles of every positive (one per positive), plus the Sievers non-degraded set, plus ProtCID packing-only epitopes

Then reduce. ESM-2 embeddings over the full candidate set, cluster, and select maximally diverse representatives to fit the measured campaign budget. Random sampling at N≈400 wastes a substantial fraction of a 48-hour run; diversity selection does not. Record the reduction ratio and the clustering parameters in the manifest.

### 3.5 Where ESMFold is used

Narrow and deliberate. ESMFold is not the docking engine and is never used for complexes.

1. Receptor models for the 152 `afdb_model_unavailable` failures and any Tier B receptor lacking an AFDB model
2. Novel sequences that cannot be in AFDB: tiling variants, alanine scans, point mutants, designed peptides
3. Ordered/disordered prefilter for designed or constrained peptides only. **Do not apply this filter to linear degron mimetics**, where disorder is expected and low pLDDT is the correct result rather than a rejection criterion

ESM-2 (not ESMFold) does the embedding and diversity reduction in 3.4.

---

## 4. Scoring

Seven signals, in descending order of trust. The composite is reported alongside the components, never instead of them. Every component is a column in the results table and a selectable axis in the Plotly views.

### 4.1 Geometry against the empirical envelope (primary)

Run BINMAN's bridging filter unchanged on every Boltz output mmCIF: ΔSASA against both chains, buried fraction, heavy-atom contact counts, bridging balance. These were built with gemmi and FreeSASA for crystal structures and apply verbatim to predicted ternaries.

The output is not a pass/fail against a fixed threshold. It is a **percentile against the distribution of 285,996 experimentally observed bridges already in the BINMAN atlas**. Report as `bridge_percentile`. This is the strongest discriminator in the stack because it compares a prediction to real interfaces rather than to a model's self-assessment.

### 4.2 Lysine reach window

Apply BINMAN's reach-window fit (already calibrated against 976 observed diGly sites) to the predicted peptide pose. A peptide that forms an excellent interface and presents no lysine into the ubiquitination shell is not a degrader lead.

Report `lysine_reach_fit` plus the count of lysines inside the window and their relative SASA.

### 4.3 Δ-ipTM, glue dependence (headline)

```
delta_iptm = iptm_min_ternary - iptm_min_binary
```

Using the minimum across the five seeds in each condition, not the mean.

Falsifiable prediction, tested in Phase 3: IMiD-dependent zinc fingers from Sievers show a large positive Δ with lenalidomide or pomalidomide present; non-degraded zinc fingers from the same screen do not. Equivalently for indisulam on RBM39/DCAF15 and CR8 on cyclin K/DDB1.

If this separation holds, NOBBLE has a glue-dependence classifier with a matched-control ROC behind it. If it does not, that is a real result about co-folding models and ternary cooperativity, and the app should report it as such rather than hiding it.

### 4.4 Pose convergence

Pairwise peptide backbone RMSD across the five seeds, after superposition on the receptor. Report mean and spread. Convergence tracks reality better than confidence for peptides: a peptide landing in the same groove from five different noise seeds is saying something ipTM is not.

### 4.5 ipTM-min

Report, but treat as enrichment rather than decision. Calibration note for the UI copy and the About page: the Thera-SAbDab benchmark of Boltz-2 across 519 therapeutic antibodies paired with cognate and non-cognate antigens found confidence metrics gave only weak though above-chance discrimination (ROC-AUC between 0.5 and 0.60), with ipTM-min carrying the strongest signal and multivariate modelling adding essentially nothing. Peptide-protein should fare better than antibody-antigen, but the app must not present ipTM as a verdict.

### 4.6 PLIP interaction fingerprint

Via `cif_to_plip.py`. Compare the predicted contact set against the canonical degron contact pattern for that E3 class (for example, burial into the CRBN tri-tryptophan pocket; the hydroxyproline hydrogen-bond network in VHL).

**Carry the `pdb_tidy` CONECT serial-gap fix across.** Boltz mmCIF output has the same failure mode that corrupts OpenBabel bond perception, and an uncaught instance produces silently wrong interaction fingerprints rather than an error.

### 4.7 Vetoes

- **ProtCID packing-only**: predicted interface matching a crystal-packing motif is furniture, scored and retained but flagged `furniture: true` and excluded from ranked views by default
- **Pocket-conditioning disagreement**: every pair runs both conditioned and unconstrained. Agreement is the signal. A pose that only appears under conditioning is flagged `forced: true`. Forcing a binder into a site it did not choose reliably produces the right neighbourhood and the wrong pose, so forced hits are shown separately and never in the headline ranking
- **Affinity head**: `affinity_pred_value` is recorded for the small-molecule chain only, where the ligand is under the 128-atom cap. It is a column, never a ranking key. There is no protein-protein affinity path in Boltz-2, so no peptide affinity is reported at all. The UI must not offer one

### 4.8 Composite

```
nobble_score = w1 * bridge_percentile
             + w2 * lysine_reach_fit
             + w3 * normalised(delta_iptm)
             + w4 * convergence_score
             + w5 * plip_fingerprint_match
```

Fit the weights on the benchmark panel and the Sievers matched set in Phase 3. Do not hand-set them. Expose the weights in the UI with sliders so the ranking can be re-derived live.

---

## 5. Validation

Three layers, all gating. A campaign that fails any of these publishes its failure rather than its hits.

1. **Pose recovery**: peptide backbone RMSD to the deposited crystal ternary for every member of the `mgtbind_ternary` set that overlaps the campaign, reported as a success-rate curve at 1, 2, 3 and 5 Å. The seven benchmark pairs are reported individually, by name, on the About page
2. **Time split**: entries deposited after the Boltz-2 training cutoff, run blind through the AlphaFraud harness. Canonical degrons are memorised, so this is the only number that estimates prospective performance. Report it next to the retrospective number and label both clearly
3. **Matched-control ROC**: Δ-ipTM on the Sievers degraded versus non-degraded split, with the Słabicki graded labels as a secondary continuous test

---

## 6. Phases

Each phase has a gate. An unattended run stops at a failed gate and writes a diagnostic rather than proceeding.

### Phase 1: Curation and manifest

**Build**

- `nobble/curate/` module reading BINMAN's DuckDB store
- Receptor construct definitions: domain boundaries from InterPro, trimming via the existing `trimmed_structures` machinery, with the VHL (VCB) and DCAF15 (DDB1 BPA-BPC + DDA1) exceptions handled explicitly
- Benchmark panel resolver: query `mgtbind_ternary` and the PDB for all seven pairs, resolve chains and ligand CCDs, fail the build on any unresolved member
- Tier A and Tier B selection per §3.2 and §3.3, frozen to `data/tier_b_selection.parquet`
- Peptide library construction per §3.4, including composition-matched scramble generation
- ESM-2 embedding and diversity reduction, sized from the Phase 2 throughput measurement (run Phase 2 §benchmark first if no measurement exists)
- MSA precomputation for every receptor construct, cached to `data/msa/`
- Manifest validation: PTM completeness per §2.3, token count per job against the cap, CCD resolution, ligand atom count against the affinity cap

**Gate**

- All seven benchmark pairs resolve to deposited structures with chains and ligands assigned
- BINMAN's Degron Scan independently recovers the GSPT1 domain II hairpin and the IKZF1 ZF2 degron from structure, without hardcoded residue ranges
- Zero manifest validation errors
- Every job in the manifest is under 400 tokens, or is one of the two declared exceptions
- Manifest contains the Tier B set, non-empty, with at least 10 ligases

### Phase 2: Execution

**Build**

- Extend BoltzMaker's YAML generator for: a third ligand chain by CCD, pocket and contact constraints, the `modifications` block for HYP/SEP/TPO, the `properties: affinity:` block scoped to the ligand chain, and paired binary/ternary job emission
- Throughput benchmark: run the seven benchmark pairs first, measure seconds per token, and write the measured rate to `data/throughput.json`. Everything downstream sizes itself from this file
- Job queue with per-job checkpointing. BoltzMaker's MPS crash recovery is load-bearing here: multi-day MPS runs hit OOM and NaN diffusion steps, and a campaign that cannot resume mid-queue is unusable
- Tier 1: 5 seeds × (binary + ternary) × (conditioned + unconstrained), 3 recycles, 1 diffusion sample, potentials off
- Tier 2: top decile by Phase 3 composite, 10 recycles, 25 diffusion samples, potentials on
- Output parsing into DuckDB: confidence JSON, affinity JSON where present, mmCIF paths

**Gate**

- Seven benchmark pairs complete and parse
- Measured throughput written and the campaign re-sized against it
- Queue survives a forced kill mid-run and resumes without duplicating or dropping a job (test this explicitly, do not assume it)
- Tier 1 completes inside 48 hours wall clock, or the manifest is automatically trimmed and the trim is logged

### Phase 3: Scoring and validation

**Build**

- Geometry scoring: BINMAN bridging filter on every output, percentile against the 285,996-bridge reference distribution
- Lysine reach window fit
- Δ-ipTM, convergence RMSD, ipTM-min aggregation
- PLIP fingerprinting via `cif_to_plip.py`, with the CONECT serial-gap fix verified against a Boltz output before the batch runs
- ProtCID furniture veto, conditioning-disagreement flag
- Composite weight fitting on the benchmark panel and the Sievers matched set
- The three validation layers in §5

**Gate**

- Pose recovery reported for all seven benchmark pairs, with GSPT1/CRBN/CC-885 and BRD4-BD2/VHL/MZ1 named individually
- Δ-ipTM ROC computed on the Sievers matched split, with a confidence interval
- Time-split number computed and reported alongside the retrospective number
- PLIP fingerprints generated with no silent bond-perception failures (assert on CONECT integrity, do not sample-check)

A poor ROC is **not** a gate failure. Reporting no ROC, or reporting one without the matched negatives, is.

### Phase 4: Application

Flask, Depot design system, served alongside BINMAN as a fifth module. Mol\*, PLIP and Plotly throughout; every element interactive with rich hover and tooltip behaviour.

**Tabs**

1. **Campaign** — the pair ledger. Sortable, filterable table over every (receptor, peptide, ligand) triple. Faceted on modality (glue / PROTAC), tier (benchmark / A / B), and flags (furniture, forced, affinity_unavailable). Row hover previews the pose thumbnail and the component scores; row click pins the triple into the shared selection state and loads it into every other tab
2. **Pose** — Mol\* viewer on the predicted ternary. Receptor cartoon, peptide tube coloured by per-residue pLDDT, ligand ball-and-stick. Toggles for: the deposited crystal ternary superposed (benchmark pairs only, with live RMSD readout), all five seeds overlaid to show convergence visually, the conditioned versus unconstrained pair side by side, and surface representation coloured by ΔSASA contribution. Reuse BINMAN's existing viewer controls (Reset / Repr / Labels / Spin / Interface)
3. **Interactions** — PLIP contact map as an interactive Plotly heatmap, peptide residue against receptor residue, cell hover giving interaction type, distance and angle. Clicking a cell highlights that contact pair in the Mol\* viewer on the Pose tab. Alongside it, the canonical-degron reference fingerprint for that E3 class with matched contacts highlighted and missing ones greyed
4. **Delta** — the headline view. Plotly scatter of Δ-ipTM against bridge percentile, points coloured by experimental label (degraded / not degraded / unknown), sized by lysine reach fit. Marginal distributions on both axes. Lasso selection pushes the selected set to the Campaign tab. A second panel holds the ROC curve with a draggable threshold that live-updates precision and recall readouts
5. **Benchmark** — the seven panel members as a dedicated page. One card each: crystal structure, predicted pose, RMSD, every component score, and a plain-language note on what that pair tests. GSPT1 and BRD4 lead. This is the page a sceptical reader opens first, so it should be the most finished thing in the app
6. **About** — pipeline schematic in the BINMAN idiom, stage counts, full reference table with licences and DOIs, the Δ-ipTM calibration caveat from §4.5 stated plainly, and the three validation numbers from §5

**Cross-tab behaviour**

Shared selection state across all six tabs, matching BINMAN's existing GLUE / E3 / TARGET pin model, extended with a PEPTIDE slot. Pinning anywhere updates everywhere. The Lens graph in BINMAN gains predicted edges, visually distinguished from experimental ones (dashed, lower opacity) and filterable out in one click.

**Interactivity requirements**

- Every numeric cell, point and bar carries a tooltip giving the raw value, the units, its percentile against the reference distribution, and the source of the number (measured / predicted / model-derived)
- Every Plotly figure supports lasso selection that propagates to the shared selection state
- Every score in the composite is a slider in a weights panel; moving a slider re-ranks the Campaign table live without a server round trip
- Hover on any E3 or substrate name gives a popover card with its UniProt accession, family, fpocket score and tier
- No figure is a static image. If something cannot be made interactive, it does not go in the app

**BINMAN-LM**

No new heads. Head A translates campaign questions into query objects over the NOBBLE tables ("show me Tier B pairs where the glue dependence beats the matched negatives"). Head C abstains when the campaign has not run the pair in question and states what is missing. The no-arithmetic contract holds: the model never emits a number.

**Gate**

- All six tabs render with real campaign data
- Selection state propagates correctly across every tab (test each pairing)
- Every figure is interactive and every element has a tooltip
- Benchmark tab renders all seven cards with crystal superposition and live RMSD
- Lighthouse and the Depot accessibility checks pass at BINMAN's existing standard

---

## 7. Repository layout

```
NOBBLE/
├── BUILD_SPEC.md              this file
├── DECISIONS.md               decision log, seeded below
├── README.md                  branded, generated via readme_forge.py at the end of Phase 4
├── pyproject.toml             pixi-based, matching the BoltzMaker packaging approach
├── nobble/
│   ├── curate/                Phase 1
│   ├── execute/               Phase 2, thin wrapper over BoltzMaker
│   ├── score/                 Phase 3, thin wrapper over BINMAN geometry
│   ├── validate/              Phase 3 validation layers
│   └── app/                   Phase 4 Flask app
├── data/
│   ├── msa/                   cached receptor MSAs
│   ├── throughput.json        measured MPS rate, written by Phase 2
│   ├── tier_b_selection.parquet
│   └── nobble.duckdb
├── campaigns/                 one directory per run, manifest + outputs + results
└── tests/
```

## 8. Decision log seed

| ID | Decision | Date |
|---|---|---|
| D-NOB-001 | Tier 1 runs ternaries and retains full scoring, rather than binary-only triage with ternaries reserved for survivors | 2026-11-03 |
| D-NOB-002 | Tier B (ligandable unproven) is included in the first campaign rather than deferred until Tier A calibration completes | 2026-11-03 |
| D-NOB-003 | GSPT1 and BRD4 are mandatory benchmark panel members, as community standards. BRD4 runs on both VHL and CRBN arms | 2026-11-03 |
| D-NOB-004 | Token cap of 400 for tier 1, with VHL (VCB trimer) and DCAF15 (DDB1 BPA-BPC + DDA1) as declared structural exceptions | 2026-11-03 |
| D-NOB-005 | Affinity head is recorded for the small-molecule chain only and is never a ranking key. No peptide affinity is reported | 2026-11-03 |
| D-NOB-006 | Composite weights are fitted on the benchmark panel and the Sievers matched set, not hand-set | 2026-11-03 |
| D-NOB-007 | NOBBLE is a BoltzMaker campaign preset plus a fifth BINMAN module, not a standalone stack. Shared code is widened in place in those repositories, never forked | 2026-11-03 |

## 9. Open items for Marc

1. Confirm the Studio's chip and unified memory so the token cap and the 48-hour budget can be set from hardware rather than estimated
2. Confirm the Boltz version pinned for this build (2.2.x or later) and whether the optional-kernels path is already installed
3. Decide whether the Tier B exploratory arm publishes as a ranked list or as an abstention-heavy list where BINMAN-LM Head C declines on anything below a confidence floor
4. Decide whether NOBBLE serves at `nobble.mdeller.com` or as a sub-route of `binman.mdeller.com`
