"""A refusal must not be the thing that destroys the atlas (F327).

`deploy/build_atlas.py` clears its output directory and then runs nine
checks, five of which can only be decided from the bundle they have just
written: the PROTAC-DB redaction, the local-path leak, the unexpected
files, the referenced files that went missing, and whether anything was
scored at all. Each of those ends in `return 1`.

Every one of them used to return with `deploy/atlas` holding neither the
previous bundle nor a complete new one. The site then served whatever the
build had got to, which for a refusal on the licensing check is the
specific thing the check exists to prevent reaching a browser.
`test_the_input_refusals_come_before_the_output_directory_is_cleared`
pushed the refusals that *could* be decided early to before the clear, and
correctly left these five where they are: they inspect the output, so they
cannot run before it exists.

So the bundle is built in `deploy/atlas_staging` and renamed into place
once the last check has passed. A refusal now returns with the published
bundle untouched, which is the bundle that passed these same checks on the
run that published it.

What is checked here. The move's semantics, exercised on real directories.
And, against the source, that no refusal can follow the move: that is the
whole guarantee, and it is a property of call order rather than of
anything the move itself does.

The successful publish is checked end to end elsewhere, and was not when
this file was written: `tests/test_redaction_count.py` and
`tests/test_design_parent_provenance.py` both run the real builder into a
`tmp_path` bundle and read what comes out, so each of them exercises the
staging directory and the rename. Measured during this change, by watching
three real builds spawn from the suite.

Not checked anywhere: an end-to-end refusal of the real builder. The one
test that asks for one skips on a clean campaign, so the late refusals and
the message naming the staged bundle are reached by no test. That needs a
campaign fixture whose inputs pass four earlier refusals and then fail a
late one. Named rather than quietly absent.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "deploy" / "build_atlas.py"
SOURCE = BUILDER.read_text()
TREE = ast.parse(SOURCE)

sys.path.insert(0, str(ROOT / "deploy"))
import build_atlas as B  # noqa: E402


def test_the_build_writes_somewhere_other_than_the_published_bundle():
    assert B.OUT != B.PUBLISHED, (
        "the build writes straight into the published bundle again, so "
        "every refusal below the clear destroys it"
    )
    assert B.OUT.parent == B.PUBLISHED.parent, (
        "the staging directory is on a different parent, so publishing is "
        "a copy of 798 MB rather than a rename"
    )


def test_the_staging_directory_is_not_committed():
    """2,515 files and 798 MB, a second time (F303).

    A refused run leaves it on disk deliberately, so the one thing that
    must not happen is it being picked up by a commit.
    """
    ignored = (ROOT / ".gitignore").read_text()
    assert B.OUT.name in ignored, (
        f"{B.OUT.name} is not in .gitignore, so a refused build leaves a "
        "second copy of the bundle for the next commit to track"
    )


def _refusal_lines() -> list[int]:
    """Every `return 1` in the module, by line."""
    return sorted(
        node.lineno for node in ast.walk(TREE)
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Constant)
        and node.value.value == 1
    )


def test_there_are_refusals_to_order():
    # Without this the ordering assertion below passes on a module that
    # cannot refuse at all, which is the empty answer wearing the clean
    # answer's shape.
    assert len(_refusal_lines()) >= 5, (
        f"only {len(_refusal_lines())} refusal(s) found in the builder; "
        "the ordering check below is vacuous if they have moved or gone"
    )


def test_no_refusal_comes_after_the_bundle_is_published():
    """The invariant. Every `return 1` precedes the move.

    Asked over the source rather than by running the build, because the
    failing arrangement is reachable by editing one line and the cost of
    discovering it from a half-published atlas is the F327 outage again.
    """
    calls = [node for node in ast.walk(TREE)
             if isinstance(node, ast.Call)
             and ast.unparse(node.func) == "publish_staged"]
    assert len(calls) == 1, (
        f"{len(calls)} call(s) to publish_staged; there is one, at the end "
        "of the build, and more than one means a bundle can be published "
        "from a path that has not passed every check"
    )
    published_at = calls[0].lineno
    late = [line for line in _refusal_lines() if line > published_at]
    assert late == [], (
        f"refusal(s) at line(s) {late} fire after the bundle is published "
        f"at line {published_at}, so the thing being refused is already "
        "the published atlas"
    )


def test_the_publish_replaces_the_previous_bundle(tmp_path):
    staged = tmp_path / "atlas_staging"
    (staged / "structures").mkdir(parents=True)
    (staged / "structures" / "new.cif").write_text("new")
    (staged / "ATLAS.json").write_text("{}")

    published = tmp_path / "atlas"
    (published / "structures").mkdir(parents=True)
    (published / "structures" / "old.cif").write_text("old")

    B.publish_staged(staged, published)

    assert not staged.exists(), "the staged bundle is still staged"
    assert (published / "structures" / "new.cif").read_text() == "new"
    assert not (published / "structures" / "old.cif").exists(), (
        "a file from the previous bundle survived the publish, so the "
        "atlas is two builds mixed together"
    )


def test_the_publish_works_when_there_is_nothing_to_replace(tmp_path):
    staged = tmp_path / "atlas_staging"
    staged.mkdir()
    (staged / "ATLAS.json").write_text("{}")
    published = tmp_path / "atlas"

    B.publish_staged(staged, published)

    assert (published / "ATLAS.json").exists()


def test_the_publish_is_a_no_op_when_the_two_are_the_same(tmp_path):
    """The case that must not delete the bundle it was asked to publish.

    `NOBBLE_ATLAS_OUT` sets the published path and the staging path is
    derived from it, so the two are never equal in the build. If some
    caller makes them equal, removing the destination removes the source.
    """
    both = tmp_path / "atlas"
    both.mkdir()
    (both / "ATLAS.json").write_text("{}")

    B.publish_staged(both, both)

    assert (both / "ATLAS.json").exists(), (
        "publishing a bundle onto itself deleted it"
    )


def test_a_refusal_says_where_the_staged_bundle_is():
    """Otherwise the operator reads the refusal and looks at `deploy/atlas`,
    which is untouched and therefore looks fine."""
    assert "the refused bundle is staged at" in SOURCE
    assert "is untouched and still holds" in SOURCE


def test_the_deploy_refuses_while_a_refused_build_is_staged():
    """The chain runs the build with `|| true` and then deploys.

    So a refusal inside `build_atlas.py` is a line in a log that the next
    stage ignores. It does not follow that a half-built bundle reached the
    droplet: `tools/atlas_drift.py` rebuilds the atlas and compares it leaf
    by leaf before the rsync, and a partial bundle fails that comparison,
    so the deploy refused. F327 said as much, that the deployment topology
    was what saved it, and this check is not a claim that it did not.

    What it adds is the reason. The drift check refuses with "the published
    atlas is not what the current code builds", which reads as code drift
    and sends the operator to rebuild: correct advice, arrived at from the
    wrong cause, and only after a full rebuild has run. This refuses first,
    locally, before a connection to the droplet is opened, and says that
    the last build refused and the bundle below it is the one before.
    """
    script = (ROOT / "deploy" / "deploy.sh").read_text()
    assert "deploy/atlas_staging" in script, (
        "the deploy no longer notices a staged bundle, so a refused atlas "
        "build is followed by a successful deploy of the bundle before it"
    )
    guard = script.index("deploy/atlas_staging")
    for sends in ("rsync -rlpt --delete \\", 'deploy/atlas/ "$DROPLET_SSH'):
        assert script.index(sends) > guard, (
            f"the staged-bundle check runs after `{sends[:22]}`, which has "
            "already sent the bundle"
        )


def test_the_chain_still_runs_the_build_without_stopping_on_it():
    """The premise of the test above, asserted rather than assumed.

    If the chain ever stops on a refused atlas build, the deploy guard is
    unreachable and this file should say so instead of carrying a check
    for a path that cannot be taken.
    """
    chain = (ROOT / "tools" / "run_chain.sh").read_text()
    assert "bash tools/refresh.sh" in chain
    window = chain[chain.index("bash tools/refresh.sh"):][:80]
    assert "|| true" in window, (
        "the chain now stops when the atlas build refuses, so the deploy "
        "guard above is no longer the thing that prevents publishing a "
        "bundle the build declined. Re-read both and simplify one of them."
    )


def test_the_drift_rebuild_stages_inside_its_temporary_directory():
    """The trap the staging change sets, closed in the same change.

    Staging is a sibling of what `NOBBLE_ATLAS_OUT` names, so a caller
    that points it at a container directory rather than at a bundle gets
    798 MB written beside that container. `tools/atlas_drift.py` pointed
    it at a `TemporaryDirectory` itself, which would have staged the
    bundle at `<tmpdir>_staging`: outside the directory that cleans up,
    and outside the project root, which the build may not leave.

    It is the one caller that rebuilds the whole atlas, and it was found
    by reading the change rather than by running it, because running it
    writes the 798 MB first. The two test callers already passed
    `tmp_path / "atlas"` and were already correct.

    Checked here rather than as a sweep over every caller: resolving the
    value needs the variable it was assigned on an earlier line, and a
    line-shaped check reported the two correct callers as offenders along
    with its own regex. A wrong check for a rare mistake is worse than a
    named check for the one place it happened.
    """
    drift = (ROOT / "tools" / "atlas_drift.py").read_text()
    assert '"NOBBLE_ATLAS_OUT": str(Path(workdir) / "atlas")' in drift, (
        "the drift rebuild no longer names a bundle inside its temporary "
        "directory, so the build stages a copy of the atlas beside that "
        "directory, where nothing cleans it up"
    )
    assert '_leaves(Path(workdir) / "atlas")' in drift, (
        "the drift check reads the rebuilt bundle from the temporary "
        "directory itself, which is now the bundle's parent, so every "
        "leaf would read as missing and every build as drifted"
    )


def test_the_published_path_is_what_the_environment_names():
    """The contract the test above is about, stated as an assertion.

    A caller sets `NOBBLE_ATLAS_OUT` to the bundle, and the staging
    directory is derived from it. Pointing it at a container gives the
    container a sibling.
    """
    import importlib
    import os

    bundle = ROOT / "deploy" / "atlas"
    previous = os.environ.get("NOBBLE_ATLAS_OUT")
    try:
        os.environ["NOBBLE_ATLAS_OUT"] = str(bundle)
        fresh = importlib.reload(B)
        assert fresh.PUBLISHED == bundle
        assert fresh.OUT == bundle.with_name("atlas_staging")
    finally:
        if previous is None:
            os.environ.pop("NOBBLE_ATLAS_OUT", None)
        else:
            os.environ["NOBBLE_ATLAS_OUT"] = previous
        importlib.reload(B)


def test_the_refusal_message_survives_a_bundle_outside_the_project(tmp_path):
    """The defect the change shipped with, for about twenty minutes.

    The message naming the staged bundle used `relative_to(ROOT)`, and
    three callers point `NOBBLE_ATLAS_OUT` at a temporary directory, which
    is not under the project root. `relative_to` raises there.

    It is on the refusal path, which is the one place where a crash in the
    reporting replaces the reason for the refusal with a reason about
    printing it.

    I said when fixing it that the run then in flight was about to hit it:
    `test_the_atlas_build_refuses_rather_than_publishing` builds a
    `tmp_path` bundle and asserts exit 1 with "REFUSING TO PUBLISH". It
    skips, because that campaign's YAML is clean, and so does every other
    refusal against a temporary bundle. Nothing in the suite reaches this
    line today, which makes the fix a fix for the next refusal rather than
    for an observed failure, and makes this test the only thing standing
    between the two.

    Worth keeping the distinction: predicting what a run will do is how
    this was found, and predicting is also how I got the consequence
    wrong.
    """
    outside = tmp_path / "atlas_staging"
    assert B._shown(outside) == str(outside), (
        "the path shown in a refusal is built with relative_to, which "
        "raises for a bundle outside the project root and turns a refusal "
        "into a traceback"
    )
    inside = ROOT / "deploy" / "atlas_staging"
    assert B._shown(inside) == "deploy/atlas_staging", (
        "a path inside the project is no longer shown relative to it"
    )


def _campaign_with_nothing_scored(tmp_path):
    """The real campaign, with its scores emptied, assembled cheaply.

    The named gap in this file's docstring was an end-to-end refusal, which
    needs inputs that pass the four refusals before the clear and then fail
    one after it. Constructing those from nothing means satisfying
    `inputs.stale_inputs`, the YAML-shape check and the featurisation
    comparison, which is why
    `tests/test_stale_inputs.py::test_the_atlas_build_refuses_rather_than_publishing`
    skips on a clean campaign rather than building a fixture.

    So the real campaign is reused, which passes all four by construction,
    and the one thing it needs to fail is arranged: `scores.jsonl` emptied,
    so `published_pairs` is zero and the refusal F324 added fires, after
    the clear and after everything that writes.

    `outputs` is 3.0 of the campaign's 3.1 GB and the build only reads it,
    so it is symlinked rather than copied. Everything else is small.
    """
    import shutil

    source = sorted(ROOT.glob("campaigns/campaign_*"))
    if not source:
        return None
    source = source[-1]
    if not (source / "scores.jsonl").exists():
        return None

    campaign = tmp_path / source.name
    campaign.mkdir()
    for entry in sorted(source.iterdir()):
        if entry.name == "outputs":
            (campaign / "outputs").symlink_to(entry)
        elif entry.is_dir():
            shutil.copytree(entry, campaign / entry.name)
        else:
            shutil.copy2(entry, campaign / entry.name)
    (campaign / "scores.jsonl").write_text("")
    return campaign


def test_a_real_refusal_leaves_the_published_bundle_untouched(tmp_path):
    """The end-to-end case, which nothing covered (F327d).

    Everything else here is either the move in isolation or a property of
    the source. This runs the real builder, makes it refuse after the
    clear, and looks at what is on disk afterwards: the published
    directory with its contents intact, the staged bundle beside it, and a
    refusal that names where the staged one went.

    Before the staging change the published directory would hold a
    half-written bundle at this point and the previous one would be gone.
    """
    import os
    import subprocess

    campaign = _campaign_with_nothing_scored(tmp_path)
    if campaign is None:
        pytest.skip("no campaign with scores on this checkout")

    published = tmp_path / "atlas"
    (published / "structures").mkdir(parents=True)
    (published / "structures" / "previous.cif").write_text("the old bundle")
    (published / "ATLAS.json").write_text('{"published_pairs": 158}')

    done = subprocess.run(
        [str(ROOT.parent / "BINMAN" / ".pixi" / "envs" / "default" / "bin"
             / "python"), "deploy/build_atlas.py", str(campaign)],
        cwd=ROOT, capture_output=True, text=True, timeout=900,
        env={**os.environ, "PYTHONPATH": str(ROOT),
             "KMP_DUPLICATE_LIB_OK": "TRUE",
             "NOBBLE_ATLAS_OUT": str(published)},
    )

    assert done.returncode == 1, (done.returncode, done.stdout[-1500:],
                                  done.stderr[-1500:])
    assert "REFUSING" in done.stderr, done.stderr[-1500:]
    assert "holds no scored pair" in done.stderr, done.stderr[-1500:]

    # The point of the whole change.
    assert (published / "structures" / "previous.cif").read_text() == (
        "the old bundle"), (
        "the refusal destroyed the published bundle, which is F327"
    )
    assert json.loads((published / "ATLAS.json").read_text())[
        "published_pairs"] == 158

    staged = published.with_name("atlas_staging")
    assert staged.is_dir(), (
        "the refused bundle is not on disk, so there is nothing to read "
        f"the refusal against: {sorted(p.name for p in tmp_path.iterdir())}"
    )
    assert "atlas_staging" in done.stderr, (
        "the refusal does not say where the staged bundle went, so the "
        "operator looks at the published one and finds it fine"
    )


def test_the_same_build_publishes_when_nothing_refuses(tmp_path):
    """The other half, so the test above is not passing on a broken build.

    A refusal that leaves the published bundle alone is worth nothing if
    the build refuses whatever it is given. Same campaign, scores intact,
    and this time the previous bundle must be replaced rather than kept.
    """
    import os
    import shutil
    import subprocess

    source = sorted(ROOT.glob("campaigns/campaign_*"))
    if not source or not (source[-1] / "scores.jsonl").exists():
        pytest.skip("no campaign with scores on this checkout")
    source = source[-1]

    campaign = tmp_path / source.name
    campaign.mkdir()
    for entry in sorted(source.iterdir()):
        if entry.name == "outputs":
            (campaign / "outputs").symlink_to(entry)
        elif entry.is_dir():
            shutil.copytree(entry, campaign / entry.name)
        else:
            shutil.copy2(entry, campaign / entry.name)

    published = tmp_path / "atlas"
    (published / "structures").mkdir(parents=True)
    (published / "structures" / "previous.cif").write_text("the old bundle")

    done = subprocess.run(
        [str(ROOT.parent / "BINMAN" / ".pixi" / "envs" / "default" / "bin"
             / "python"), "deploy/build_atlas.py", str(campaign)],
        cwd=ROOT, capture_output=True, text=True, timeout=900,
        env={**os.environ, "PYTHONPATH": str(ROOT),
             "KMP_DUPLICATE_LIB_OK": "TRUE",
             "NOBBLE_ATLAS_OUT": str(published)},
    )
    assert done.returncode == 0, (done.stdout[-1500:], done.stderr[-1500:])
    assert not (published / "structures" / "previous.cif").exists(), (
        "a file from the previous bundle survived a successful publish, so "
        "the atlas is two builds mixed together"
    )
    assert (published / "ATLAS.json").exists()
    assert not published.with_name("atlas_staging").exists(), (
        "the staging directory is still there after a successful publish"
    )
