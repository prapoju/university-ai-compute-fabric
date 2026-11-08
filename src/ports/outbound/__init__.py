"""Outbound ports: the read-only providers (contracts.md section 3, OP-1..OP-12), the id generator
(OP-13), the prose writer (OP-14), the Module-12-owned session and audit stores and the unit of
work over them.
Adapters implement these."""

from src.ports.outbound.audit_store import AuditEntry, AuditStorePort
from src.ports.outbound.catalog import CatalogPort
from src.ports.outbound.clock import ClockPort
from src.ports.outbound.event_store import EventStorePort, EventWindow
from src.ports.outbound.groups import GroupsPort
from src.ports.outbound.idgen import IdGenPort
from src.ports.outbound.jobs import JobsPort
from src.ports.outbound.llm_prose import LlmProsePort
from src.ports.outbound.nodes import NodesPort
from src.ports.outbound.policy import PolicyPort
from src.ports.outbound.policy_content import PolicyContent, PolicyContentPort
from src.ports.outbound.proposal_store import ProposalStorePort
from src.ports.outbound.reservations import ReservationsPort
from src.ports.outbound.runbook_registry import RunbookRegistryPort
from src.ports.outbound.session_store import SessionStorePort, StoredSession
from src.ports.outbound.unit_of_work import Transaction, UnitOfWorkError, UnitOfWorkPort
from src.ports.outbound.users import UsersPort
from src.ports.outbound.windows import WindowsPort

__all__ = [
    "AuditEntry",
    "AuditStorePort",
    "ProposalStorePort",
    "CatalogPort",
    "ClockPort",
    "EventStorePort",
    "EventWindow",
    "GroupsPort",
    "IdGenPort",
    "JobsPort",
    "LlmProsePort",
    "NodesPort",
    "PolicyContent",
    "PolicyContentPort",
    "PolicyPort",
    "ReservationsPort",
    "RunbookRegistryPort",
    "SessionStorePort",
    "StoredSession",
    "Transaction",
    "UnitOfWorkError",
    "UnitOfWorkPort",
    "UsersPort",
    "WindowsPort",
]
