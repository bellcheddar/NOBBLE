"""Two functions named free_disk_gb, disagreeing by 7.4 per cent (F179).

`nobble/execute/runner.py` divides by 1e9 and the G5 gate compares the
result against `min_free_disk_gb = 50`, which is CLAUDE.md's "below 50 GB".
`tools/hwprobe.py` divided by 1024**3 and returned the answer under the same
name and the same `_gb` label, so it was gibibytes called gigabytes: on the
volume this project runs on, 37 GB out.

Nothing decided on the probe's figure, which is recorded in
`config/hardware.toml` and printed by the probe. It still mattered, because
that printed line is where a reader looks to find out how much room there
is, and I read it against the gate's and spent a few minutes believing 37 GB
had disappeared in half an hour.

Pinned rather than merged. The probe deliberately imports nothing from the
`nobble` package: it is Phase 0 and runs before the package is necessarily
usable, which is a property worth keeping. So there are still two
implementations, and this requires them to return the same number.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import hwprobe  # noqa: E402
from nobble import paths  # noqa: E402
from nobble.execute import runner  # noqa: E402


def test_the_probe_and_the_gate_measure_the_same_thing():
    probe = hwprobe.free_disk_gb(paths.ROOT)
    gate = runner.free_disk_gb(paths.ROOT)
    # Generous, because free space moves between the two calls and the probe
    # rounds to one decimal. A unit disagreement is 7.4 per cent, which on
    # any volume large enough to run this project is tens of gigabytes, so
    # the tolerance does not hide the thing being tested.
    assert abs(probe - gate) < 1.0, (
        f"the probe says {probe} GB and the gate {gate:.1f} GB. A gap this "
        "size is a unit disagreement, not two readings a moment apart."
    )


def test_both_are_decimal_gigabytes_as_CLAUDE_md_states_the_floor():
    """The gate's floor is written as GB, so GB is what it must be compared to."""
    floor = paths.thresholds()["gates"]["min_free_disk_gb"]
    assert floor == 50
    for module_path in (ROOT / "tools" / "hwprobe.py",
                        ROOT / "nobble" / "execute" / "runner.py"):
        body = module_path.read_text()
        found = re.search(r"def free_disk_gb.*?\n\n\n", body, re.S)
        assert found, f"{module_path.name} no longer defines free_disk_gb"
        code = re.sub(r'""".*?"""', "", found.group(0), flags=re.S)
        assert "1e9" in code, f"{module_path.name} is not dividing by 1e9"
        assert "1024" not in code, (
            f"{module_path.name} divides by a power of 1024, which gives "
            "gibibytes under a gigabyte name"
        )


def test_the_gate_itself_is_judged_in_those_units():
    """Belt and braces: a real reading against a real floor."""
    free = shutil.disk_usage(paths.ROOT).free / 1e9
    gate = runner.disk_gate(paths.ROOT)
    assert abs(gate["free_gb"] - free) < 1.0
    assert gate["floor_gb"] == 50
    assert gate["open"] is (free < 50)
