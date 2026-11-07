"""The command the chain tells you to run must do something.

`tools/run_chain.sh` refuses at stage 2 with "no main campaign assembled: run
nobble.execute.campaign first". The module had no `__main__`, so that command
printed nothing and exited 0: an operator following the advice would see
success, re-run the chain and meet the same refusal (F296).

It is now an entry point, and creating a campaign needs `--apply`, because
`assemble_campaign` writes a new `campaigns/campaign_<stamp>` directory and
both the chain and `tools/status.sh` select the newest complete one. An
accidental run would make an empty campaign "the latest" and point the
remaining stages at it, which is the hazard F265's comment named.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str):
    env = {**os.environ, "PYTHONPATH": str(ROOT), "KMP_DUPLICATE_LIB_OK": "TRUE"}
    return subprocess.run([sys.executable, "-m", "nobble.execute.campaign",
                           *args], capture_output=True, text=True, cwd=ROOT,
                          env=env, timeout=600)


def _campaigns() -> int:
    return len(list((ROOT / "campaigns").glob("campaign_*")))


def test_the_bare_command_says_something():
    """Exit 0 with no output is the failure this exists to prevent."""
    out = _run()
    assert out.returncode == 0, out.stderr[-500:]
    assert out.stdout.strip(), (
        "the command printed nothing: the module has no entry point again")


def test_nothing_is_created_without_apply():
    before = _campaigns()
    out = _run("--fresh")
    assert out.returncode == 0, out.stderr[-500:]
    assert "Nothing written" in out.stdout, out.stdout
    assert _campaigns() == before, (
        "a campaign was assembled without --apply, so an accidental run "
        "would become the campaign the chain targets")


def test_the_help_names_the_flag_that_writes():
    out = _run("--help")
    assert out.returncode == 0, out.stderr[-400:]
    assert "--apply" in out.stdout, out.stdout


def test_the_chain_still_points_at_this_command():
    """If the message changes, this test should be the thing that notices."""
    text = (ROOT / "tools" / "run_chain.sh").read_text()
    assert "nobble.execute.campaign" in text, (
        "run_chain.sh no longer names the assembly command, so this test is "
        "checking a command nothing recommends")


def test_the_module_has_an_entry_point_at_all():
    """Asserted on the source, because the bare run cannot tell an empty
    module from a quiet one."""
    import re

    source = (ROOT / "nobble" / "execute" / "campaign.py").read_text()
    assert re.search(r'^if __name__ == "__main__":', source, re.M), (
        "campaign.py has no __main__ block")
