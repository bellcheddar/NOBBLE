"""Single source of truth for every path and interpreter NOBBLE uses.

Nothing else in the codebase builds a path to BINMAN or BoltzMaker by hand.
"""
from __future__ import annotations

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
