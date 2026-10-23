"""ATDD suite bootstrap.

Puts the ATDD directory (for ``module12_interface``) and the harness directory
(``tests/``, for ``support.*``) on ``sys.path`` so the red-phase suite can call the
interface stub and reuse the harness builders/helpers. No fixtures are redefined here;
tests import the ``support`` helpers directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ATDD_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _ATDD_DIR.parents[1] / "tests"

for _p in (str(_ATDD_DIR), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
