# 🧬 NOBBLE

> **Does a molecular glue actually change the interface it is supposed to create? NOBBLE measures it, against 285,996 real ones.**

![python](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white) ![boltz](https://img.shields.io/badge/Boltz--2-ternary%20co--folding-467FF7) ![backend](https://img.shields.io/badge/backend-Apple%20MPS-000000?logo=apple&logoColor=white) ![status](https://img.shields.io/badge/status-in%20development-fcb900) ![licence](https://img.shields.io/badge/licence-MIT-00897B) ![author](https://img.shields.io/badge/author-Marc%20C.%20Deller%2C%20D.Phil.-1C244B)

<table>
<tr>
<td>🌐 <b>Website</b></td><td><a href="https://marcdeller.com" target="_blank" rel="noopener noreferrer">marcdeller.com</a></td>
<td>✉️ <b>Contact</b></td><td><a href="mailto:marc@marcdeller.com">marc@marcdeller.com</a></td>
<td>🐙 <b>GitHub</b></td><td><a href="https://github.com/bellcheddar" target="_blank" rel="noopener noreferrer">@bellcheddar</a></td>
</tr>
</table>

---

**N**eosubstrate and **O**ligopeptide **B**inder **B**enchmarking for **L**igase
**E**ngagement. NOBBLE generates and scores peptide poses against curated
targeted-protein-degradation (TPD) machinery using Boltz-2 ternary co-folding,
and asks one question of every pair: does the presence of the glue or degrader
change the predicted interface, and does that change separate experimentally
degraded substrates from experimentally non-degraded ones assayed in the same
screen?

Why it matters: a co-folding model will report high confidence in a ternary
complex that does not exist, and it will do so in a way that looks exactly like
success. NOBBLE's answer is not to trust the model's self-assessment but to
compare every predicted interface against the distribution of 285,996
experimentally observed small-molecule bridges, to run a matched control for
every positive, and to publish the pairs where the method fails as prominently
as the ones where it works. It is useful for: triaging neosubstrate hypotheses
before committing wet-lab effort, calibrating how far a co-folding model can be
trusted on induced interfaces, and benchmarking glue-dependence against
published degradation screens.

## 🎯 The headline metric

```
delta_iptm = iptm_min_ternary - iptm_min_binary
```

The difference in interface confidence between the ternary complex (E3 domain +
peptide + small molecule) and the binary complex (E3 domain + peptide), taking
the minimum across five seeds in each condition. Everything else in the
pipeline exists to make that number trustworthy or to explain it.

Delta-ipTM is measured on the **receptor-to-peptide chain pair**, not the global
ipTM: on a ternary complex the global figure averages in the receptor-to-ligand
interface, which is the easy one, so a glue sitting perfectly in its pocket
while the degron fails to dock would raise it.

## ✨ What is in the box

| Module | Spec phase | Does |
|---|---|---|
| `nobble/curate/` | 1 | Benchmark panel resolution, receptor constructs from InterPro, tier selection, peptide library, manifest and validation |
| `nobble/execute/` | 2 | MSA precomputation, Boltz YAML generation, a resumable job queue with per-job checkpointing |
| `nobble/score/` | 3 | Bridge percentile, Delta-ipTM, pose convergence, docking checks, lysine geometry, PLIP fingerprints |
| `nobble/validate/` | 3 | Pose recovery, time-split blind evaluation, matched-control ROC |
| `nobble/app/` | 4 | Flask application, six tabs, Mol\* and Plotly throughout |

NOBBLE is not a standalone stack. It is a campaign preset on
[BoltzMaker](https://github.com/bellcheddar/BoltzMaker) plus a fifth module on
[BINMAN](https://github.com/bellcheddar/BINMAN), and shared code is widened in
place in those repositories rather than forked.

## 🔬 The benchmark panel

Seven pairs with published crystallographic ternaries, run first in every
campaign, to prove the pipeline works before any discovery claim is made. Every
PDB accession, chain identifier and ligand code below is resolved
**programmatically** at build time from the curated sources and the deposited
structures: none is written into the code, because hardcoded accessions rot and
are a known source of silent error.

| # | Substrate | E3 | Small molecule | Modality | Resolved to | Role |
|---|---|---|---|---|---|---|
| 1 | GSPT1, domain II hairpin | CRBN | CC-885 | Glue | 5HXB (`85C`) | Canonical glycine-degron glue benchmark |
| 2 | BRD4 BD2 | VHL (VCB) | MZ1 | PROTAC | 5T35 (`759`) | Canonical bivalent ternary benchmark |
| 3 | BRD4 BD1 | CRBN | dBET57 | PROTAC | 6BNB | E3 swap on the same substrate |
| 4 | IKZF1 ZF2 | CRBN | pomalidomide | Glue | 6H0F (`Y70`) | Founding IMiD neosubstrate observation |
| 5 | CK1alpha | CRBN | lenalidomide | Glue | 5FQD (`LVY`) | Same glue, different neosubstrate |
| 6 | RBM39 RRM2 | DCAF15 | indisulam | Glue | 6Q0W (`EF6`) | Aryl sulfonamide arm |
| 7 | cyclin K | DDB1 | CR-8 | Glue | 6TD3 (`RC8`) | Glue acting without a substrate receptor |

## 🎯 Scoring

Seven signals, in descending order of trust. The composite is reported alongside
its components, never instead of them, and its weights are fitted on the
benchmark panel and the Sievers matched set rather than hand-set.

| Signal | What it is | Status |
|---|---|---|
| Bridge percentile | Buried surface, contact counts and bridging balance, as a percentile against 285,996 observed bridges | primary |
| Delta-ipTM | Glue dependence, receptor-to-peptide pair, minimum across seeds | headline |
| Pose convergence | Pairwise peptide backbone RMSD across seeds, superposed on the receptor | working |
| ipTM-min | Reported as enrichment, never as a verdict | working |
| PLIP fingerprint | Interaction pattern against the canonical degron contacts for that E3 class | working |
| Lysine geometry | Lysine exposure and distance to the glue | reported as measurement, **not validated** |
| ProtCID packing veto | Crystal-packing motifs flagged as furniture | **not computed**, source unavailable |

Two of those carry honest caveats rather than numbers, and both are documented
in `DECISIONS.md` with the measurements behind them.

## 📊 Early results

From the benchmark panel, at tier-1 triage settings, written up in `FINDINGS.md`:

- **Geometry separates poses that ipTM cannot.** For GSPT1 / CRBN / CC-885, a
  pose that bridges scores ipTM 0.885 and one that does not scores 0.877. The
  highest ipTM in the ternary set, 0.916, does not bridge at all.
- **The glue docks reliably; the degron does not follow.** All five canonical
  CRBN contacts (W380, W386, W400, H378, F402) matched in every seed, so CC-885
  is placed correctly and reproducibly, while only 3 of 10 ternary trajectories
  bring the degron into contact with it. The PLIP fingerprint and the buried
  surface filter reach that verdict independently.
- **One trajectory in five failed to dock the peptide at all**, leaving it 81 A
  from the receptor in free solvent. A confidence aggregate cannot tell that
  apart from a weak interface, so NOBBLE checks docking explicitly.

These are interim, single-pair, triage-tier numbers. They are published here
because a pipeline that only reports its successes is not a benchmark.

## 📋 Requirements

| Requirement | Notes |
|---|---|
| Apple Silicon with MPS | Developed on an M2 Ultra (16 performance cores, 128 GB unified memory, 60 GPU cores). No CUDA path in this build |
| Boltz 2.2 or later | Supplied by BoltzMaker's pixi environment, with its model weights cached |
| BINMAN checkout | Supplies the bridge atlas, the degron scan, the ligase triage and the geometry filter |
| BoltzMaker checkout | Supplies Boltz, PLIP, OpenBabel and `cif2plip` |
| pixi | Both environments are pixi-managed and `osx-arm64` only |

Nothing in the codebase hard-codes a core count, a memory figure, a device or a
threshold. Hardware settings are derived by `tools/hwprobe.py` into
`config/hardware.toml` and `config/tuning.toml`; every cutoff lives in
`config/thresholds.toml`.

## 🚀 Usage

```bash
# Phase 0: probe the machine and derive the tuning
python3 tools/hwprobe.py

# Phase 1: check the gates (panel resolution, degron recovery, token budget)
python -m pytest tests/test_phase1.py -q

# Phase 1: precompute one MSA per receptor construct, once, offline
bash tools/run_msa.sh

# Phase 2: assemble the benchmark campaign and run its queue
python -c "from nobble.execute.campaign import assemble_benchmark; print(assemble_benchmark())"
bash tools/run_queue.sh

# Phase 3: score whatever has landed, re-runnable against a live queue
python -m nobble.score.run
```

Long runs belong in `tmux`: `tools/run_queue.sh` wraps the queue in
`caffeinate -dimsu` and the queue itself is resumable, because multi-day MPS
runs hit OOM and NaN diffusion steps and a queue that cannot resume mid-run is
unusable.

## 🔧 Tech stack

| Layer | Choice |
|---|---|
| Co-folding | Boltz-2, MPS backend, optional kernels disabled |
| Structure handling | gemmi, FreeSASA, mkdssp |
| Interactions | PLIP via `cif2plip`, with the CONECT serial-gap fix asserted on every structure |
| Embeddings | ESM-2 (35M) for diversity reduction, on MPS |
| Stores | BINMAN's SQLite atlas read-only, DuckDB and Parquet for analysis |
| Application | Flask, Jinja, vanilla JS, Mol\*, Plotly, D3 |

## 📄 Licence and reuse

The code in this repository is MIT licensed. **The data is not ours to give.**
NOBBLE reads curated third-party databases through BINMAN, several of which
restrict redistribution: PROTAC-DB is internal-use only, UbiBrowser ships as
derived counts, and BioLiP2 annotations are not redistributed. No third-party
dataset is bundled here, and the generated campaign artefacts are deliberately
excluded from version control because some of them embed those records. If you
reuse this, acquire the sources yourself under their own terms and cite them.

## 🧾 Provenance

`DECISIONS.md` records every judgement made during the build, with the
alternatives, the reason and how to reverse it, including the places where the
build specification turned out to be wrong about its own data. `BUILD_LOG.md` is
the timestamped event log, `PROGRESS.md` the phase checklist, `FINDINGS.md` the
results, and `BUILD_SPEC.md` the authoritative specification the build follows.

---

## 👤 Author

**Marc C. Deller, D.Phil.**  
Structural biologist & drug discovery scientist  

<table>
<tr>
<td>🌐</td><td><a href="https://marcdeller.com" target="_blank" rel="noopener noreferrer">marcdeller.com</a></td>
<td>✉️</td><td><a href="mailto:marc@marcdeller.com">marc@marcdeller.com</a></td>
<td>🐙</td><td><a href="https://github.com/bellcheddar" target="_blank" rel="noopener noreferrer">github.com/bellcheddar</a></td>
</tr>
</table>
