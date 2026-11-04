"""The best-window pLDDT search decides Tier B membership.

spec 3.3 filters receptors on mean pLDDT, and `summary` reports both the
whole-model mean and the best 200-residue window. The window matters
because a long protein with one well-ordered domain and a lot of
disorder has a poor whole-model mean and a good domain: judging it on the
whole would reject exactly the receptors worth running.

The search is a rolling sum with 1-based reporting, which is the shape
that goes wrong by one and still returns a plausible number. The module
had no test. These use a constructed profile, so no AlphaFold model is
needed and the expected answer is known rather than observed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.curate import plddt


def _summary(profile, monkeypatch) -> dict:
    monkeypatch.setattr(plddt, "plddt_profile", lambda accession: tuple(profile))
    return plddt.summary("TEST")


def test_a_short_model_reports_the_whole_thing_as_its_window(monkeypatch):
    """Below the window length there is nothing to slide."""
    result = _summary([90.0] * 50, monkeypatch)
    assert result["status"] == "ok"
    assert result["residues"] == 50
    assert result["mean_plddt"] == 90.0
    assert result["best_window_mean_plddt"] == 90.0
    assert result["best_window"] == [1, 50]


def test_the_window_finds_an_ordered_domain_inside_a_disordered_protein(monkeypatch):
    """The case the window exists for: 200 good residues buried in noise.
    Reported 1-based and inclusive, so a domain at positions 301 to 500
    must come back as [301, 500] and not [300, 499] or [302, 501]."""
    profile = [20.0] * 300 + [95.0] * 200 + [20.0] * 300
    result = _summary(profile, monkeypatch)

    assert result["residues"] == 800
    assert result["best_window"] == [301, 500], result["best_window"]
    assert result["best_window_mean_plddt"] == 95.0
    # The whole-model mean would have rejected this receptor outright.
    assert result["mean_plddt"] < 50


def test_the_window_at_the_very_start_and_the_very_end(monkeypatch):
    """Both edges, because a rolling sum typically fails at one of them."""
    start = _summary([95.0] * 200 + [10.0] * 300, monkeypatch)
    assert start["best_window"] == [1, 200], start["best_window"]

    end = _summary([10.0] * 300 + [95.0] * 200, monkeypatch)
    assert end["best_window"] == [301, 500], end["best_window"]
    assert end["best_window"][1] == end["residues"]


def test_an_unreadable_or_absent_model_reports_rather_than_raises(monkeypatch):
    """Tier B selection runs over hundreds of accessions, so one missing
    model must not stop the pass. It reports a status instead."""
    monkeypatch.setattr(plddt, "plddt_profile", lambda a: ())
    empty = plddt.summary("NOMODEL")
    assert empty["status"] == "no_model"
    assert empty["mean_plddt"] is None

    def _boom(accession):
        raise OSError("file is not there")

    monkeypatch.setattr(plddt, "plddt_profile", _boom)
    broken = plddt.summary("BROKEN")
    assert broken["status"].startswith("unreadable: OSError")
    assert broken["best_window_mean_plddt"] is None


def test_alphafold_writes_one_confidence_per_residue():
    """The invariant the CA preference rests on (F155).

    `plddt_profile` takes the CA's B-factor, falling back to the residue's
    first atom. On AlphaFold data those are the same number, because one
    per-residue confidence is written into every atom, so removing the
    preference changes nothing and the mutation sweep could not catch it.

    Pinned rather than argued. If AFDB ever ships genuine per-atom
    confidence this fails, which is the moment the preference stops being a
    no-op and starts deciding the profile.

    Sampled with a fixed seed: 20,279 models is too many to read in a test
    and one is too few to call an invariant.
    """
    import random

    import gemmi

    from nobble.curate import plddt as plddt_module

    models = sorted(plddt_module.AFDB_CACHE.glob("afdb_cif_*.bin"))
    if len(models) < 5:
        pytest.skip("no cached AlphaFold models on this checkout")
    random.Random(20261104).shuffle(models)
    residues = disagreeing = without_ca = ca_first = 0
    for path in models[:12]:
        try:
            structure = gemmi.read_structure(
                str(path), format=gemmi.CoorFormat.Mmcif)
        except Exception:                               # noqa: BLE001
            continue
        for chain in structure[0]:
            for residue in chain:
                residues += 1
                names = [atom.name for atom in residue]
                if "CA" not in names:
                    without_ca += 1
                elif names[0] == "CA":
                    ca_first += 1
                if len({round(atom.b_iso, 6) for atom in residue}) > 1:
                    disagreeing += 1
    assert residues > 1000, f"only {residues} residues sampled"
    assert disagreeing == 0, (
        f"{disagreeing} of {residues} residues have atoms that disagree "
        "about pLDDT, so which atom the profile reads now decides the number"
    )
    # The other two halves of why it is a no-op: the fallback never fires,
    # and the preference always has something to prefer.
    assert without_ca == 0, f"{without_ca} residues have no CA atom"
    assert ca_first == 0, (
        f"{ca_first} residues already have CA first, which is not a problem "
        "and does mean this test no longer describes the data it was written "
        "against"
    )


def test_a_cached_model_actually_reads(tmp_path):
    """The failure the profile's docstring is about (F155).

    BINMAN's fetcher stores every cached body under a `.bin` suffix, and
    gemmi infers format from the extension: without the explicit
    `CoorFormat.Mmcif` it raises "Unknown format" on a perfectly good mmCIF.
    That was caught silently once and turned 20,279 usable models into a
    uniform "no model" answer.

    The mutation sweep found no test behind it either, which is how this
    came to be written: a test that reads a model with gemmi directly, as
    the invariant check above does, passes the format itself and so cannot
    see the bug. This goes through `plddt_profile`.
    """
    from nobble.curate import plddt as plddt_module

    models = sorted(plddt_module.AFDB_CACHE.glob("afdb_cif_*.bin"))
    if not models:
        pytest.skip("no cached AlphaFold models on this checkout")
    accession = models[0].name.removeprefix("afdb_cif_").removesuffix(".bin")

    profile = plddt_module.plddt_profile(accession)
    assert profile, (
        f"{accession} is cached and read as no residues at all, which is "
        "what an inferred format does to a .bin body"
    )
    assert all(0.0 <= value <= 100.0 for value in profile), (
        "pLDDT is a percentage; these are not in range, so the B-factor "
        "column is not what was read"
    )

    # And through the caller, which swallows the exception into a status
    # rather than raising: the uniform "no model" answer was that status,
    # reported 20,279 times.
    outcome = plddt_module.summary(accession)
    assert outcome["status"] != "unreadable", outcome
    assert outcome["residues"] == len(profile)
    assert outcome["mean_plddt"] is not None
