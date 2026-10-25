"""The prose guard (AD-8): connective prose may link facts, it must never carry one.

The LLM writes prose around an answer whose facts are already fixed and cited. Any fact that
escaped into the prose would be uncited, so the pipeline scans the prose for the answer's
*fact tokens* (entity ids, names, roles, rule and clause ids, reason classes, times) and rejects
the whole prose on a hit - it never strips mid-sentence (D48). Pure: normalisation and regex only.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


def _fold(text: str) -> str:
    """NFKC + case-fold + single spaces; invisible format characters (zero-width space, soft
    hyphen, word joiner, BOM) are dropped so they cannot split a fact token in two."""
    visible = "".join(
        c for c in unicodedata.normalize("NFKC", text) if unicodedata.category(c) != "Cf"
    )
    return " ".join(visible.casefold().split())


def scan_prose(prose: str, tokens: Iterable[str]) -> list[str]:
    """The fact tokens found in ``prose`` (whole words, case-folded, NFKC), unique and sorted."""
    haystack = _fold(prose)
    hits: set[str] = set()
    for token in tokens:
        needle = _fold(token)
        if not needle:
            continue
        if re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack):
            hits.add(needle)
    return sorted(hits)
