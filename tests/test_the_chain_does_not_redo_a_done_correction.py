"""The chain used the one spelling of the correction without the guard (F302).

`tools/corrections.sh` has known since F267 that both underlying operations
clear results, so it has to decide whether there is anything left to correct,
and it reads that off a rehearsal because the exit code cannot carry it.
`tools/run_chain.sh` did not use it. It called
`rerun_pair.py bench02_BRD4_VHL --apply` directly, every start,
unconditionally.

On the 2026-11-07 restart, forty minutes after the same fifteen jobs had been
corrected and re-run, that stage printed "corrected 0 YAML(s) from a
known-good campaign" and then "removed 15 cached output directory/ies": an
hour of GPU on every chain start to arrive back where it started, with the
correct results dropped first. F267's own comment had predicted the cost to
the hour.

Two fixes, because the duplicate spelling is the cause and the missing guard
is the mechanism. The chain now goes through `corrections.sh`, which also
covers scr_bench03 as that stage never did; and the reference path of
`rerun_pair.py` refuses on its own when nothing needs correcting, so any
caller gets it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

SCI = ROOT / ".." / "BINMAN" / ".pixi" / "envs" / "default" / "bin" / "python"


def _code_lines(script: Path) -> list[str]:
    """The script's lines with comments and blanks removed.

    The first version of the test below asserted that the string
    "rerun_pair.py bench02_BRD4_VHL" does not appear in `run_chain.sh`, and
    it failed on the comment I had just written there explaining what the
    stage used to do. That is F296's slip again, a text check defeated by my
    own prose, so the check reads code rather than text.
    """
    out = []
    for line in script.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append(stripped.split(" #")[0])
    return out


def test_the_chain_corrects_through_the_guarded_script():
    """Not through rerun_pair.py, whose reference path clears regardless."""
    chain = ROOT / "tools" / "run_chain.sh"
    code = _code_lines(chain)
    assert any("tools/corrections.sh --apply" in line for line in code)
    offenders = [line for line in code if "rerun_pair.py" in line]
    assert not offenders, (
        "the chain calls rerun_pair directly again, bypassing the guard that "
        f"knows when the correction has already landed: {offenders}"
    )


def test_the_chain_does_not_refresh_twice():
    """corrections.sh refreshes at the end and the chain's next stage
    refreshes too, which scores and rebuilds the atlas for nothing."""
    chain = (ROOT / "tools" / "run_chain.sh").read_text()
    assert "--no-refresh" in chain


def test_the_no_refresh_flag_skips_the_refresh():
    script = (ROOT / "tools" / "corrections.sh").read_text()
    assert 'NO_REFRESH' in script
    assert "refresh: skipped on request" in script


def test_the_applied_message_is_not_applied_one():
    """`${APPLY:+applied}${APPLY:-rehearsed}` printed "applied1", because the
    second expansion falls back only when APPLY is empty and APPLY is "1"."""
    script = (ROOT / "tools" / "corrections.sh").read_text()
    assert "${APPLY:+applied}${APPLY:-rehearsed}" not in script
    assert "corrections applied with no refusal" in script


def test_an_unknown_argument_is_refused():
    """Adding a second flag by looping over "$@" makes a typo silent unless
    the loop says otherwise."""
    result = subprocess.run(["bash", str(ROOT / "tools" / "corrections.sh"),
                             "--aply"],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 2
    assert "unknown argument" in result.stderr


def _campaign(tmp_path: Path, *, folded: str,
              with_reference: bool = True) -> Path:
    """A one-job campaign whose YAML is already correct.

    `with_reference` writes a second campaign holding one copy of the same
    job's YAML, because F146 refuses to clear results for a job with no
    known-good reference and that refusal fires before the one under test.
    """
    import numpy as np

    campaign = tmp_path / "campaign_x"
    (campaign / "yaml").mkdir(parents=True)
    job_id = "pairA__binary__unconstrained__seed1"
    yaml_path = campaign / "yaml" / f"{job_id}.yaml"
    yaml_path.write_text("sequences:\n- protein:\n    id: P\n"
                         "    sequence: PVDVEALGLHDYCDI\n")
    (campaign / "queue.jsonl").write_text(
        json.dumps({"job_id": job_id, "pair_id": "pairA",
                    "yaml": str(yaml_path)}) + "\n")
    for name in ("state.jsonl", "results.jsonl", "scores.jsonl"):
        (campaign / name).write_text(
            json.dumps({"job_id": job_id, "pair_id": "pairA",
                        "status": "done"}) + "\n")

    structures = (campaign / "outputs" / job_id / f"boltz_results_{job_id}"
                  / "processed" / "structures")
    structures.mkdir(parents=True)
    residues = np.array([(folded.encode(),), (b"VAL",)], dtype=[("name", "S8")])
    chains = np.array([(b"P", 0, 2)],
                      dtype=[("name", "S8"), ("res_idx", "i4"),
                             ("res_num", "i4")])
    np.savez(structures / f"{job_id}.npz", residues=residues, chains=chains)

    if with_reference:
        reference = tmp_path / "campaign_reference" / "yaml"
        reference.mkdir(parents=True)
        (reference / f"{job_id}.yaml").write_text(yaml_path.read_text())
    return campaign


def _apply(campaign: Path):
    return subprocess.run(
        [str(SCI), str(ROOT / "tools" / "rerun_pair.py"), "pairA",
         "--campaign", str(campaign), "--apply"],
        capture_output=True, text=True, cwd=ROOT,
        env={"PYTHONPATH": str(ROOT), "KMP_DUPLICATE_LIB_OK": "TRUE",
             "PATH": "/usr/bin:/bin"})


def test_nothing_to_correct_refuses_and_drops_nothing(tmp_path):
    """The live failure, reproduced: a correct YAML, a cache that agrees,
    and an --apply that used to clear everything anyway."""
    campaign = _campaign(tmp_path, folded="PRO")
    before = {name: (campaign / name).read_text()
              for name in ("state.jsonl", "results.jsonl", "scores.jsonl")}

    result = _apply(campaign)
    said = result.stdout + result.stderr
    assert result.returncode == 2, said
    # Named, because `rerun_pair` has several refusals that all exit 2 and
    # this test would otherwise pass on any of them.
    assert "(F146, F302)" in said, said
    for name, text in before.items():
        assert (campaign / name).read_text() == text, f"{name} was dropped"
    assert list((campaign / "outputs").iterdir()), "outputs were cleared"


def test_a_disagreeing_cache_does_not_trip_the_new_guard(tmp_path):
    """The F219 case is real and must not be refused by this guard: the YAML
    can already be right while the cache holds the old input.

    Asserted as "execution got past the guard" rather than as "the results
    were cleared", because clearing is gated by F146's separate refusal for a
    job with no known-good reference, and `_known_good` searches the real
    `campaigns/` tree rather than `tmp_path`, so a fixture cannot satisfy it.
    Claiming the stronger thing here would be testing F146's guard and
    calling it this one.
    """
    campaign = _campaign(tmp_path, folded="HYP")
    result = _apply(campaign)
    said = result.stdout + result.stderr
    assert "(F146, F302)" not in said, (
        "the new guard refused a job whose cached featurisation disagrees "
        f"with its YAML, which is the case it exists to let through: {said}"
    )
    assert "no known-good reference" in said, (
        f"execution did not reach F146's refusal, so where it stopped is "
        f"not established: {said}"
    )
