"""Pure classification of a destructive request (FR-09, NFR-8, AD-4, Annex AD-30).

Given a query that already looks destructive, decide *which* closed ``ActionVerb`` it asks for and
*what* it aims at. Nothing here resolves an entity, reads the clock or touches state: resolution is
the handler's job, and the refusal itself is a canonical literal. The query text is data, never
control: a word outside the verb table is not a destructive intent, and a sentence that mixes a
destructive verb with a second request is never split, it goes to clarification (FR-01, AD-4).

Input is the text normalised by ``intent.normalise_query`` (NFKC, case-folded, spaces collapsed).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from src.domain import canonical_strings as cs
from src.dto import ActionVerb

INTENT_CODE = "propose_destructive_action"
RULE_ID = "RULE-INTENT-DESTRUCTIVE"

# Every surface form (base, third person, -ing, participle) -> the closed enum value. ``terminate``
# is ``cancel_jobs`` (docs/impl2-rules.md); the enum itself never grows (D4).
_VERB_FORMS: dict[ActionVerb, tuple[str, ...]] = {
    "delete_jobs": (
        "delete deletes deleting deleted remove removes removing removed "
        "purge purges purging purged wipe wipes wiping wiped"
    ).split(),
    "cancel_jobs": (
        "cancel cancels canceling cancelling canceled cancelled "
        "terminate terminates terminating terminated kill kills killing killed"
    ).split(),
    "drain_node": "drain drains draining drained".split(),
    "cordon_node": "cordon cordons cordoning cordoned".split(),
}
_FORM_TO_VERB: dict[str, ActionVerb] = {
    form: verb for verb, forms in _VERB_FORMS.items() for form in forms
}
_VERB = re.compile(r"\b(" + "|".join(sorted(_FORM_TO_VERB, key=len, reverse=True)) + r")\b")

JOB_VERBS: frozenset[ActionVerb] = frozenset({"delete_jobs", "cancel_jobs"})
NODE_VERBS: frozenset[ActionVerb] = frozenset({"cordon_node", "drain_node"})

# A second request next to a destructive verb makes the query compound (D5).
_DIAGNOSTIC = re.compile(
    r"\b(?:show|list|tell|explain|diagnose|check|display|find|why|what|how|when|which)\b"
)

_ID = r"[^\s,;:?!()\[\]']+"  # no quote: "group#group-2's jobs" names group-2
_TYPED = re.compile(rf"\b(?P<kind>group|job|node)#(?P<id>{_ID})")
_NUMBERED = re.compile(r"\b(?P<kind>group|job)[ -]?(?P<n>\d+)\b")
_NODE_ID = re.compile(r"\bws-gpu-\d+\b")
_BARE = re.compile(r"\b(?:for|of)\s+(?:the\s+)?(?P<token>[a-z0-9][a-z0-9_.-]*)")
# words that can follow "for"/"of" without being a name
_NOT_A_NAME = frozenset(
    "all every each any the this that these those them it its my our your their his her "
    "entire whole lab group groups job jobs node nodes everything everyone pending running "
    "active queued".split()
)

# Words a fleet-wide request may use besides its verb (D3). Anything else names a referent this
# module does not understand ("alex's jobs", "the database", "them"): such a request is clarified,
# never widened to the whole fleet (AD-4, review D-1).
_GENERIC = frozenset(
    "a an the all every each any both entire whole pending running active queued stuck "
    "lab labs fleet cluster job jobs node nodes everything please now immediately right away "
    "kindly to for of in on at from and then also".split()
)
_WORD = re.compile(r"[a-z0-9']+")

# Fleet-wide scope phrases (D3): a closed list, so a scope is never guessed from free text.
_SCOPE_NODES = re.compile(r"\b(?:all|every)\s+nodes?\b")
_SCOPE_JOBS = re.compile(r"\b(?:all|every)\s+jobs?\b")

TargetKind = Literal["group", "job", "node"]
Scope = Literal["any", "nodes", "jobs"]


@dataclass(frozen=True)
class Target:
    """One named reference. ``token`` is what the resolver takes: ``group-2`` or ``group#nope``."""

    kind: TargetKind
    token: str


