"""QC has to know which build it is talking to (F138).

Browser QC drives a live server and reports pages captured, non-200
responses, console errors and axe violations. It had no way of telling which
build was answering. A run reported 14 pages, 0 non-200 and 0 console errors
against a process started hours before the change it was meant to be
checking, and the change was not in those pages at all.

So the server states its identity and the harness refuses a server whose
identity is not the working tree.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from nobble.app import fingerprint

ROOT = Path(__file__).resolve().parents[1]


def test_the_fingerprint_is_stable_across_calls():
    assert fingerprint.fingerprint() == fingerprint.fingerprint()


def test_it_covers_the_templates_and_the_routes():
    covered = {str(path.relative_to(ROOT)) for path in fingerprint.files()}
    for required in ("nobble/app/routes.py", "nobble/app/data.py",
                     "nobble/app/templates/pose.html",
                     "nobble/app/static/css/depot.css",
                     "nobble/app/static/js/nobble.js"):
        assert required in covered, f"{required} is not in the fingerprint"


def test_it_covers_the_shared_bridge_but_not_the_pinned_libraries():
    """The loose file in vendor/ is BINMAN's code and it changes.

    Widening the bridge to name Mol*'s logo link fixed a serious axe
    violation and moved no fingerprint, so QC would have passed against a
    server running the old bridge.
    """
    covered = {str(path.relative_to(ROOT)) for path in fingerprint.files()}
    assert "nobble/app/static/vendor/molstar-bridge.js" in covered
    assert "nobble/app/static/vendor/VENDOR.json" in covered
    libraries = [name for name in covered
                 if "/vendor/molstar/" in name or "/vendor/plotly/" in name
                 or "/vendor/d3/" in name or "/vendor/tabulator/" in name]
    assert not libraries, (
        f"{libraries} are pinned third-party builds; hashing them makes the "
        "fingerprint a statement about Mol* rather than about this build"
    )


def test_changing_a_template_changes_the_fingerprint(tmp_path):
    """The property the whole thing rests on, checked by actually doing it.

    Restored in a finally, and the file is read back to confirm the restore:
    a test that leaves a template modified is worse than no test (F45).
    """
    template = ROOT / "nobble" / "app" / "templates" / "pose.html"
    original = template.read_text()
    before = fingerprint.fingerprint()
    try:
        template.write_text(original + "\n<!-- fingerprint check -->\n")
        after = fingerprint.fingerprint()
    finally:
        template.write_text(original)
    assert template.read_text() == original, "the template was not restored"
    assert after != before
    assert fingerprint.fingerprint() == before


def test_the_path_and_not_the_location_goes_into_the_digest():
    """The droplet and the build machine have the tree in different places.

    If an absolute path reached the hash the two would never agree, and the
    check would reject every deployed server.
    """
    source = (ROOT / "nobble" / "app" / "fingerprint.py").read_text()
    assert "relative_to(ROOT)" in source
    digest = fingerprint.fingerprint()
    assert str(ROOT) not in json.dumps(fingerprint.detail())
    assert digest == fingerprint.fingerprint()


def test_the_tool_prints_what_the_module_computes():
    """One implementation, called from both sides.

    qc.mjs shells out to this rather than recomputing the hash in
    JavaScript, because two implementations of one hash drift and the
    symptom of the drift is QC refusing a server that is current.
    """
    done = subprocess.run(
        [sys.executable, "tools/app_fingerprint.py"],
        cwd=ROOT, capture_output=True, text=True,
        env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"},
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.strip() == fingerprint.fingerprint()


def test_healthz_reports_it():
    page = (ROOT / "nobble" / "app" / "routes.py").read_text()
    health = page[page.index('@bp.route("/healthz")'):]
    health = health[:health.index("\n@bp.route") if "\n@bp.route" in health
                    else len(health)]
    assert "source_fingerprint" in health, (
        "/healthz does not report the fingerprint, so qc.mjs has nothing to "
        "compare against"
    )


def test_qc_refuses_a_server_it_cannot_identify():
    harness = (ROOT / "qc" / "qc.mjs").read_text()
    guard = harness[:harness.index("const browser = await chromium.launch()")]
    assert "source_fingerprint" in guard, (
        "the build check runs after the browser launches, or not at all"
    )
    assert "process.exit(3)" in guard, (
        "a mismatched build has to stop the run, not print a warning into a "
        "report that then says the pages were clean"
    )
    assert "app_fingerprint.py" in guard, (
        "qc.mjs recomputes the hash instead of calling the one definition"
    )


def test_the_axe_detail_tool_says_which_host_it_looked_at():
    """It was hardcoded to the live site while qc.mjs ran against localhost.

    The two then reported different violations and neither said which host
    it had audited, which is F138 in a second file.
    """
    tool = (ROOT / "qc" / "axe_detail.mjs").read_text()
    assert "NOBBLE_BASE" in tool
    assert "console.log('axe ' + BASE + target)" in tool


def test_the_digest_does_not_depend_on_where_the_tree_lives(tmp_path, monkeypatch):
    """The property the deploy comparison rests on (F162).

    `deploy.sh` fingerprints the tree on this machine and compares it against
    what the droplet reports from its own copy at `$REMOTE_DIR`. That only
    means anything if the digest is a function of relative paths and content
    and nothing else. Verified against a real rsync with the deploy's own
    exclude list, which gave the same digest; this is the cheap version of
    that, copying only the hashed files to a different root.

    If it ever stops holding, every deploy refuses and the message blames
    the droplet for serving the wrong build.
    """
    import shutil

    from nobble.app import fingerprint

    before = fingerprint.fingerprint()
    for path in fingerprint.files():
        target = tmp_path / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

    monkeypatch.setattr(fingerprint, "ROOT", tmp_path)
    monkeypatch.setattr(fingerprint, "APP", tmp_path / "nobble" / "app")
    after = fingerprint.fingerprint()
    assert after == before, (
        "the digest moved when the same files were read from a different "
        "root, so the droplet can never agree with this machine"
    )


def test_a_file_disappearing_mid_read_is_not_a_crash(tmp_path, monkeypatch):
    """`files()` globs and `detail()` then reads, so the set can go stale.

    A deploy fingerprints the tree while a campaign is writing, and an editor
    or a sweep can remove a file between the two. Raising there fails a
    deploy with an OSError rather than a verdict, which is the least useful
    way to stop one.
    """
    import shutil

    from nobble.app import fingerprint

    for path in fingerprint.files():
        target = tmp_path / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    monkeypatch.setattr(fingerprint, "ROOT", tmp_path)
    monkeypatch.setattr(fingerprint, "APP", tmp_path / "nobble" / "app")

    listed = fingerprint.files()
    assert listed, "the fixture copied nothing"
    victim = next(p for p in listed if p.suffix == ".html")
    real_files = fingerprint.files

    def stale_listing():
        found = real_files()
        victim.unlink(missing_ok=True)
        return found

    monkeypatch.setattr(fingerprint, "files", stale_listing)
    digest = fingerprint.fingerprint()
    assert isinstance(digest, str) and digest, (
        "a file removed between the listing and the read raised instead of "
        "producing a digest"
    )
    # And the tree is a different tree, so it says which file went and does
    # not pass for a tree that never had it.
    monkeypatch.setattr(fingerprint, "files", real_files)
    assert fingerprint.detail().get(
        str(victim.relative_to(tmp_path))) in (None, fingerprint.MISSING)
