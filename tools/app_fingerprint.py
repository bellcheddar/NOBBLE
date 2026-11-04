#!/usr/bin/env python
"""Print the app's source fingerprint, for the QC harness (F138).

Called by qc/qc.mjs rather than reimplemented there, so there is one
definition of the hash. `--detail` prints the per-file digests, which is what
to look at when a mismatch needs explaining.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.app import fingerprint  # noqa: E402


def main() -> int:
    if "--detail" in sys.argv:
        print(json.dumps(fingerprint.detail(), indent=2))
    else:
        print(fingerprint.fingerprint())
    return 0


if __name__ == "__main__":
    sys.exit(main())
