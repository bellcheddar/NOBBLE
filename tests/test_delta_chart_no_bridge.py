"""An absent bridge is not a bridge percentile of zero.

The Delta view is the headline view: a Plotly scatter of Delta-ipTM against
bridge percentile, which is spec 4.1's primary signal. A pair with no
measurable bridge was plotted at `bridge_percentile === null ? 0`, which puts
it on the axis beside pairs with a genuine weak bridge, and the hover said
"bridge percentile 0.0": a stated number for a measurement that does not
exist.

It is not hypothetical. CDK12's ten seeds all reject as `single_chain`,
meaning the glue touched one chain rather than two. That is not a weak
bridge, it is no bridge, and the campaign table already says so by blanking
the cell and naming the reject reason. The chart did not, and the chart is
the one the spec calls the headline.

F115 established that the computation cannot report a confident zero, because
BINMAN's bridging criterion rejects a non-finite dSASA. This is the same
hazard arriving by presentation instead of by arithmetic (F116).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEMPLATE = ROOT / "nobble" / "app" / "templates" / "delta.html"


def _source() -> str:
    return TEMPLATE.read_text()


def test_a_null_percentile_is_not_plotted_at_zero():
    source = _source()
    assert "p.bridge_percentile === null ? 0" not in source, (
        "an absent bridge is plotted on the axis again"
    )
    assert "hasBridge(p) ? p.bridge_percentile : NO_BRIDGE_Y" in source


def test_the_band_is_outside_the_percentile_range():
    """Below zero, so it cannot be read as a percentile at all."""
    source = _source()
    match = re.search(r"const NO_BRIDGE_Y = (-?\d+(?:\.\d+)?)", source)
    assert match, "NO_BRIDGE_Y is gone"
    assert float(match.group(1)) < 0, match.group(1)

    axis = re.search(r"range: \[(-?\d+(?:\.\d+)?), (\d+)\]", source)
    assert axis, "the y-axis range is gone"
    assert float(axis.group(1)) < float(match.group(1)), (
        "the axis range does not reach the no-bridge band, so those points "
        "would be clipped out of the headline view entirely"
    )


def test_the_band_is_labelled_on_the_axis():
    """So its meaning does not have to be guessed from a hover."""
    source = _source()
    assert "tickvals: [NO_BRIDGE_Y" in source
    assert "ticktext: ['none'" in source


def test_the_hover_says_so_rather_than_quoting_a_number():
    source = _source()
    assert "'bridge percentile %{y:.1f}<br>'" not in source, (
        "the hover quotes the plotted position again, which is the band "
        "rather than a percentile"
    )
    assert "%{customdata[8]}" in source
    assert "'no bridge in any seed'" in source


def test_the_customdata_index_matches_what_is_pushed():
    """A hovertemplate indexes customdata positionally, so adding a field in
    the wrong place silently relabels every one after it."""
    source = _source()
    block = source[source.index("customdata: rows.map"):source.index("mode: 'markers'")]

    # Counted by splitting on top-level commas, not by lines: the first line
    # holds three entries, which is how the first version of this test
    # convinced itself there were seven.
    depth, current, entries = 0, "", []
    for character in block[block.index("[") + 1:block.rindex("]")]:
        if character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
        if character == "," and depth == 0:
            entries.append(current.strip())
            current = ""
        else:
            current += character
    if current.strip():
        entries.append(current.strip())
    entries = [entry for entry in entries if entry]

    assert len(entries) == 9, [entry[:40] for entry in entries]
    assert "bridgeText(p)" in entries[-1], entries[-1]

    # And the hovertemplate reaches exactly that far and no further.
    import re as _re

    indices = {int(found) for found in
               _re.findall(r"customdata\[(\d+)\]", source)}
    assert indices == set(range(9)), sorted(indices)


def test_the_table_and_the_chart_agree_about_what_absent_means():
    """The campaign table blanks the cell and names the reject reason. Both
    surfaces now refuse to call it zero, which is the point: a reader moving
    between them should not get two answers."""
    campaign = (ROOT / "nobble" / "app" / "templates" / "campaign.html").read_text()
    assert "bridge_reject_reasons" in campaign
    assert "no bridge:" in campaign
    assert "no bridge in any seed" in _source()


def test_the_script_still_parses():
    """A template that emits broken JavaScript still returns 200, and the
    chart simply does not draw."""
    import shutil
    import subprocess

    if not shutil.which("node"):
        import pytest

        pytest.skip("node is not available")

    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", _source(), re.S)
    assert scripts, "no inline script in delta.html"
    body = max(scripts, key=len)
    body = re.sub(r"\{\{.*?\}\}", "null", body, flags=re.S)
    body = re.sub(r"\{%.*?%\}", "", body, flags=re.S)
    checked = ROOT / "qc" / "_delta_check.js"
    checked.write_text(body)
    try:
        result = subprocess.run(["node", "--check", str(checked)],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr[-400:]
    finally:
        checked.unlink(missing_ok=True)
