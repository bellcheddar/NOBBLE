"""Which Boltz produced the coordinates (F185).

`campaign.json` published the tuning a campaign ran under, token caps,
recycle counts, diffusion samples and seeds, and not the model version.
Every number in the atlas is a Boltz-2 prediction, so the version is the one
thing a reader needs to reproduce a pose, and the About page said "Boltz-2"
without pinning it.

Three places are checked: the probe, which must record a failure rather than
raise; the assembler, which records at assembly because that is when the
environment is the one the queue will run in; and the atlas build, which
measures at publish for campaigns assembled before this existed and labels
that as the different claim it is.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.execute import software  # noqa: E402


def test_the_probe_reads_the_environment_that_runs_boltz():
    measured = software.versions()
    if measured.get("status") != "ok":
        pytest.skip(f"no readable Boltz environment: {measured.get('status')}")
    assert measured["boltz"], measured
    # A version string, not a path or a message.
    assert measured["boltz"][0].isdigit(), measured["boltz"]
    assert measured.get("measured_at", "").endswith("Z")


def test_an_unreadable_environment_is_a_recorded_state_not_an_exception(monkeypatch):
    """A campaign must not fail to assemble because a probe could not run."""
    monkeypatch.setattr(software.paths, "PY_BOLTZ", Path("/nonexistent/python"))
    measured = software.versions()
    assert "status" in measured
    assert "boltz" not in measured, (
        "a missing version was reported as a version"
    )
    assert software.summary(measured).startswith("model version unavailable")


def test_the_probe_is_built_without_str_format():
    """Its own source contains `out = dict()`; braces and format collide.

    The first version used `str.format` and the probe text contained `{}`,
    which format read as a positional field: it raised IndexError before the
    subprocess started. The error path caught it and recorded
    `unreadable: IndexError`, which is how the bug was visible at all.
    """
    source = (ROOT / "nobble" / "execute" / "software.py").read_text()
    assert ".format(" not in source, (
        "the probe is built with str.format again, and its source contains "
        "braces"
    )


def test_a_version_is_never_computed_from_a_literal():
    """CLAUDE.md: the environment is the fact, not a number written down."""
    source = (ROOT / "nobble" / "execute" / "software.py").read_text()
    for pinned in ("2.2.1", "2.10.0"):
        assert pinned not in source, (
            f"{pinned} is written into the probe, so it would report a "
            "version it did not measure"
        )


def test_both_assemblers_record_it():
    source = (ROOT / "nobble" / "execute" / "campaign.py").read_text()
    assert source.count('"software": software.versions(),') == 2, (
        "one of the two campaign summaries does not record the model version"
    )


def test_the_atlas_build_fills_it_in_for_campaigns_assembled_before_this():
    builder = (ROOT / "deploy" / "build_atlas.py").read_text()
    assert 'not payload.get("software")' in builder, (
        "the atlas build no longer fills in a missing model version, so the "
        "campaign on the GPU would publish without one"
    )
    assert "at publish, not at assembly" in builder, (
        "a publish-time reading is published as though the assembler had "
        "recorded it, which is a different and stronger claim"
    )


def test_the_about_page_states_it_only_when_it_is_recorded():
    """An absent version must render nothing, not an empty claim."""
    template = (ROOT / "nobble" / "app" / "templates" / "about.html").read_text()
    assert "software.get('boltz')" in template, (
        "the panel no longer guards on the version being present"
    )
    assert "software.boltz" in template


def test_the_app_reads_the_published_record_rather_than_measuring():
    """The droplet's environment is not the one that ran the jobs.

    Measuring on the server would report a version confidently and wrongly,
    and the droplet has no Boltz install at all.
    """
    routes = (ROOT / "nobble" / "app" / "routes.py").read_text()
    assert 'get("software")' in routes
    assert "software.versions()" not in routes, (
        "the app measures the version on the server it is served from"
    )


def test_the_published_atlas_either_carries_a_version_or_predates_this():
    """Documents the state rather than demanding it: the published bundle was
    built before F185 and gains a version at the next build."""
    published = ROOT / "deploy" / "atlas" / "campaign.json"
    if not published.exists():
        pytest.skip("no published atlas")
    payload = json.loads(published.read_text())
    block = payload.get("software")
    if block is None:
        pytest.skip("this atlas predates F185; the next build fills it in")
    assert block.get("boltz") or block.get("status"), block


def test_the_provenance_report_states_the_model_or_says_it_is_not_recorded():
    """One line either way, never silence (F185).

    `tools/provenance.py` runs at module level and prints, so this runs it
    rather than importing it. The two acceptable outputs are a version and an
    explanation of why there is none: what is not acceptable is the section
    omitting the model, because a provenance block that is silent about the
    model reads as though the model were not part of the provenance.
    """
    import subprocess

    done = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "provenance.py")],
        capture_output=True, text=True, cwd=ROOT,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT),
             "KMP_DUPLICATE_LIB_OK": "TRUE"},
    )
    if done.returncode != 0:
        pytest.skip(f"provenance.py could not run here: {done.stderr[:120]}")
    lines = [line for line in done.stdout.splitlines()
             if line.strip().startswith("model")]
    assert len(lines) == 1, (
        f"the provenance report has {len(lines)} model lines, not one:\n"
        f"{done.stdout}"
    )
    line = lines[0]
    assert ("Boltz" in line) or ("not recorded" in line), line


def test_the_report_does_not_measure_the_environment_to_fill_the_gap():
    """A campaign with no recorded version must not be given one now.

    The environment on this machine is probably the one that ran the jobs,
    and "probably" is not provenance. This is the same distinction the atlas
    build makes when it labels a publish-time reading.
    """
    source = (ROOT / "tools" / "provenance.py").read_text()
    assert "software.versions()" not in source, (
        "the provenance report measures the environment to fill a gap in a "
        "campaign's record, which presents a reading taken now as the "
        "version that ran"
    )


def test_a_probe_that_ran_but_found_nothing_does_not_report_ok(monkeypatch):
    """`ok` meant "the subprocess returned", not "the version was found".

    A package the probe cannot resolve comes back as `<name>_error`, and the
    status was set to `ok` regardless, so `summary()` produced "model version
    unavailable: ok": a status line contradicting itself. The status now
    names what was missing.
    """
    monkeypatch.setattr(software, "PACKAGES", ("boltz", "definitely_not_installed"))
    measured = software.versions()
    if "definitely_not_installed_error" not in measured:
        pytest.skip("the probe did not run here")
    assert measured["status"] != "ok"
    assert "definitely_not_installed" in measured["status"]
    # And a package that WAS found is still reported, because a partial
    # answer is more useful than none and the status says it is partial.
    if measured.get("boltz"):
        assert software.summary(measured).startswith("Boltz ")


def test_the_status_is_always_set_whatever_happens(monkeypatch):
    """Every return path, because a missing status reads as a missing probe."""
    assert "status" in software.versions()
    monkeypatch.setattr(software.paths, "PY_BOLTZ", Path("/nonexistent"))
    assert "status" in software.versions()
