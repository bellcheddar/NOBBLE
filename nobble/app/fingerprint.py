"""What build is this server running? (F138)

Browser QC drives a live server and reports pages captured, non-200
responses, console errors and axe violations. It has no idea which build it
is talking to. A server left running from earlier in the build answers every
request happily with the old templates and the old routes, and the report
comes back clean because the old build was clean.

That is not hypothetical. A QC run reported 14 pages, 0 non-200, 0 console
errors and 0 serious axe violations against a process started hours before
the change it was meant to be checking. The change was not in the pages at
all. What gave it away was looking for the new element in the DOM and finding
no such element, which is a thing I happened to do and not a thing the
harness does.

So the server states its own identity and QC refuses to report on a server
whose identity does not match the working tree. A fingerprint over the app's
own source, which is everything under `nobble/app` except the vendored
libraries, plus the modules outside it that decide what the API returns.

Vendored assets are excluded deliberately. They are pinned, they are 10 MB,
and hashing them would make the fingerprint a statement about Mol* rather
than about this build.

One implementation, called from both sides. `tools/app_fingerprint.py` prints
it for the harness rather than the harness recomputing it in JavaScript: two
implementations of one hash is a thing that drifts, and when it drifts the
symptom is a QC run that refuses a server that is in fact current.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parents[1]

# Everything the app serves or decides with, except the pinned libraries.
#
# `static/vendor/*.js` is deliberately included and `static/vendor/*/*` is
# not. The subdirectories are third-party builds, 10 MB of Mol*, Plotly, D3
# and Tabulator, pinned and not ours. The loose file beside them is
# `molstar-bridge.js`, which is BINMAN's own shared code vendored in, and it
# changes: widening the bridge to name Mol*'s logo link fixed a serious axe
# violation and moved no fingerprint, so QC would have passed against a
# server running the old bridge (F138).
#
# `VENDOR.json` stands in for the libraries themselves. It records what is
# pinned, so a version change moves the fingerprint without hashing the
# builds.
INCLUDE = (
    "*.py",
    "templates/*.html",
    "static/css/*.css",
    "static/js/*.js",
    "static/vendor/*.js",
    "static/vendor/VENDOR.json",
)
# Modules outside nobble/app that change what the API returns. Named rather
# than globbed: the scoring stack is not part of what the droplet serves, and
# hashing it would make the fingerprint change on work the pages cannot show.
ALSO = ("nobble/sampling.py", "nobble/numeric.py", "nobble/paths.py")


def files() -> list[Path]:
    found: set[Path] = set()
    for pattern in INCLUDE:
        found.update(path for path in APP.glob(pattern) if path.is_file())
    for relative in ALSO:
        path = ROOT / relative
        if path.is_file():
            found.add(path)
    return sorted(found)


def detail() -> dict[str, str]:
    """Per-file digest, so a mismatch can say which file differs."""
    return {
        str(path.relative_to(ROOT)):
            hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        for path in files()
    }


def fingerprint() -> str:
    """One digest over the app's source, stable across processes and hosts.

    Paths are relative to the project root so the digest does not depend on
    where the tree is checked out, which it would if the absolute path went
    into the hash: the droplet and the build machine would then never agree.
    """
    digest = hashlib.sha256()
    for name, value in sorted(detail().items()):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(value.encode())
        digest.update(b"\n")
    return digest.hexdigest()[:16]
