"""Deterministic extraction of entity references from a routed query (FR-03, AD-7, D6).

Extraction finds the *tokens the operator typed* - nothing else. Resolving them against state
(exact match under case-folding, never fuzzy) is the resolver's job, and the intent fixes which
type each token has. No LLM, no fuzzy matching, and a token is only ever a substring of the query:
the extractor cannot invent a reference.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from src.domain.intent import fold_apostrophes


@dataclass(frozen=True)
class AccessDenialReferences:
    """The raw user and model tokens of an access-denial question, case as typed."""

    user: str
    model: str


# a reference token: anything up to whitespace or sentence punctuation (ids may hold - . #);
# surrounding quotes and a possessive 's are removed afterwards by _strip
_TOKEN = r"[^\s,;:?!()\[\]]+"
_END = r"(?=[\s,;:?!.]|$)"
# words that can stand where a name should be but never are one (a stop-word is no reference)
_USER_STOP = r"(?:the|a|an|student|user|he|she|they|it|someone|somebody|anyone)"
_MODEL_STOP = r"(?:access|to|from|for|the|a|an|of|on|in|model)"
_WHO = rf"(?:(?:student|user|the|a)\s+)*(?!{_USER_STOP}{_END})(?P<user>{_TOKEN})"
_WHAT = rf"(?:(?:model|the)\s+)*(?!{_MODEL_STOP}{_END})(?P<model>{_TOKEN})"
_VERB = r"(?:denied|blocked|refused)"
_OBJECT = rf"(?:(?:the\s+)?access\s+)?(?:(?:to|from|for)\s+)?{_WHAT}"

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
    """Same normalisation as the router (NFKC, apostrophe lookalikes folded before and after)."""
    folded = unicodedata.normalize("NFKC", fold_apostrophes(text))
    return " ".join(fold_apostrophes(folded).split())


_QUOTES = "'\"`"


def _strip(token: str) -> str:
    """Drop surrounding quotes, a trailing sentence dot and a possessive ``'s``."""
    token = token.strip(_QUOTES).rstrip(".")
    if token.lower().endswith("'s"):
        token = token[:-2]
    return token.strip(_QUOTES).rstrip(".")


def extract_access_denial_references(query: str) -> AccessDenialReferences | None:
    """The user/model tokens of ``why was <user> denied <model>`` (and variants), or ``None``."""
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


# Shared with the other diagnosers (story 3.1+): same query normalisation and token cleaning.
clean_query = _clean
strip_token = _strip
