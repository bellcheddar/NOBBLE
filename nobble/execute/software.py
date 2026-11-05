"""Which Boltz produced the coordinates (F185).

`campaign.json` publishes the tuning a campaign ran under: token caps,
recycle counts, diffusion samples, seeds. It did not publish the model
version, and every number in the atlas is a Boltz-2 prediction, so the one
thing a reader needs to reproduce a pose was the one thing missing. The About
page says "Boltz-2" and names no version either.

Measured here rather than written down, for the same reason nothing in this
project hard-codes a core count: the environment is the fact, and a version
in a config file is a claim about it. Read from the BoltzMaker environment,
which owns the install the runner invokes, following `hwprobe.mps_state()`.

Metadata only, never an import. `importlib.metadata.version("torch")` reads
the installed distribution's metadata without importing torch, which takes
40 ms against several seconds, and the atlas build runs this on every publish.

Failure is a recorded state rather than an exception. An unreadable
environment must not stop a campaign assembling or an atlas building, and a
missing version must not be published as a blank that reads like "no
version": `status` says what happened and the version keys are absent.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone

from nobble import paths

# What the atlas is entitled to say produced it. `boltz` is the model, `torch`
# the runtime it ran on, and both are part of reproducing a coordinate set.
PACKAGES = ("boltz", "torch")

def _probe(names: tuple[str, ...]) -> str:
    """The one-liner run in the Boltz environment.

    Built by concatenation rather than `str.format`, because the probe's own
    source contains `out = {}` and `format` read those braces as a
    positional field: the first version of this raised IndexError before the
    subprocess ever started, and the failure surfaced as the recorded status
    `unreadable: IndexError`, which is the error path working on my own bug.
    """
    return (
        "import importlib.metadata as m, json\n"
        "out = dict()\n"
        "for name in " + repr(list(names)) + ":\n"
        "    try:\n"
        "        out[name] = m.version(name)\n"
        "    except Exception as problem:\n"
        "        out[name + '_error'] = type(problem).__name__\n"
        "print('NOBBLE_SOFTWARE=' + json.dumps(out))\n"
    )


def versions(timeout: int = 60) -> dict:
    """Installed versions in the environment that runs Boltz.

    The sentinel prefix is how `hwprobe` reads its own probe's output, and it
    is there because a pixi environment can print a warning on startup: the
    last line of stdout is not reliably the answer.
    """
    measured = {"measured_at": datetime.now(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")}
    python = paths.PY_BOLTZ
    if not python.exists():
        measured["status"] = f"no interpreter at {python}"
        return measured
    environment = dict(os.environ, KMP_DUPLICATE_LIB_OK="TRUE")
    try:
        done = subprocess.run(
            [str(python), "-c", _probe(PACKAGES)],
            capture_output=True, text=True, timeout=timeout, env=environment,
        )
    except Exception as problem:                        # noqa: BLE001
        measured["status"] = f"unreadable: {type(problem).__name__}"
        return measured
    for line in done.stdout.splitlines():
        if line.startswith("NOBBLE_SOFTWARE="):
            try:
                measured.update(json.loads(line.split("=", 1)[1]))
            except json.JSONDecodeError:
                measured["status"] = "unparseable probe output"
                return measured
            # The probe ran; that is not the same as it finding anything. A
            # package it could not resolve comes back as `<name>_error`, and
            # calling that "ok" made `summary()` read "model version
            # unavailable: ok", which is a status line contradicting itself.
            failed = sorted(key[: -len("_error")] for key in measured
                            if key.endswith("_error"))
            if failed:
                measured["status"] = (
                    "not installed in the Boltz environment: " + ", ".join(failed))
            else:
                measured["status"] = "ok"
            return measured
    measured["status"] = f"probe printed nothing (exit {done.returncode})"
    return measured


def summary(measured: dict | None = None) -> str:
    """One line for a provenance panel, or what is missing instead."""
    measured = measured if measured is not None else versions()
    if measured.get("boltz"):
        parts = [f"Boltz {measured['boltz']}"]
        if measured.get("torch"):
            parts.append(f"torch {measured['torch']}")
        return ", ".join(parts)
    return f"model version unavailable: {measured.get('status', 'unknown')}"


# What a campaign with no recorded version should say, which is not the same
# as what an unreadable probe should say. `summary()` answers "the probe ran
# here and this is what it found"; this answers "the campaign's own record
# says nothing", and the honest line for that is not a version measured now.
# The environment on this machine is probably the one that ran the jobs, and
# probably is not provenance (F185).
NOT_RECORDED = ("not recorded: this campaign was assembled before the version "
                "was captured, and the atlas build fills it in at publish")


def provenance_line(recorded: dict | None) -> str:
    """One line for a provenance report, from a campaign's own record.

    Separated from `tools/provenance.py` so it can be tested without running
    it. That script prints at module level and its atlas check rebuilds the
    whole bundle, so asserting on one line of its output cost seven seconds
    and a full rebuild per run (F192).

    Three cases, because they are three different claims: no record at all,
    a record carrying versions, and a record whose probe failed. The middle
    one is `summary()`, reused rather than reimplemented, with the `recorded`
    label appended when the atlas build filled the block in at publish time
    instead of the assembler recording it.
    """
    recorded = recorded or {}
    if not recorded:
        return NOT_RECORDED
    line = summary(recorded)
    label = recorded.get("recorded")
    if label:
        line = line + " (" + str(label) + ")"
    return line
