"""Pure ``Instant`` helpers (contracts.md section 0.1): ISO-8601 UTC strings <-> datetimes.

Nothing here reads the wall clock - only the injected ``clock_port`` may do that (R2) - so
the deterministic core can compare and shift instants safely.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

_INSTANT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z$")


def parse_instant(value: str) -> datetime:
    """Parse an ``Instant`` into an aware UTC datetime; raise ``ValueError`` otherwise."""
    # fullmatch: ``$`` would also accept a trailing newline (e.g. from an env file)
    if not _INSTANT_RE.fullmatch(value):
        raise ValueError(f"not an Instant (ISO-8601 UTC): {value!r}")
    fmt = "%Y-%m-%dT%H:%M:%S.%fZ" if "." in value else "%Y-%m-%dT%H:%M:%SZ"
    try:
        return datetime.strptime(value, fmt).replace(tzinfo=UTC)
    except ValueError as exc:  # right shape, impossible date such as 2026-02-30
        raise ValueError(f"not an Instant (ISO-8601 UTC): {value!r} ({exc})") from exc


def is_instant(value: str) -> bool:
    """Non-raising twin of :func:`parse_instant`."""
    try:
        parse_instant(value)
    except ValueError:
        return False
    return True


def format_instant(value: datetime) -> str:
    """Format as an ``Instant`` with millisecond precision, converting to UTC."""
    utc = value.astimezone(UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"


def add_seconds(value: str, seconds: float) -> str:
    return format_instant(parse_instant(value) + timedelta(seconds=seconds))
