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
            _rx(r"\bwhy\b.*\b(?:denied|blocked|refused|rejected|forbidden)\b"),
            _rx(r"\bwhy\b.*\b(?:can't|cannot|can not|isn't|is not|not)\b.*\baccess\b"),
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

_FOLLOW_UP = _rx(r"^(?:(?:and|also|then)\s+)?(?:what|how) about\b")
FOLLOW_UP_RULE_ID = "RULE-FOLLOWUP-CONTEXT"


def _normalise(query: str) -> str:
    text = unicodedata.normalize("NFKC", query).casefold()
    text = text.replace("’", "'")  # curly apostrophe -> straight
    return " ".join(text.split())


def classify(
    query: str,
    prior_intents: Sequence[str],
    rules: Sequence[IntentRule] = INTENT_RULES,
) -> Routed | Clarify:
    """Route ``query`` to exactly one registered intent, or ask for clarification."""
    text = _normalise(query)
    destructive = _DESTRUCTIVE.search(text) is not None
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
