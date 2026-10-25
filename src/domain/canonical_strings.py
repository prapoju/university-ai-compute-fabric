"""Canonical strings: the single owner of every literal the Copilot says verbatim.

contracts.md section 0 / ARCHITECTURE "Consistency Conventions" (D57): these literals are data
owned by the deterministic core. Nothing else may re-word or re-type them; adapters import them
from here. Templates keep their ``{placeholders}`` and are filled with ``str.format``.
"""

from __future__ import annotations

S_ENF = "Entity Not Found in State: {ref_list}."
S_CNC = "Cannot confirm (insufficient evidence): checked {checked_list}."
S_PUA = "Provider unavailable — cannot answer."
S_ARF = "Action refused."
S_RBX = "no runbook available for code {code}."
S_CAP = "This confirms a proposal for delegation. It does not grant or assert authorization."
S_CLR = "Clarification required: {reason}."

# Reasons that fill ``S_CLR``. Fixed sentences without a trailing period (the template adds it).
R_NO_INTENT = "no registered intent matches this query"
R_COMPOUND_DESTRUCTIVE = (
    "the query mixes a diagnosis with a destructive action; submit them separately"
)
R_FOLLOWUP_NO_CONTEXT = "there is no earlier topic in this session to follow up on"
R_MULTIPLE_INTENTS = "more than one intent matches this query; ask one question at a time"


def clarification(reason: str) -> str:
    """The clarification literal for ``reason``."""
    return S_CLR.format(reason=reason)
