"""Single source of truth for every path and interpreter NOBBLE uses.

Nothing else in the codebase builds a path to BINMAN or BoltzMaker by hand.
"""
from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO = ROOT.parent

BINMAN = PORTFOLIO / "BINMAN"
BOLTZMAKER = PORTFOLIO / "BoltzMaker"

# BINMAN's stores. Read-only from NOBBLE's side: see DECISIONS.md D-NOB-008.
BINMAN_ATLAS = BINMAN / "data" / "atlas" / "binman.sqlite"
BINMAN_VALIDATION = BINMAN / "data" / "validation"
BINMAN_INTERIM = BINMAN / "data" / "interim"
BINMAN_CACHE = BINMAN / "data" / "cache"

# Interpreters. Curation and scoring run under BINMAN's solved environment
# (gemmi, freesasa, duckdb, rdkit, plip); inference runs under BoltzMaker's.
PY_SCIENCE = BINMAN / ".pixi" / "envs" / "default" / "bin" / "python"
PY_BOLTZ = BOLTZMAKER / ".pixi" / "envs" / "default" / "bin" / "python"
BOLTZ_CLI = BOLTZMAKER / ".pixi" / "envs" / "default" / "bin" / "boltz"

# NOBBLE's own tree.
CONFIG = ROOT / "config"
DATA = ROOT / "data"
MSA = DATA / "msa"
MANIFESTS = DATA / "manifests"
INTERIM = DATA / "interim"
REFERENCE = DATA / "reference"
CAMPAIGNS = ROOT / "campaigns"
DUCKDB = DATA / "nobble.duckdb"
THROUGHPUT = DATA / "throughput.json"
TIER_B_SELECTION = DATA / "tier_b_selection.parquet"

for _directory in (MSA, MANIFESTS, INTERIM, REFERENCE, CAMPAIGNS):
    _directory.mkdir(parents=True, exist_ok=True)


def load_toml(name: str) -> dict:
    """Read a config file from config/ by bare name, with or without suffix."""
    path = CONFIG / (name if name.endswith(".toml") else f"{name}.toml")
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. Run tools/hwprobe.py for hardware.toml and tuning.toml."
        )
    with path.open("rb") as handle:
        return tomllib.load(handle)


def tuning() -> dict:
    return load_toml("tuning")


def thresholds() -> dict:
    return load_toml("thresholds")


def hardware() -> dict:
    return load_toml("hardware")


def science_env() -> dict:
    """Environment for subprocesses that import torch next to conda-forge numpy."""
    settings = tuning().get("env", {})
    return dict(os.environ, **{key: str(value) for key, value in settings.items()})


def tool_env(*environments) -> dict:
    """science_env plus the given pixi environments' bin directories on PATH.

    Needed because several tools are console scripts inside a pixi environment
    rather than importable modules: mkdssp, pdb_tidy and pdb_validate are all
    found via PATH by the code that calls them. Invoking an environment's
    interpreter directly does not activate it, so PATH still points at the outer
    shell's and the tool is reported missing even though it is installed. This
    has now caused two separate silent failures (a DSSP run and a PLIP
    conversion), so the PATH is assembled here rather than per caller.
    """
    environment = science_env()
    roots = environments or (BOLTZMAKER, BINMAN)
    bins = [str(Path(root) / ".pixi" / "envs" / "default" / "bin") for root in roots]
    existing = environment.get("PATH", "")
    environment["PATH"] = os.pathsep.join([*bins, existing]) if existing else os.pathsep.join(bins)
    # libcifpp's dictionaries, which mkdssp loads by this variable.
    for root in roots:
        share = Path(root) / ".pixi" / "envs" / "default" / "share" / "libcifpp"
        if share.exists():
            environment.setdefault("LIBCIFPP_DATA_DIR", str(share))
            break
    return environment


def write_atomic(path: Path, text: str) -> Path:
    """Write `text` to `path` so a reader never sees it half-written.

    `Path.write_text` truncates the file and then writes into it, so a kill
    inside that window leaves whatever had been flushed. For a file something
    reads later, that is a corruption with no self-healing: a cached InterPro
    response is kept because it `exists()`, never re-fetched, and swallowed by
    `domain_context`'s `except Exception` into "interpro_unavailable", which
    silently drops a substrate from its folded domain to the 15-mer. A cached
    UniProt sequence is worse, because it is plain text: a truncation is still
    a valid-looking protein and has no parse step to fail at, so every domain
    slice taken from it would be quietly short.

    Written to a sibling and renamed instead. `os.replace` is atomic within a
    directory, so a reader sees the old contents or the new ones and nothing
    between. The project's own rule is to assume the process can be killed at
    any moment (F110).

    Not a general-purpose utility: use it for anything a later run reads back,
    which is every cache and every manifest.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".writing")
    temporary.write_text(text)
    os.replace(temporary, path)
    return path


def read_jsonl(path: Path, *, tolerate_torn: bool = False) -> list[dict]:
    """Rows from a JSON-lines file.

    `tolerate_torn` says what an unparseable line means, and the answer
    differs by file rather than by taste.

    `results.jsonl` and `state.jsonl` are appended to one row at a time by a
    runner that may be killed at any moment, so a torn final line is an
    expected state and the rows before it are good. `scores.jsonl` is written
    in one pass and a kill truncates it, with the same consequence. For those,
    `tolerate_torn=True`: skip the line and keep the rest. The runner's own
    `completed()` has always done this, with the comment "a torn final line
    from a kill mid-write: ignore it and re-run that job", and seven other
    readers of the same files did not, so a kill at the wrong moment made the
    next stage raise instead of processing the 2,359 complete records (F111).

    `queue.jsonl` and the library manifest are written once, before anything
    runs, and nothing appends to them. A line that will not parse there is not
    a torn tail, it is a damaged input, and skipping it would run 2,359 of
    2,360 jobs without saying so. Those stay strict, which is the default.
    """
    path = Path(path)
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if tolerate_torn:
                continue
            raise
    return rows


def torn_lines(path: Path) -> int:
    """How many lines of a JSON-lines file will not parse.

    So a stage that tolerates a torn tail can say how many it skipped rather
    than skipping in silence, which is the failure F99 and F103 were both
    instances of.
    """
    path = Path(path)
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError:
            count += 1
    return count
