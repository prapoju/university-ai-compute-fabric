"""The rule id a policy clause prints next to itself in its evidence snippet (story 1.6, task 4.4).

A policy evidence snippet reads ``policy#catalog.4.2 (RULE-CAT-04) [not-in-allowlist]: ...``. The
rule id is the parenthesised code right after the clause id. The extraction is a fixed pattern, so
no DTO field is added and the contract does not change. Pure domain function (no I/O, no clock).
"""

from __future__ import annotations

import re

RULE_CODE = r"RULE-[A-Z]+-\d{2}"


def rule_of_clause(snippet: str, clause_id: str) -> str | None:
    """The rule id printed next to ``clause_id`` in ``snippet``, or None when it is not there."""
    pattern = re.compile(rf"{re.escape(clause_id)} \(({RULE_CODE})\)")
    match = pattern.search(snippet)
    return match.group(1) if match else None
