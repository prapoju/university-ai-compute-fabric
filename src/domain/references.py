"""Deterministic extraction of entity references from a routed query (FR-03, AD-7, D6).

Extraction finds the *tokens the operator typed* - nothing else. Resolving them against state
(exact match under case-folding, never fuzzy) is the resolver's job, and the intent fixes which
type each token has. No LLM, no fuzzy matching, and a token is only ever a substring of the query:
the extractor cannot invent a reference.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
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


_POLICY_REF = re.compile(r"\bpolicy#(?P<id>[^\s,;:?!()\[\]]+)", re.I)


def extract_policy_references(query: str) -> list[str]:
    """Typed ``policy#...`` references named in the query: once each (case-folded, as the store
    compares them), case as first typed, in input order."""
    found: list[str] = []
    seen: set[str] = set()
    for match in _POLICY_REF.finditer(_clean(query)):
        ref = _strip(match["id"])
        key = f"policy#{ref}" if ref else None
        if key and key.casefold() not in seen:
            seen.add(key.casefold())
            found.append(key)
    return found


_SEPARATOR = r"[\s-]+"


def _typed_at(text: str, name: str) -> int:
    """Where the operator typed ``name``: the full key, else its bare id (``-`` may be typed as a
    space: ``group 99`` names ``group#group-99``); ``-1`` when it is not in the query at all."""
    bare = name.partition("#")[2] or name
    for needle in (name, bare):
        typed = _SEPARATOR.join(re.escape(w) for w in needle.casefold().split("-"))
        match = re.search(rf"(?<!\w){typed}(?!\w)", text)
        if match is not None:
            return match.start()
    return -1


def in_input_order(query: str, names: Sequence[str]) -> tuple[str, ...]:
    """Each unresolved name once (case-folded), in the order the query typed it (contracts.md
    resolve_entities Q4). A name the query does not hold (a session-context entity of a follow-up)
    was named by an earlier turn, so it comes first; ties keep the given order."""
    text = _clean(query).casefold()
    unique: dict[str, str] = {}
    for name in names:
        unique.setdefault(name.casefold(), name)
    return tuple(sorted(unique.values(), key=lambda name: _typed_at(text, name)))


@dataclass(frozen=True)
class NodeTriageReferences:
    """The raw node token and the error code of a node-triage question, case as typed."""

    node: str
    code: str


# words that follow "node" in a triage question but never are its id: "the node is cordoned"
# names no node, so it is a clarification and never ENTITY_NOT_FOUND node#is (I2-51)
_NODE_STOP = (
    r"(?:is|are|was|were|has|have|had|cordoned|drained|reports|shows|with|the|a|an|it|that|in|on"
    r"|and|of|for|to)"
)
_NODE_REF = re.compile(rf"\bnode(?:#|\s+)(?!{_NODE_STOP}(?=[\s,;:?!.]|$))(?P<node>{_TOKEN})", re.I)
_NODE_CODE = re.compile(rf"\bcode\s+(?P<code>{_TOKEN})", re.I)
# A node or a code named without its word: "ws-gpu-11 cordoned ERR_THERMAL_88" (NFR-1 corpus).
# Tried only when the word form is absent, so the word form is read exactly as before.
_BARE_NODE_REF = re.compile(r"\b(?P<node>ws-[a-z0-9-]+)\b", re.I)
_BARE_NODE_CODE = re.compile(r"\b(?P<code>err_[a-z0-9_]+)\b", re.I)
_RUNBOOK_WORD = re.compile(r"\brunbooks?\b", re.I)


def extract_node_triage_references(query: str) -> NodeTriageReferences | None:
    """The node and the code of ``Node <node> is cordoned with code <code>`` (and variants)."""
    text = _clean(query)
    node = _NODE_REF.search(text) or _BARE_NODE_REF.search(text)
    code = _NODE_CODE.search(text) or _BARE_NODE_CODE.search(text)
    if node is None or code is None:
        return None
    node_token, code_token = _strip(node["node"]), _strip(code["code"])
    if node_token and code_token:
        return NodeTriageReferences(node_token, code_token)
    return None


def asks_for_runbook(query: str) -> bool:
    """Whether the operator explicitly asks for a runbook (the word ``runbook``, any case)."""
    return _RUNBOOK_WORD.search(_clean(query)) is not None
