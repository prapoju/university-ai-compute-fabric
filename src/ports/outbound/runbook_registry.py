"""OP-12 ``runbook_registry_port`` - registered runbook templates (AD-9).

Read-only: templates are validated when the fixtures load (>= 1 step; a physical-intervention
template needs an approved source). ``register`` is intentionally not a port method (AD-1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import RunbookTemplateDTO


class RunbookRegistryPort(ABC):
    @abstractmethod
    def get(self, error_code: str) -> Result[RunbookTemplateDTO | None]:
        """Exact-code lookup; an unregistered code is ``Ok(None)``."""