@dataclass(frozen=True)
class Fleet:
    """A fleet-wide scope (``entire lab``, ``all nodes``) or no target: nothing to resolve."""

    scope: Scope = "any"


@dataclass(frozen=True)
class DestructiveRequest:
    verb: ActionVerb
    target: Target | Fleet


@dataclass(frozen=True)
class Compound:
    """A destructive verb together with a second request: clarification, never decomposition."""

    reason: str = cs.R_COMPOUND_DESTRUCTIVE


@dataclass(frozen=True)
class Unnamed:
    """A destructive verb aimed at something this module cannot name: clarification, not a guess."""

    reason: str = cs.R_MISSING_TARGET


def accepts(verb: ActionVerb, target: Target | Fleet) -> bool:
    """Whether ``verb`` applies to that kind of target (contracts P3)."""
    if isinstance(target, Fleet):
        if target.scope == "nodes":
            return verb in NODE_VERBS
        if target.scope == "jobs":
            return verb in JOB_VERBS
        return True
    if verb in JOB_VERBS:
        return target.kind in ("group", "job")
    return target.kind == "node"


def _targets(text: str) -> list[Target]:
    """Every distinct named reference of ``text``, in input order (typed beats bare)."""
    found: list[tuple[int, Target]] = []
    taken: list[tuple[int, int]] = []

    def free(span: tuple[int, int]) -> bool:
        return all(span[1] <= a or span[0] >= b for a, b in taken)

    def add(match: re.Match[str], target: Target) -> None:
        taken.append(match.span())
        found.append((match.start(), target))

    for m in _TYPED.finditer(text):
        add(m, Target(m["kind"], f"{m['kind']}#{m['id'].rstrip('.')}"))  # type: ignore[arg-type]
    for m in _NUMBERED.finditer(text):
        if free(m.span()):
            add(m, Target(m["kind"], f"{m['kind']}-{m['n']}"))  # type: ignore[arg-type]
    for m in _NODE_ID.finditer(text):
        if free(m.span()):
            add(m, Target("node", m.group(0)))
    if not found:  # a bare word after for/of is read as a group key ("jobs for cs201")
        for m in _BARE.finditer(text):
            token = m["token"].rstrip(".")
            if token not in _NOT_A_NAME:
                add(m, Target("group", token))
    ordered: list[Target] = []
    for _, target in sorted(found, key=lambda pair: pair[0]):
        if target not in ordered:
            ordered.append(target)
    return ordered


def _scope(text: str) -> Scope:
    if _SCOPE_NODES.search(text):
        return "nodes"
    if _SCOPE_JOBS.search(text):
        return "jobs"
    return "any"  # "entire lab", "whole lab", "the lab", or no target at all


def _names_something_else(text: str) -> bool:
    """Whether, besides its verbs, ``text`` holds a word that is not part of a generic scope."""
    return any(w not in _GENERIC for w in _WORD.findall(text) if w not in _FORM_TO_VERB)


def parse_destructive(text: str) -> DestructiveRequest | Compound | Unnamed | None:
    """The request ``text`` makes, ``Compound``/``Unnamed`` when it cannot be acted on, or ``None``.

    ``None`` means no word of the closed verb table appears: it is not a destructive intent.
    """
    verbs = [_FORM_TO_VERB[m.group(1)] for m in _VERB.finditer(text)]
    if not verbs:
        return None
    targets = _targets(text)
    if len(set(verbs)) > 1 or len(targets) > 1 or _DIAGNOSTIC.search(text):
        return Compound()
    if targets:
        return DestructiveRequest(verbs[0], targets[0])
    if _names_something_else(text):
        return Unnamed()  # "delete alex's jobs": a referent we cannot resolve is not "everything"
    return DestructiveRequest(verbs[0], Fleet(_scope(text)))
