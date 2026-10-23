"""`explain_assert` — assert a decision carries >= 1 rule id + the observed values.

Module 12's central discipline is that every deterministic decision is *bound to a rule
and to observed values*, never read from LLM output (AD-2, AD-8, AD-11):

  - `Intent` = ``{intent_code, confidence, matched_rule_id}`` — "rule-based classifier
    output (AD-11), never LLM-derived" (contracts.md §0.5).
  - `Diagnosis.diagnosis_class` is "a pure function of the EvidenceSet" (AD-2).
  - every `Claim.text` is bound to ``>= 1`` citation (AD-8, L1).
  - the 200-canonical codes are decided by code, not prose (D54).

`explain_assert` is deliberately **duck-typed**: it accepts a mapping, a dataclass, or a
future `Intent`/`Diagnosis`/`Answer` object, so the same helper works before and after the
module source lands. It never mutates its argument.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

_MISSING = object()

_RULE_KEYS = ("rule_ids", "matched_rule_id", "rule_id", "diagnosis_class", "reason_class",
              "intent_code", "canonical", "canonical_code")
_RULE_NESTED = ("intent", "classification", "decision")
_OBSERVED_KEYS = ("observed", "observed_values", "observed_state", "values", "facts",
                  "observed_facts")
_CITATION_KEYS = ("citations", "citation_ids", "claim_citations", "evidence_citations")


@dataclass
class Explanation:
    rule_ids: tuple[str, ...]
    observed: dict[str, Any] = field(default_factory=dict)
    citations: tuple[str, ...] = ()
    label: str | None = None
    raw: Any = None


def _get(obj: Any, name: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, _MISSING)
    return getattr(obj, name, _MISSING)


def _as_str_list(value: Any) -> list[str]:
    if value is _MISSING or value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [str(k) for k in value]
    if isinstance(value, Iterable):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, Mapping) and "citation_id" in item:
                out.append(str(item["citation_id"]))
        return out
    return [str(value)]


def coerce_explanation(decision: Any) -> Explanation:
    """Extract (rule_ids, observed, citations) from a mapping/object."""
    if isinstance(decision, Explanation):
        return decision

    rule_ids: list[str] = []
    observed: dict[str, Any] = {}
    citations: list[str] = []

    # rule ids (flat + one level of nesting for the classifier output)
    for key in _RULE_KEYS:
        rule_ids.extend(_as_str_list(_get(decision, key)))
    for key in _RULE_NESTED:
        nested = _get(decision, key)
        if nested is not _MISSING and nested is not None:
            for nkey in _RULE_KEYS:
                rule_ids.extend(_as_str_list(_get(nested, nkey)))

    # observed values
    for key in _OBSERVED_KEYS:
        value = _get(decision, key)
        if value is not _MISSING and value is not None:
            observed = dict(value)
            break

    # citations: direct lists, evidence[], and claims[].claim_citations[]
    for key in _CITATION_KEYS:
        citations.extend(_as_str_list(_get(decision, key)))
    for evidence in _as_list(_get(decision, "evidence")):
        citations.extend(_as_str_list(_get(evidence, "citation_id")))
    for claim in _as_list(_get(decision, "claims")):
        citations.extend(_as_str_list(_get(claim, "claim_citations")))
        for cit in _as_list(_get(claim, "evidence")):
            citations.extend(_as_str_list(_get(cit, "citation_id")))

    # de-dup, preserve order
    seen: set[str] = set()
    unique_rules = [r for r in rule_ids if not (r in seen or seen.add(r))]
    seen_cit: set[str] = set()
    unique_citations = [c for c in citations if not (c in seen_cit or seen_cit.add(c))]

    label = _get(decision, "label")
    return Explanation(
        rule_ids=tuple(unique_rules),
        observed=observed,
        citations=tuple(unique_citations),
        label=None if label is _MISSING else label,
        raw=decision,
    )


def _as_list(value: Any) -> list[Any]:
    if value is _MISSING or value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def explain_assert(
    decision: Any,
    *,
    rule_id: str | None = None,
    rule_ids: Iterable[str] | None = None,
    values: Mapping[str, Any] | None = None,
    observed: Mapping[str, Any] | None = None,
    min_citations: int = 1,
    require_rule: bool = True,
    require_citations: bool = True,
    label: str | None = None,
) -> Explanation:
    """Assert the decision is *explained*: it names a rule, the values it acted on, and
    (by default) at least ``min_citations`` citations. Returns the coerced `Explanation`.

    ``values`` (alias ``observed``) is checked key-by-key against the observed values the
    decision carries; a missing or mismatched key fails.
    """
    explanation = coerce_explanation(decision)
    where = f"[{label or explanation.label or 'decision'}]"

    if require_rule:
        assert explanation.rule_ids, (
            f"{where} has no rule id: a deterministic decision must cite its rule "
            f"(AD-2/AD-11); got rule_ids={explanation.rule_ids}"
        )
    if rule_id is not None:
        assert rule_id in explanation.rule_ids, (
            f"{where} expected rule_id {rule_id!r}; got {explanation.rule_ids}"
        )
    if rule_ids is not None:
        expected = set(rule_ids)
        missing = expected - set(explanation.rule_ids)
        assert not missing, f"{where} missing rule ids {sorted(missing)}; got {explanation.rule_ids}"

    expected_values = dict(values or {})
    expected_values.update(observed or {})
    for key, expected in expected_values.items():
        assert key in explanation.observed, (
            f"{where} carries no observed value for {key!r}; observed={explanation.observed}"
        )
        actual = explanation.observed[key]
        assert actual == expected, (
            f"{where} observed[{key!r}] = {actual!r}, expected {expected!r}"
        )

    if require_citations:
        assert len(explanation.citations) >= min_citations, (
            f"{where} has {len(explanation.citations)} citation(s); "
            f"needs >= {min_citations} (AD-8)"
        )
    return explanation
