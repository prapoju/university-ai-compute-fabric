"""OP-3 ``policy_port`` - access-policy clauses. Query-only."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import AccessPolicyClauseDTO


class PolicyPort(ABC):
    @abstractmethod
    def get(self, clause_id: str) -> Result[AccessPolicyClauseDTO | None]:
        """Clause for ``policy#...``; a miss is ``Ok(None)``."""

    @abstractmethod
    def for_model(self, model_id: str) -> Result[list[AccessPolicyClauseDTO]]:
        """Clauses restricting a model, in stable ``clause_id`` order (AD-2, AD-14).

        An unknown model is ``Failure("ENTITY_NOT_FOUND")``.
        """

    @abstractmethod
    def browse(self, q: str, page: int, page_size: int) -> Result[list[AccessPolicyClauseDTO]]:
        """Case-folded exact-id match; empty ``q`` lists all."""
