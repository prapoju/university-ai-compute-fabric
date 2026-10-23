"""``explain_assert`` — assert a decision carries >= 1 rule id and the observed values.

Re-exports the canonical implementation from ``tests/support/explain.py``.
Anchors: AD-2, AD-8, AD-11; contracts §0.5 ``Intent``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

from support.explain import Explanation, coerce_explanation, explain_assert  # noqa: E402

__all__ = ["explain_assert", "coerce_explanation", "Explanation"]
