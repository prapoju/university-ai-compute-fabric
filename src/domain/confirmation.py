"""Pure confirmation rules (story 2.3, AD-5, AD-6; contracts ``confirm_and_dispatch`` P2-P4).

Given the stored proposal and the instant of one clock read, decide whether the token is still
fresh, whether the presented token is the stored one, whether there is anything to confirm and how
the re-queried set differs from the stored one. Nothing here reads the clock, a port or the
database: the application ring feeds it values. The expiry is derived from the snapshot and the
lifetime setting in force, never stored (story 2.3 D2).
"""

from __future__ import annotations

import hmac
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from src.domain.instants import parse_instant
from src.dto import AffectedItemDTO

STALE_LAST_LINE = "confirmation disabled: run a new dry-run"


def elapsed_seconds(snapshot_timestamp: str, now: str) -> float:
    """Seconds from the snapshot to ``now`` (negative if the clock went back)."""
    return (parse_instant(now) - parse_instant(snapshot_timestamp)).total_seconds()


def token_is_fresh(snapshot_timestamp: str, now: str, ttl_seconds: int) -> bool:
    """P2: accepted while ``now - snapshot <= ttl`` (``<=``: the boundary instant is accepted)."""
    return parse_instant(now) - parse_instant(snapshot_timestamp) <= timedelta(seconds=ttl_seconds)


def expired_delta(snapshot_timestamp: str, now: str, ttl_seconds: int) -> str:
    """The text a stale answer carries for an expired token (the code is ``CONFIRMATION_STALE``)."""
    elapsed = elapsed_seconds(snapshot_timestamp, now)
    return f"token expired: {elapsed:.3f} s after the snapshot, lifetime {ttl_seconds} s"


def tokens_match(presented: str, stored: str) -> bool:
    """Constant-time comparison, so the answer time does not tell how much of a guess was right."""
    return hmac.compare_digest(presented.encode("utf-8"), stored.encode("utf-8"))


def has_actionable(items: Sequence[AffectedItemDTO]) -> bool:
    """P4: something to confirm; an empty set and a set with nothing actionable have none."""
    return any(item.actionable for item in items)


@dataclass(frozen=True)
class Delta:
    """How the re-queried set differs from the stored one, each part ordered by key."""

    added: tuple[AffectedItemDTO, ...] = ()
    removed: tuple[AffectedItemDTO, ...] = ()
    changed: tuple[tuple[AffectedItemDTO, AffectedItemDTO], ...] = ()  # (stored, current)

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.changed)


def _identity(item: AffectedItemDTO) -> tuple[str, bool, str]:
    return (item.actionable_field, item.actionable, item.actionable_value)


def diff(stored: Sequence[AffectedItemDTO], current: Sequence[AffectedItemDTO]) -> Delta:
    """P3: compare on ``(id, actionable status)``: what left, what joined, what changed."""
    before = {item.key: item for item in stored}
    after = {item.key: item for item in current}
    return Delta(
        added=tuple(after[key] for key in sorted(after.keys() - before.keys())),
        removed=tuple(before[key] for key in sorted(before.keys() - after.keys())),
        changed=tuple(
            (before[key], after[key])
            for key in sorted(before.keys() & after.keys())
            if _identity(before[key]) != _identity(after[key])
        ),
    )


def _change(old: AffectedItemDTO, new: AffectedItemDTO) -> str:
    if old.actionable_value != new.actionable_value:
        return f"{old.key} {old.actionable_value} -> {new.actionable_value}"
    return f"{old.key} actionable {old.actionable} -> {new.actionable}"


def delta_lines(delta: Delta) -> list[str]:
    """One line per difference: added, then removed, then changed, each ordered by key."""
    return [
        *(f"added {item.key}" for item in delta.added),
        *(f"removed {item.key}" for item in delta.removed),
        *(_change(old, new) for old, new in delta.changed),
    ]


def delta_text(delta: Delta) -> str:
    """The ``{delta}`` of ``Snapshot stale: {delta}.``: the lines joined by ``; ``."""
    return "; ".join(delta_lines(delta))
