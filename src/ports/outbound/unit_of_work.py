"""Unit of work over the Module-12-owned stores (review D-6, log I2-06, TG-I2-1).

The application opens one ``atomic()`` block around the writes that must commit together (a turn's
``Answer`` and its audit rows, AD-10). Every store write made inside the block joins the same
transaction; the outermost exit commits, or rolls back if the block raised or was ``abort()``-ed.
No driver type appears here (R1): a begin or commit failure surfaces as :class:`UnitOfWorkError`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Protocol


class UnitOfWorkError(Exception):
    """The transaction could not be opened or committed; nothing was written."""


class Transaction(Protocol):
    def abort(self) -> None:
        """Mark the transaction rollback-only: the outermost exit rolls it back."""


class UnitOfWorkPort(ABC):
    @abstractmethod
    def atomic(self) -> AbstractContextManager[Transaction]:
        """One transaction; nested blocks on the same thread join the outer one."""
