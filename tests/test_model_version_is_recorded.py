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


def test_every_assembler_records_it():
    """One per assembler, counted rather than pinned at two.

    This asserted exactly 2 and broke when a third assembler arrived for
    the Tier B arm, which is a test that fails when the thing it guards
    gets wider rather than when it gets wrong.
    """
    source = (ROOT / "nobble" / "execute" / "campaign.py").read_text()
    assemblers = [line for line in source.splitlines()
                  if line.startswith("def assemble_")]
    assert len(assemblers) >= 2, assemblers
    recorded = source.count('"software": software.versions(),')
    assert recorded == len(assemblers), (
        f"{len(assemblers)} assembler(s) and {recorded} recording the model "
        f"version: {assemblers}"
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


def test_the_provenance_line_says_the_version_or_why_there_is_none():
    """One line either way, never silence (F185), tested without running it.

    This used to run `tools/provenance.py` as a subprocess. That script
    prints at module level and its atlas check rebuilds the whole bundle, so
    asserting on one line of its output cost about seven seconds and a full
    rebuild on every suite run, and it wrote `validation.json` and
    `weights.json` into the campaign directory as a side effect. The line is
    a pure function now and the script calls it (F192).
    """
    assert software.provenance_line(None) == software.NOT_RECORDED
    assert software.provenance_line({}) == software.NOT_RECORDED

    recorded = {"boltz": "9.9.9", "torch": "8.8.8", "status": "ok"}
    assert software.provenance_line(recorded) == "Boltz 9.9.9, torch 8.8.8"

    # The atlas build's weaker claim carries its label through.
    labelled = dict(recorded, recorded="at publish, not at assembly")
    assert software.provenance_line(labelled) == (
        "Boltz 9.9.9, torch 8.8.8 (at publish, not at assembly)")

    # A record whose probe failed is a third case, not the first: the
    # campaign recorded something and what it recorded is a failure.
    failed = software.provenance_line({"status": "unreadable: TimeoutExpired"})
    assert failed.startswith("model version unavailable")
    assert failed != software.NOT_RECORDED


def test_the_report_prints_exactly_one_model_line_through_that_function():
    source = (ROOT / "tools" / "provenance.py").read_text()
    assert "software.provenance_line" in source
    assert source.count("model         ") == 1, (
        "the provenance report has more or fewer than one model line"
    )
    # And it must not have gone back to formatting the line itself, which is
    # how the two copies would drift.
    assert "detail +=" not in source


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
