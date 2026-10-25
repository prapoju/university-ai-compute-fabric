"""Read-only provider ports (contracts.md section 3, OP-1..OP-12). Adapters implement these."""

from src.ports.outbound.catalog import CatalogPort
from src.ports.outbound.clock import ClockPort
from src.ports.outbound.event_store import EventStorePort, EventWindow
from src.ports.outbound.groups import GroupsPort
from src.ports.outbound.jobs import JobsPort
from src.ports.outbound.nodes import NodesPort
from src.ports.outbound.policy import PolicyPort
from src.ports.outbound.policy_content import PolicyContent, PolicyContentPort
from src.ports.outbound.reservations import ReservationsPort
from src.ports.outbound.runbook_registry import RunbookRegistryPort
from src.ports.outbound.users import UsersPort
from src.ports.outbound.windows import WindowsPort

__all__ = [
    "CatalogPort",
    "ClockPort",
    "EventStorePort",
    "EventWindow",
    "GroupsPort",
    "JobsPort",
    "NodesPort",
    "PolicyContent",
    "PolicyContentPort",
    "PolicyPort",
    "ReservationsPort",
    "RunbookRegistryPort",
    "UsersPort",
    "WindowsPort",
]
