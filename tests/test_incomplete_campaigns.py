"""A failed assembly must not leave something that looks like a campaign.

Three directories named `design_20261104T0758…`, `…T0818…` and `…T0819…`
sat in `campaigns/`, each holding an empty `yaml/` and an empty `outputs/`
and nothing else. Every assembler creates those two subdirectories and then
does work that can raise, so a failure leaves the skeleton behind under a
campaign name, and a skeleton is indistinguishable from a campaign that ran
and produced no results.

`latest()` sorts by name and returns the newest match, so the newest
skeleton was "the latest design campaign". Nothing called `latest("design")`
yet, which is the only reason this had not caused a wrong answer: four of
the function's seven callers use what it returns without checking anything
further.

Two fixes, because there are two failures. An assembly that raises now
removes its own directory. A process killed between the mkdir and the
manifest cannot do that, so `latest()` also requires the completion marker,
which every assembler writes last (F57).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402
from nobble.execute import campaign as C  # noqa: E402


@pytest.fixture()
def campaigns(tmp_path, monkeypatch):
    """Redirect everything the helper writes, not only the campaigns.

    The failure record was added after these tests and escaped the first
    version of this fixture, which redirected CAMPAIGNS alone: four test
    failures were appended to the real manifest before anyone looked. A
    fixture that redirects some of a function's outputs is a fixture that
    silently stops covering the rest of them.
    """
    directory = tmp_path / "campaigns"
    directory.mkdir()
    monkeypatch.setattr(paths, "CAMPAIGNS", directory)
    monkeypatch.setattr(C.paths, "CAMPAIGNS", directory)
    monkeypatch.setattr(C, "FAILED_ASSEMBLIES",
                        tmp_path / "manifests" / "failed_assemblies.jsonl")
    return directory


def _complete(campaigns, name):
    directory = campaigns / name
    (directory / "yaml").mkdir(parents=True)
    (directory / "outputs").mkdir(parents=True)
    (directory / "queue.jsonl").write_text("{}\n")
    (directory / C.COMPLETION_MARKER).write_text("{}")
    return directory


def _skeleton(campaigns, name):
    """Exactly what the three real ones held."""
    directory = campaigns / name
    (directory / "yaml").mkdir(parents=True)
    (directory / "outputs").mkdir(parents=True)
    return directory


def test_a_skeleton_does_not_shadow_a_real_campaign(campaigns):
    """The hazard. The skeleton sorts last, so it was "the latest"."""
    real = _complete(campaigns, "design_20261104T024349Z")
    _skeleton(campaigns, "design_20261104T081927Z")
    assert C.latest("design") == real


def test_a_campaign_with_no_marker_is_not_the_latest(campaigns):
    _skeleton(campaigns, "design_20261104T081927Z")
    assert C.latest("design") is None


def test_a_queue_alone_is_not_enough(campaigns):
    """The marker is written last, after the queue and the YAMLs. A
    directory with a queue and no marker is an assembly that died part way
    through writing it, and the old guards tested the queue and then read
    the marker, so that case raised FileNotFoundError."""
    directory = campaigns / "design_20261104T081927Z"
    (directory / "yaml").mkdir(parents=True)
    (directory / "queue.jsonl").write_text("{}\n")
    assert C.latest("design") is None


def test_a_complete_campaign_is_still_found(campaigns):
    real = _complete(campaigns, "benchmark_20261103T192126Z")
    assert C.latest("benchmark") == real


def test_the_newest_complete_one_wins(campaigns):
    _complete(campaigns, "design_20261103T000000Z")
    newer = _complete(campaigns, "design_20261104T024349Z")
    assert C.latest("design") == newer


def test_a_failed_assembly_removes_its_own_directory(campaigns):
    with pytest.raises(RuntimeError, match="pocket"):
        with C.fresh_campaign("design") as directory:
            created = directory
            assert created.exists()
            raise RuntimeError("no pocket could be derived")
    assert not created.exists()
    assert list(campaigns.iterdir()) == []


def test_an_assembly_that_forgets_the_marker_is_also_removed(campaigns):
    """Returning without writing the manifest is the same failure wearing a
    success. The directory would hold a queue and no marker, which is the
    state `test_a_queue_alone_is_not_enough` describes."""
    with pytest.raises(RuntimeError, match=C.COMPLETION_MARKER):
        with C.fresh_campaign("design") as directory:
            created = directory
            (directory / "queue.jsonl").write_text("{}\n")
    assert not created.exists()


def test_a_successful_assembly_is_kept(campaigns):
    with C.fresh_campaign("design") as directory:
        (directory / "queue.jsonl").write_text("{}\n")
        (directory / C.COMPLETION_MARKER).write_text("{}")
    assert directory.exists()
    assert (directory / "yaml").is_dir()
    assert (directory / "outputs").is_dir()
    assert C.latest("design") == directory


def test_a_keyboard_interrupt_cleans_up_too(campaigns):
    """BaseException, not Exception: a run stopped with ctrl-c part way
    through an assembly is the most likely way to make one of these."""
    with pytest.raises(KeyboardInterrupt):
        with C.fresh_campaign("design") as directory:
            created = directory
            raise KeyboardInterrupt
    assert not created.exists()


def test_the_design_assembler_actually_uses_it(monkeypatch, campaigns):
    """The wiring, not the helper (F40). A failure inside the design
    assembler, at the step that failed for real, must leave nothing."""
    from nobble.design import assemble as A
    from nobble.execute import yaml_gen as Y

    def no_pocket(*args, **kwargs):
        raise RuntimeError("could not derive the pocket")

    monkeypatch.setattr(Y, "derive_pocket", no_pocket)
    monkeypatch.setattr(A.Y, "derive_pocket", no_pocket)

    with pytest.raises(RuntimeError):
        A.assemble("benchmark_888fd2c63e")
    assert not list(campaigns.glob("design_*")), (
        "the design assembler left a skeleton behind: "
        f"{[p.name for p in campaigns.glob('design_*')]}"
    )


def test_the_design_assembler_names_its_directory_the_same_way():
    """The helper stamps the directory now, so the assembler no longer
    carries its own copy of the format. A second copy is how two names
    drift apart."""
    source = (ROOT / "nobble" / "design" / "assemble.py").read_text()
    assert 'f"design_{stamp}"' not in source
    assert 'fresh_campaign("design")' in source


def test_the_stamp_format_is_written_once():
    """Three assemblers each carried their own copy of the timestamp
    format, and `latest()` matches directory names against TIMESTAMP. A
    copy drifting from that regex would not have failed anything: the
    campaign would simply have stopped being found, which is the same
    silence the skeletons produced."""
    import re

    sources = {
        path.name: path.read_text()
        for path in [
            ROOT / "nobble" / "execute" / "campaign.py",
            ROOT / "nobble" / "execute" / "corrected.py",
            ROOT / "nobble" / "design" / "assemble.py",
        ]
    }
    copies = {name: len(re.findall(r"%Y%m%dT%H%M%SZ", text))
              for name, text in sources.items() if "%Y%m%dT%H%M%SZ" in text}
    assert copies == {"campaign.py": 1}, (
        f"the stamp format is written in more than one place: {copies}"
    )


def test_every_assembler_builds_inside_the_helper():
    """The sweep, rather than the three sites I happened to look at. An
    assembler that creates its own campaign directory is one that can leave
    a skeleton behind."""
    offenders = {}
    for path in sorted((ROOT / "nobble").rglob("*.py")):
        text = path.read_text()
        if 'paths.CAMPAIGNS / campaign_id(' in text or 'paths.CAMPAIGNS / (' in text:
            if path.name != "campaign.py":
                offenders[str(path.relative_to(ROOT))] = "builds its own path"
        if 'f"design_{stamp}"' in text:
            offenders[str(path.relative_to(ROOT))] = "stamps its own name"
    assert not offenders, (
        f"assembler(s) not using fresh_campaign: {offenders}"
    )


def _records():
    return [json.loads(line) for line in
            C.FAILED_ASSEMBLIES.read_text().splitlines() if line.strip()]


def test_the_reason_is_recorded_before_the_directory_goes(campaigns):
    """Removing the litter without writing down why would be quieter than
    leaving it and no more informative. The three real skeletons carried no
    record, so their cause could only be guessed at afterwards."""
    with pytest.raises(RuntimeError):
        with C.fresh_campaign("design") as directory:
            (directory / "queue.jsonl").write_text("{}\n")
            raise RuntimeError("could not derive the pocket")

    (record,) = _records()
    assert record["campaign_id"] == directory.name
    assert record["error"] == "RuntimeError"
    assert "could not derive the pocket" in record["message"]
    assert "could not derive the pocket" in record["traceback"]
    assert "queue.jsonl" in record["contents"]
    assert record["failed_at"]


def test_the_records_accumulate(campaigns):
    """Appended, not rewritten. Three identical skeletons 20 minutes apart
    said more together than any one of them did."""
    for _ in range(3):
        with pytest.raises(RuntimeError):
            with C.fresh_campaign("design") as directory:
                raise RuntimeError("the same failure again")
    assert len(_records()) == 3


def test_a_successful_assembly_records_nothing(campaigns):
    with C.fresh_campaign("design") as directory:
        (directory / C.COMPLETION_MARKER).write_text("{}")
    assert not C.FAILED_ASSEMBLIES.exists()


def test_a_missing_marker_is_recorded_too(campaigns):
    with pytest.raises(RuntimeError):
        with C.fresh_campaign("design") as directory:
            (directory / "queue.jsonl").write_text("{}\n")
    (record,) = _records()
    assert C.COMPLETION_MARKER in record["message"]


def test_a_failed_record_does_not_mask_the_error(campaigns, monkeypatch):
    """The record is a diagnostic, not a dependency. If it cannot be
    written the assembly's own error is still what the caller sees."""
    monkeypatch.setattr(C, "FAILED_ASSEMBLIES",
                        campaigns / "nonexistent\x00dir" / "x.jsonl")
    with pytest.raises(RuntimeError, match="the real failure"):
        with C.fresh_campaign("design") as directory:
            raise RuntimeError("the real failure")
    assert not directory.exists()
