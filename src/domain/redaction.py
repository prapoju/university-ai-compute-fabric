"""Write-time redaction of audit summaries (NFR-11, contracts.md section 5 I15, D45).

Pure: ``redact`` returns a new structure and never mutates its input. The value of every key whose
name contains a secret-looking word is replaced, and inside string values a ``bearer <token>`` or a
``<secret-key>=<value>`` / ``<secret-key>: <value>`` pair keeps its key and loses its value. Ids
such as ``user#alex`` or ``policy#catalog.4.2`` are left untouched.
"""

from __future__ import annotations

import re

REDACTED = "[REDACTED]"

_SECRET_WORDS = ("api_key", "apikey", "token", "secret", "password", "authorization", "credential")
# a hyphen reads as an underscore, so an HTTP-style ``x-api-key`` is as secret as ``api_key``
_SECRET_WORD = "|".join(re.escape(word).replace("_", "[_-]") for word in _SECRET_WORDS)
_VALUE = r"[^\s,;&\"'()\[\]{}]+"
_SCHEME = r"(?:bearer|basic)\s+"

# ``key=value``, ``key: value``, ``key="quoted value"`` and a JSON ``"key": "value"``; a ``bearer``
# or ``basic`` scheme in front of the value goes with it
_PAIR = re.compile(
    rf"(?P<key>[\w.-]*(?:{_SECRET_WORD})[\w.-]*)(?P<kq>[\"']?)(?P<sep>\s*[=:]\s*)(?:{_SCHEME})?"
    rf"(?:(?P<q>[\"'])(?:(?!(?P=q)).)*(?P=q)|{_VALUE})",
    re.IGNORECASE,
)
_BEARER = re.compile(rf"\b(?P<scheme>bearer)\s+{_VALUE}", re.IGNORECASE)


def is_secret_key(name: str) -> bool:
    folded = name.casefold().replace("-", "_")
    return any(word in folded for word in _SECRET_WORDS)


def redact_text(text: str) -> str:
    def pair(m: re.Match[str]) -> str:
        quote = m["q"] or ""
        return f"{m['key']}{m['kq']}{m['sep']}{quote}{REDACTED}{quote}"

    text = _PAIR.sub(pair, text)
    return _BEARER.sub(lambda m: f"{m['scheme']} {REDACTED}", text)


def redact(value: object) -> object:
    """A redacted copy of ``value`` (dicts, lists, tuples and sets are walked recursively)."""
    if isinstance(value, dict):
        return {
            key: REDACTED if isinstance(key, str) and is_secret_key(key) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, set | frozenset):
        return type(value)(redact(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value
