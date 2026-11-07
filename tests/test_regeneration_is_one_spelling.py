"""One spelling of how a YAML is built, and a way to correct from code.

`tools/rerun_pair.py` corrects a pair by copying a known-good YAML from
another campaign. That works for F47, whose corrected YAML exists elsewhere,
and cannot work for F262, whose ternary YAMLs were written without their glue
by an assembler that was wrong everywhere: the correct file has never existed
on disk in any campaign, so there is nothing to copy.

The tool's own comment said the right fix was to factor the emission path out
so one pair can be regenerated in place, and deferred it as something not to
do while a long run was reading those files. It is factored out now:
`campaign.document_for` builds the document, `campaign._pocket_for_pair`
resolves the pocket, and `assemble_campaign` and `campaign.regenerate_pair`
both call them, so there is no second spelling to drift (F265).

The check that matters is that the refactor changed nothing: regenerating the
main campaign's YAMLs produces byte-identical text for every job except the
five F262 corrects.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _campaign() -> Path | None:
    from nobble.execute.campaign import latest

    found = latest("campaign")
    return Path(found) if found else None


def _on_disk(campaign: Path) -> dict[str, Path]:
    out = {}
    for line in (campaign / "queue.jsonl").read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["job_id"]] = Path(row["yaml"])
    return out


def test_regenerating_a_clean_pair_reproduces_its_yaml_exactly():
    """The refactor's whole claim, on a pair no fix has touched.

    A pair whose YAML regenerates byte-identically is evidence that
    `document_for` and the assembler agree. A pair chosen because it differs
    would prove the opposite of what this needs.
    """
    campaign = _campaign()
    if campaign is None:
        pytest.skip("no campaign assembled")
    from nobble.execute.campaign import regenerate_pair

    on_disk = _on_disk(campaign)
    pair = "scr_bench04_IKZF1_CRBN"
    fresh = regenerate_pair(pair)
    if not fresh:
        pytest.skip(f"{pair} is not in the current manifest")
    compared = 0
    for job_id, text in fresh.items():
        path = on_disk.get(job_id)
        if path is None or not path.exists():
            continue
        assert text == path.read_text(), (
            f"{job_id} regenerates differently from the file the campaign "
            "ran, so the assembler and document_for disagree")
        compared += 1
    assert compared >= 10, f"only compared {compared} job(s)"


def test_the_f262_pair_regenerates_with_its_glue():
    """And the pair a fix has touched differs, in exactly its ternary arm.

    Five ternary jobs and no binary ones: the binary arm never carried a
    ligand and should not start now.
    """
    campaign = _campaign()
    if campaign is None:
        pytest.skip("no campaign assembled")
    from nobble.execute.campaign import regenerate_pair

    on_disk = _on_disk(campaign)
    fresh = regenerate_pair("scr_bench03_BRD4_CRBN")
    if not fresh:
        pytest.skip("the pair is not in the current manifest")
    differ = sorted(job_id for job_id, text in fresh.items()
                    if on_disk.get(job_id) and on_disk[job_id].exists()
                    and on_disk[job_id].read_text() != text)
    if not differ:
        pytest.skip("the campaign on disk has been corrected, so this has "
                    "served out")
    assert all("__ternary__" in job_id for job_id in differ), differ
    assert len(differ) == 5, differ
    for job_id in differ:
        assert "ligand:" in fresh[job_id], (
            f"{job_id} regenerates still without its glue")


def test_a_conditioned_job_with_no_pocket_is_omitted_from_both():
    """The assembler drops and counts them, so regeneration must too.

    Otherwise a caller comparing the two would find jobs in the regeneration
    that the campaign never ran and read them as corrections.
    """
    campaign = _campaign()
    if campaign is None:
        pytest.skip("no campaign assembled")
    from nobble.execute.campaign import regenerate_pair

    on_disk = _on_disk(campaign)
    fresh = regenerate_pair("bench03_BRD4_CRBN")
    if not fresh:
        pytest.skip("the pair is not in the current manifest")
    extra = sorted(set(fresh) - set(on_disk))
    assert not extra, (
        f"regeneration emits {extra}, which the campaign does not hold: a "
        "conditioned job with no pocket is dropped by the assembler and must "
        "be dropped here")


def test_regenerate_mode_refuses_when_nothing_would_change():
    """F146's guard, by the thing it is about rather than by its proxy.

    A known-good reference is a proxy for "the input will change". With
    --regenerate the direct test is available, and it has to refuse in the
    same case: identical text means clearing the results would re-run the
    same input.
    """
    import importlib.util
    import subprocess

    campaign = _campaign()
    if campaign is None:
        pytest.skip("no campaign assembled")
    out = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "rerun_pair.py"),
         "scr_bench04_IKZF1_CRBN", "--campaign", str(campaign),
         "--regenerate"],
        capture_output=True, text=True, cwd=ROOT,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT),
             "KMP_DUPLICATE_LIB_OK": "TRUE"}, timeout=600)
    if "is not in" in out.stderr:
        pytest.skip("the pair is not in this campaign")
    assert out.returncode == 2, (out.returncode, out.stdout, out.stderr)
    assert "byte-identical" in out.stderr, out.stderr


def test_the_source_has_one_build_yaml_call_for_the_campaign_path():
    """Structural, so a second spelling cannot creep back in.

    `assemble_campaign` used to call `Y.build_yaml` directly; it now goes
    through `document_for`, and so does `regenerate_pair`. A third caller
    building its own document is the drift this is here to prevent.
    """
    import ast

    source = (ROOT / "nobble" / "execute" / "campaign.py").read_text()
    tree = ast.parse(source)
    callers = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for inner in ast.walk(node):
            if (isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr == "build_yaml"):
                callers.append(node.name)
    # The benchmark and Tier B assemblers have their own loops, which is a
    # separate question from this one; what matters is that the main
    # campaign's path is not duplicated.
    assert "document_for" in callers, callers
    assert "assemble_campaign" not in callers, (
        "assemble_campaign builds its own document again, so regenerate_pair "
        f"and the assembler can now drift: {callers}")
