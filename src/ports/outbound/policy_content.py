"""OP-11 ``policy_content_port`` - curated institutional policy text, treated as data (AD-11)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.result import Result


@dataclass(frozen=True)
class PolicyContent:
    """``{source_id, text, version}`` with ``1 <= len(text) <= 2000``."""

    source_id: str
    text: str
    version: str


class PolicyContentPort(ABC):
    @abstractmethod
    def get(self, source_id: str) -> Result[PolicyContent]:
        """Content for a curated source; an unknown source is ``Failure("ENTITY_NOT_FOUND")``."""
