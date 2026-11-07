# NOBBLE

Built from BUILD_SPEC.md, which is authoritative.

- Unattended mode. Never stop except at a Gate (see Gates in this file). Decide,
  log to DECISIONS.md, continue.
- Logging: BUILD_LOG.md (events, timestamped), PROGRESS.md (phase checklist),
  DECISIONS.md (choices with alternatives and reversal notes).
- Every stage writes data/manifests/<stage>.jsonl and is resumable and idempotent.
  Assume the process can be killed at any moment.
- Commit locally at the end of every phase. Never push (Gate G4).
- Hardware settings come from config/tuning.toml, written by tools/hwprobe.py.
  Never hard-code cores, memory or device.
- Thresholds come from config/thresholds.toml. Never hard-code a cutoff in Python.
- UI design system: "Depot", inherited from BINMAN. The marcdeller.com house header
  and palette do NOT apply to the app UI. They do apply to the README.
- BINMAN-LM never computes, estimates or reports a number. All numeric values are
  computed deterministically in Python.
- Shared code is widened in place in BINMAN or BoltzMaker, never forked (D-NOB-007).
- House style: British English, no em dashes (colons, semicolons or parentheses),
  and none of: groundbreaking, revolutionary, paradigm-shifting, game-changing,
  cutting-edge, unprecedented, seamless, leverage (verb), delve.

## Environments

| Purpose | Interpreter |
|---|---|
| Curation, scoring, validation | `../BINMAN/.pixi/envs/default/bin/python` (gemmi, freesasa, duckdb, rdkit, plip) |
| Boltz-2 inference | `../BoltzMaker/.pixi/envs/default/bin/python` (boltz, torch MPS) |
| App | `uv` environment under `app/` |

Set `KMP_DUPLICATE_LIB_OK=TRUE` for anything importing torch alongside the
conda-forge scientific stack: see BoltzMaker's pixi.toml for why.

## Operating rules earned the hard way

Three things cost hours on 2026-11-07 and none is inferable from the code.

- **Never edit a script the chain is executing.** Bash reads a script
  incrementally, so an edit shifts the byte offsets under a running copy and
  it resumes mid-statement. `tools/run_chain.sh` died on a valid file with
  `syntax error near unexpected token 'else'` and never reached tier 2
  (F308). While the chain holds them, `run_chain.sh`, `tier2.sh`,
  `refresh.sh`, `corrections.sh`, `run_queue.sh` and `wait_for_gpu.sh` are
  off limits; a Python module is safer only because the interpreter reads it
  whole at import.
- **Search FINDINGS before naming a cause.** `tools/findings.py --grep` is
  one command. Three findings were written on the premise that duplicate
  files in the tree were unexplained, while F173 and F186 had recorded the
  cause and `deploy/deploy.sh` already refused on it (F304). Doing the sweep
  again is F291 and F295; concluding from a sweep without searching is
  worse, because it reaches a wrong answer rather than a slow one.
- **Never `git add -A` while a build owns `deploy/atlas`.** The bundle is
  2,515 tracked files and 330 MB, the build clears and rewrites it, and
  iCloud restores conflict copies into it minutes later. `git add -A`
  committed and pushed 706 of them (F303) and later failed outright with
  `unable to stat`. Commit by path.

## Gates

| Gate | Opens when |
|---|---|
| G1 Compute | MPS and CPU smoke tests both fail, or the minimum viable set exceeds MAX_COMPUTE_HOURS after automatic scope reduction |
| G2 Secrets | Any credential is needed |
| G3 Deploy | App passes QC locally and is ready for the droplet (nginx vhost and TLS for nobble.mdeller.com) |
| G4 Publish | Any git push, repo creation or public release |
| G5 Disk | Free space on the project volume falls below 50 GB |
| G6 Science | A positive control still fails after the fallback ladder and that would invalidate a headline result |

## UI copy

Keep narrative prose in the app to a minimum. One short line per panel saying
what it shows or what the number means. Reasoning belongs in DECISIONS.md and
FINDINGS.md, not on screen. Budget: under 40 words per panel, under 150 per
page, excluding tables, labels and pipeline-generated status text. Disclaimers
only where a figure would be actively misread without one, and then one
sentence; a caveat repeated on every tab reads as a lack of confidence in the
numbers rather than as rigour.
