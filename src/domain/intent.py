"""Deterministic, rule-based intent routing (FR-01, AD-11).

Routing depends only on the rule registry below and the session's prior intents: query text is
data, never control, and there is no LLM and no scoring. A query is routed only when a rule
matches; otherwise it is clarified - the classifier never guesses and never force-routes.
New intents are added by registering an :class:`IntentRule` (stories 3.1, 4.1, 3.4); nothing else
changes.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from src.domain import canonical_strings as cs


@dataclass(frozen=True)
class IntentRule:
    """One registered intent: a stable code, a rule id for citations, and its patterns."""

    intent_code: str
    rule_id: str
    patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class Routed:
    intent_code: str
    matched_rule_id: str
    confidence: float = 1.0  # rule-based: a match is a match


@dataclass(frozen=True)
class Clarify:
    reason: str


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


# Patterns run on text that is NFKC-normalised, case-folded and whitespace-collapsed.
INTENT_RULES: tuple[IntentRule, ...] = (
    IntentRule(
        intent_code="diagnose_access_denial",
        rule_id="RULE-INTENT-ACCESS-DENIAL",
        patterns=(
            # "why was alex denied deepseek-coder": the verb must be followed by what was denied,
            # so "why was job 8823 blocked?" is not an access denial
            _rx(
                r"\bwhy\b.*\b(?:denied|blocked|refused)\s+(?:access\s+)?(?:to\s+|from\s+|for\s+)?\S"
            ),
            # "why can't alex access deepseek-coder": an explicit inability, never a bare "not"
            _rx(r"\bwhy\b.*\b(?:can't|cannot|can not|unable to|not allowed to)\b.*\baccess\b"),
            # "alex was denied access to deepseek-coder"
            _rx(r"\b(?:denied|blocked|refused)\b.*\baccess\b"),
        ),
    ),
)

# Base, third-person and -ing forms only: "cordoned"/"cancelled" report what happened and are
# not requests to do something.
_DESTRUCTIVE = _rx(
    r"\b(?:delet(?:e|es|ing)|cancel(?:s|l?ing)?|drain(?:s|ing)?|cordon(?:s|ing)?"
    r"|remov(?:e|es|ing)|kill(?:s|ing)?|purg(?:e|es|ing)|wip(?:e|es|ing)"
    r"|terminat(?:e|es|ing))\b"
)

# A destructive request can also be phrased as a causative or passive ("have his jobs deleted",
# "get them cancelled", "should be drained"). Without a causative/modal marker a bare past
# participle is a report of what happened ("was cordoned") and is not a request.
_DESTRUCTIVE_REQUEST = _rx(
    r"\b(?:hav(?:e|ing)|get(?:s|ting)?|got|mak(?:e|ing)|let|please|should|must|to be)\b"
    r".*\b(?:deleted|cancel(?:l)?ed|drained|cordoned|removed|killed|purged|wiped|terminated)\b"
)

_FOLLOW_UP = _rx(r"^(?:(?:and|also|then)\s+)?(?:what|how) about\b")
FOLLOW_UP_RULE_ID = "RULE-FOLLOWUP-CONTEXT"


# apostrophe lookalikes -> straight apostrophe (left/right quote, reversed, modifier letter, acute
# accent, grave accent, prime), so "can’t", "can´t" and "can`t" route like "can't"
_APOSTROPHES = str.maketrans(dict.fromkeys("‘’‛ʼ´`′", "'"))


def _normalise(query: str) -> str:
    # translate BEFORE NFKC (U+00B4 would otherwise decompose into a space plus an accent) and
    # again after, for any lookalike NFKC itself produces
    text = unicodedata.normalize("NFKC", query.translate(_APOSTROPHES)).casefold()
    return " ".join(text.translate(_APOSTROPHES).split())


def classify(
    query: str,
    prior_intents: Sequence[str],
    rules: Sequence[IntentRule] = INTENT_RULES,
) -> Routed | Clarify:
    """Route ``query`` to exactly one registered intent, or ask for clarification."""
    text = _normalise(query)
    destructive = _DESTRUCTIVE.search(text) is not None or (
        _DESTRUCTIVE_REQUEST.search(text) is not None
    )
    matched = [r for r in rules if any(p.search(text) for p in r.patterns)]

    if matched and destructive:
        return Clarify(cs.R_COMPOUND_DESTRUCTIVE)
    if len(matched) == 1:
        return Routed(matched[0].intent_code, matched[0].rule_id)
    if len(matched) > 1:
        return Clarify(cs.R_MULTIPLE_INTENTS)

    if _FOLLOW_UP.search(text):
        if destructive:
            return Clarify(cs.R_COMPOUND_DESTRUCTIVE)
        registered = {r.intent_code for r in rules}
        for code in reversed(prior_intents):  # session context first, newest turn first
            if code in registered:
                return Routed(code, FOLLOW_UP_RULE_ID)
        return Clarify(cs.R_FOLLOWUP_NO_CONTEXT)

    return Clarify(cs.R_NO_INTENT)
