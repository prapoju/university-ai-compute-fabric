"""Outbound port OP-15: the executor, the only place that may change state (AD-1, AD-3, AD-15).

``dispatch`` hands one confirmed proposal to the executor under the frozen request
``{proposal_id, action, selector, gate_token, dry_run_ref}`` and answers the frozen
``ExecutorResult``; ``get`` reads what the executor recorded. The port is the replacement point of
the contract: only the dispatcher calls ``dispatch``. The executor applies exactly the items of the
snapshot the request refers to and never re-enumerates scope; it writes no proposal state.
Every operation returns a typed ``Result`` (AD-12).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import ExecutorRequestDTO, ExecutorResultDTO


class ExecutorPort(ABC):
    @abstractmethod
    def dispatch(self, request: ExecutorRequestDTO) -> Result[ExecutorResultDTO]:
        """Apply the referenced snapshot once; an identical retry returns the stored result."""

    @abstractmethod
    def get(self, proposal_id: str) -> Result[ExecutorResultDTO | None]:
        """What the executor recorded for ``proposal_id``; a miss is ``Ok(None)``."""
