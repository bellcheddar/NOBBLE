"""The deploy asks whether the bundle fits before it writes anything (F175).

`deploy.sh` rsyncs the published atlas with `--delete` and never asked how
much room was on the far side. At 25 MB the question did not arise; the
running campaign projects to 265 MB of structures, and rsync running out of
space part way through leaves a half-written atlas behind a live site.

This path cannot be exercised end to end here, because the only honest test
of it is a real deploy to a real droplet. So the arithmetic lives in
`tools/space_check.py` and is tested directly, and what the shell does with
the exit status is read out of the shell.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
import space_check  # noqa: E402

# The invocation, not the tool's name: deploy.sh mentions the name in a
# comment above the call, and anchoring an ordering test on the first
# mention compared against the comment rather than against the command.
CALL = "tools/space_check.py --free-kb"


def test_the_margin_is_configured_not_written_into_the_tool():
    """CLAUDE.md: thresholds come from config, never a cutoff in Python."""
    configured = paths.thresholds()["deploy"]["droplet_free_margin_mb"]
    assert isinstance(configured, int) and configured > 0
    source = (ROOT / "tools" / "space_check.py").read_text()
    # It must read the value, and must not carry one of its own. Checking
    # for the bare number would hit the `/ 1024` byte conversions, which is
    # how this test failed first time round.
    assert 'thresholds()["deploy"]["droplet_free_margin_mb"]' in source
    assert not re.search(r"margin_mb\s*(:\s*int\s*)?=\s*\d+", source), (
        "space_check.py carries a default margin of its own, which can drift "
        "from config/thresholds.toml"
    )


def test_a_bundle_that_fits_with_room_to_spare_passes():
    verdict = space_check.judge(free_kb=20_000_000, bundle_kb=260_000, margin_mb=1024)
    assert verdict["fits"]
    assert verdict["bundle_mb"] == pytest.approx(253.9, abs=0.1)


def test_a_bundle_that_fits_but_eats_the_margin_is_refused():
    """The failure this exists for: room for the bundle, none for anything else."""
    margin_kb = 1024 * 1024
    verdict = space_check.judge(free_kb=260_000 + margin_kb - 1,
                                bundle_kb=260_000, margin_mb=1024)
    assert not verdict["fits"], (
        "a bundle that leaves less than the margin free was accepted; the "
        "margin is what the droplet needs to keep working, not slack"
    )


def test_the_boundary_is_inclusive():
    margin_kb = 1024 * 1024
    assert space_check.judge(free_kb=260_000 + margin_kb,
                             bundle_kb=260_000, margin_mb=1024)["fits"]


def test_it_compares_the_whole_bundle_not_the_difference():
    """`--delete` removes the old copy after the transfer, so the peak is both.

    A check that compared only the growth would pass on a droplet with room
    for 1 MB of change and none for the 265 MB that briefly sits beside the
    old atlas.
    """
    assert not space_check.judge(free_kb=30_000, bundle_kb=260_000,
                                 margin_mb=0)["fits"]


def test_bundle_kilobytes_counts_every_file_and_rounds_up(tmp_path):
    (tmp_path / "structures").mkdir()
    (tmp_path / "a.json").write_bytes(b"x" * 100)          # rounds to 1 KiB
    (tmp_path / "structures" / "b.cif").write_bytes(b"x" * 5000)   # 5 KiB
    assert space_check.bundle_kilobytes(tmp_path) == 1 + 5


def test_it_exits_nonzero_so_the_shell_stops(tmp_path):
    (tmp_path / "f.json").write_bytes(b"x" * 1024)
    tool = ROOT / "tools" / "space_check.py"
    tight = subprocess.run(
        [sys.executable, str(tool), "--free-kb", "1000",
         "--bundle", str(tmp_path), "--margin-mb", "1024"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert tight.returncode == 3, tight.stderr
    assert "half-written atlas" in tight.stderr

    roomy = subprocess.run(
        [sys.executable, str(tool), "--free-kb", "20000000",
         "--bundle", str(tmp_path), "--margin-mb", "1024"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert roomy.returncode == 0, roomy.stderr


def test_a_missing_bundle_is_refused_rather_than_read_as_empty(tmp_path):
    """An empty bundle fits anywhere, which is the wrong answer."""
    tool = ROOT / "tools" / "space_check.py"
    done = subprocess.run(
        [sys.executable, str(tool), "--free-kb", "20000000",
         "--bundle", str(tmp_path / "nothing-here")],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert done.returncode == 2
    assert "no bundle" in done.stderr


def test_deploy_runs_the_check_before_it_sends_anything():
    script = (ROOT / "deploy" / "deploy.sh").read_text()
    assert CALL in script
    checked = script.index(CALL)
    for sent in ("rsync -rlpt --delete \\", "deploy/atlas/ \"$DROPLET_SSH"):
        assert script.index(sent) > checked, (
            f"the space check runs after `{sent[:24]}`, which has already "
            "written to the droplet"
        )


def test_deploy_refuses_rather_than_guessing_when_df_says_nothing():
    """An unreadable `df` must not read as plenty of room."""
    script = (ROOT / "deploy" / "deploy.sh").read_text()
    assert 'if [[ -z "${FREE_KB:-}" ]]; then' in script
    guard = script.index('if [[ -z "${FREE_KB:-}" ]]; then')
    assert script.index(CALL) > guard
