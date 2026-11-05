"""A queue row naming no YAML crashed the check written to catch it.

`stale_inputs` compares each queue row against the YAML it names, and has a
branch for the row whose YAML is missing from disk. A row with no `yaml`
field at all slipped past that branch: `Path("")` is not absolute, so
`campaign / Path("")` is the campaign directory, and a directory exists. The
function then called `read_text()` on it and raised `IsADirectoryError`.

Where that surfaced matters more than the exception. `stale_inputs` is called
by `deploy/build_atlas.py` before it publishes, which runs unattended inside
`tools/run_chain.sh` after fifty hours of inference. The failure arrived as a
traceback from `pathlib`, saying nothing about queues or YAML, in the step
whose job is to refuse politely when the inputs are wrong.

Found by building a tier-2 rehearsal campaign by hand and writing minimal
queue rows for it. The current selector copies the whole job dict, so every
row it writes carries `yaml`, and no campaign on disk has a row without one:
this hardens a guard rather than fixing a reachable defect. The guard is
worth hardening anyway, because it is the thing that decides whether a
fifty-hour run gets published.

The reason is branched too. "The YAML the queue row names is not on disk"
describes a file the row never claimed to have, which is the one-message-for-
two-cases shape of F198 through F201.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.validate import inputs  # noqa: E402


def _campaign(tmp_path: Path, rows: list[dict], yaml_text: str | None = None) -> Path:
    campaign = tmp_path / "campaign"
    (campaign / "yaml").mkdir(parents=True)
    if yaml_text is not None:
        (campaign / "yaml" / "job.yaml").write_text(yaml_text)
    (campaign / "queue.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows))
    return campaign


def test_a_row_with_no_yaml_field_is_reported_rather_than_raising(tmp_path):
    campaign = _campaign(tmp_path, [{"job_id": "j1", "pair_id": "p1"}])
    stale = inputs.stale_inputs(campaign)
    assert len(stale) == 1, stale
    assert stale[0]["job_id"] == "j1"
    assert "names no YAML" in stale[0]["reason"], stale[0]["reason"]


def test_an_empty_yaml_string_is_the_same_case(tmp_path):
    """`Path("")` is how the field arrives when it is present and blank, and
    it resolves to the campaign directory exactly as a missing field does."""
    campaign = _campaign(tmp_path, [{"job_id": "j1", "pair_id": "p1", "yaml": ""}])
    stale = inputs.stale_inputs(campaign)
    assert len(stale) == 1
    assert "names no YAML" in stale[0]["reason"]


def test_a_row_naming_a_directory_is_also_refused(tmp_path):
    """The general form of the defect: any path that exists and is not a
    file. `exists()` accepted all of them and `read_text()` raised."""
    campaign = _campaign(tmp_path, [{"job_id": "j1", "pair_id": "p1",
                                     "yaml": "yaml"}])
    stale = inputs.stale_inputs(campaign)
    assert len(stale) == 1
    assert stale[0]["reason"], stale[0]


def test_a_row_naming_a_missing_file_keeps_its_own_reason(tmp_path):
    """The branch that already worked, and the two reasons stay distinct: a
    campaign whose inputs were moved is not a row that names nothing."""
    campaign = _campaign(tmp_path, [{"job_id": "j1", "pair_id": "p1",
                                     "yaml": "yaml/gone.yaml"}])
    stale = inputs.stale_inputs(campaign)
    assert len(stale) == 1
    assert "is not on disk" in stale[0]["reason"], stale[0]["reason"]
    assert "names no YAML" not in stale[0]["reason"]


def test_the_two_reasons_are_different_strings(tmp_path):
    missing = inputs.stale_inputs(_campaign(
        tmp_path / "a", [{"job_id": "j", "yaml": "yaml/gone.yaml"}]))
    nameless = inputs.stale_inputs(_campaign(
        tmp_path / "b", [{"job_id": "j"}]))
    assert missing[0]["reason"] != nameless[0]["reason"]


def test_a_row_whose_yaml_agrees_is_not_stale(tmp_path):
    """Red-green: without this the tests above pass against a function that
    calls everything stale."""
    campaign = _campaign(
        tmp_path,
        [{"job_id": "j1", "pair_id": "p1", "yaml": "yaml/job.yaml"}],
        yaml_text="sequences:\n  - protein:\n      id: A\n",
    )
    assert inputs.stale_inputs(campaign) == []


def test_the_atlas_build_consults_it(tmp_path):
    """Why the failure mode mattered: this is the caller that turns a stale
    input into a refusal to publish."""
    source = (ROOT / "deploy" / "build_atlas.py").read_text()
    assert "stale_inputs(" in source
