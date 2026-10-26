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
    IntentRule(
        intent_code="diagnose_schedule_window",
        rule_id="RULE-INTENT-SCHEDULE-WINDOW",
        patterns=(
            # "why can't group 4 run their fine-tuning job right now"
            _rx(
                r"\bwhy\b.*\b(?:can't|cannot|can not|won't|unable to|not able to"
                r"|(?:isn't|is not|aren't)\b.*\bable to)\b.*\b(?:run|start|launch|execute)\b"
            ),
            # "why is group 4's job pending / not running / waiting"
            _rx(
                r"\bwhy\b.*\bjobs?\b.*\b(?:not running|not starting|pending|waiting|queued|stuck)\b"
            ),
            # "when can group 4 run their job" / "when does the next window open"
            _rx(r"\bwhen\b.*\b(?:can|will|could)\b.*\b(?:run|start|launch)\b"),
            _rx(r"\bwhen\b.*\bnext\b.*\bwindow\b"),
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
# participle is a report of what happened ("was cordoned") and is not a request - and so is a
# participle inside an embedded question ("tell me why job 8823 was cancelled", "let me know if
# it was drained") or a perfect passive ("why have the jobs been cancelled"): the text between
# the marker and the participle never crosses into one. "got" is past ("it got cancelled"), and
# "get" with no object is a passive ("did it get cancelled"); neither is a request.
_PARTICIPLE = (
    r"(?:deleted|cancel(?:l)?ed|drained|cordoned|removed|killed|purged|wiped|terminated)"
)
_REPORTED = (
    r"\b(?:why|how|whether|been)\b"
    # "which"/"who"/"what" are also relative pronouns ("the jobs which are pending"), so like
    # "if"/"when"/"where" they only open a question after a verb that asks or tells
    r"|\b(?:know|tell|ask|check|see|confirm|show|explain|wonder)\s+(?:(?:me|us|him|her|them)\s+)?"
    r"(?:if|when|where|what|which|who|whom|whose)\b"
)
_UNTIL_PARTICIPLE = rf"(?:(?!{_REPORTED}).)*?"
_DESTRUCTIVE_REQUEST = _rx(
    # causative or imperative: "have his jobs deleted", "please make sure they are removed"
    rf"\b(?:hav(?:e|ing)|mak(?:e|ing)|let|please)\b{_UNTIL_PARTICIPLE}\b{_PARTICIPLE}\b"
    # "get" takes its object first: "get them cancelled" asks, "did it get cancelled" reports
    rf"|\bget(?:s|ting)?\b(?!\s*{_PARTICIPLE}\b){_UNTIL_PARTICIPLE}\b{_PARTICIPLE}\b"
    # modal or infinitive passive: "should be drained", "must all be purged", "to be removed"
    rf"|\b(?:should|must)\s+(?:\S+\s+){{0,3}}be\s+{_PARTICIPLE}\b"
    rf"|\bto be\s+(?:\S+\s+)?{_PARTICIPLE}\b"
)

_FOLLOW_UP = _rx(r"^(?:(?:and|also|then)\s+)?(?:what|how) about\b")
FOLLOW_UP_RULE_ID = "RULE-FOLLOWUP-CONTEXT"


# apostrophe lookalikes -> straight apostrophe (left/right quote, reversed, modifier letter, acute
# accent, grave accent, prime), so "can’t", "can´t" and "can`t" route like "can't"
_APOSTROPHES = str.maketrans(dict.fromkeys("‘’‛ʼ´`′", "'"))


def fold_apostrophes(text: str) -> str:
    """Replace the usual apostrophe lookalikes by a straight apostrophe (shared with extraction)."""
    return text.translate(_APOSTROPHES)


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
