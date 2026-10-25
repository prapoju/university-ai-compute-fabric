"""Deterministic extraction of entity references from a routed query (FR-03, AD-7, D6).

Extraction finds the *tokens the operator typed* - nothing else. Resolving them against state
(exact match under case-folding, never fuzzy) is the resolver's job, and the intent fixes which
type each token has. No LLM, no fuzzy matching, and a token is only ever a substring of the query:
the extractor cannot invent a reference.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.domain.intent import fold_apostrophes


@dataclass(frozen=True)
class AccessDenialReferences:
    """The raw user and model tokens of an access-denial question, case as typed."""

    user: str
    model: str


# a reference token: anything up to whitespace or sentence punctuation (ids may hold - . #)
_TOKEN = r"[^\s,;:?!()\[\]\"]+"
_WHO = rf"(?:(?:student|user|the|a)\s+)*(?P<user>{_TOKEN})"
_WHAT = rf"(?:(?:model|the)\s+)*(?P<model>{_TOKEN})"
_VERB = r"(?:denied|blocked|refused)"
_OBJECT = rf"(?:access\s+)?(?:(?:to|from|for)\s+)?{_WHAT}"

_ACCESS_DENIAL = (
    # why was alex denied (access to) deepseek-coder
    re.compile(
        rf"\bwhy\s+(?:was|is|were|has|had|did)\s+{_WHO}\s+(?:been\s+)?{_VERB}\s+{_OBJECT}", re.I
    ),
    # why can't / cannot alex access deepseek-coder
    re.compile(rf"\bwhy\s+(?:can't|cannot|can\s+not)\s+{_WHO}\s+access\s+{_WHAT}", re.I),
    # why is alex not allowed to / unable to access deepseek-coder
    re.compile(
        rf"\bwhy\s+(?:is|are)\s+{_WHO}\s+(?:not\s+allowed\s+to|unable\s+to)\s+access\s+{_WHAT}",
        re.I,
    ),
    # alex was denied access to deepseek-coder
    re.compile(rf"^{_WHO}\s+(?:was|has\s+been|is)\s+{_VERB}\s+{_OBJECT}", re.I),
)

_FOLLOW_UP = re.compile(
    rf"^(?:(?:and|also|then)\s+)?(?:what|how)\s+about\s+(?P<ref>{_TOKEN})", re.I
)


def _clean(text: str) -> str:
    return " ".join(fold_apostrophes(text).split())


def _strip(token: str) -> str:
    return token.rstrip(".")


def extract_access_denial_references(query: str) -> AccessDenialReferences | None:
    """The user and model tokens of ``why was <user> denied <model>`` (and variants), or ``None``."""
    text = _clean(query)
    for pattern in _ACCESS_DENIAL:
        match = pattern.search(text)
        if match is not None:
            user, model = _strip(match["user"]), _strip(match["model"])
            if user and model:
                return AccessDenialReferences(user, model)
    return None


def extract_follow_up_reference(query: str) -> str | None:
    """The single token of ``(and) what/how about <ref>``, or ``None`` if it is not a follow-up."""
    match = _FOLLOW_UP.search(_clean(query))
    if match is None:
        return None
    return _strip(match["ref"]) or None
