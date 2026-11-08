"""Composition root: the only place that wires adapters to the application (R3).

Everything the service needs is built here from :class:`~src.config.Settings`, so the
FastAPI app and the tests construct the system the same way. Ports are registered by their
interface type, which is the extension seam for new entity types (NFR-10): a new fixture set,
one query-only port and one adapter are added with :meth:`Container.register_port` - nothing
that already exists changes. Readiness checks are registered by name.

A broken database or estate never crashes the build: it is logged and surfaces as a failing
readiness check, so an operator can see what is wrong through ``/readyz``.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

from src import dependency_check
from src.adapters.outbound.db.audit_store import SqliteAuditStore
from src.adapters.outbound.db.migrate import MigrationError, apply_migrations
from src.adapters.outbound.db.proposal_store import SqliteProposalStore
from src.adapters.outbound.db.session_store import SqliteSessionStore
from src.adapters.outbound.db.sqlite_writer import SqliteWriter
from src.adapters.outbound.sim.executor_adapter import SimExecutor
from src.adapters.outbound.sim.fixtures_adapter import SimProviders
from src.adapters.outbound.sim.idgen_adapter import SimIdGen
from src.adapters.outbound.sim.prose_adapter import SimProse
from src.adapters.outbound.token_idgen import SecureTokenIdGen
from src.application.access_denial_handler import INTENT as ACCESS_DENIAL_INTENT
from src.application.access_denial_handler import AccessDenialHandler
from src.application.audit_service import AuditService
from src.application.audit_writer import AuditWriter
from src.application.chat_service import ChatService
from src.application.confirmation_service import ConfirmationService
from src.application.destructive_handler import INTENT as DESTRUCTIVE_INTENT
from src.application.destructive_handler import DestructiveRefusalHandler
from src.application.dry_run_service import DryRunService
from src.application.entity_resolver import EntityResolver
from src.application.evidence_assembler import EvidenceAssembler
from src.application.evidence_service import EvidenceService
from src.application.node_triage_handler import INTENT as NODE_TRIAGE_INTENT
from src.application.node_triage_handler import NodeTriageHandler
from src.application.parallel_reads import ParallelReads
from src.application.pipeline import AnswerPipeline
from src.application.proposal_dispatcher import ProposalDispatcher
from src.application.proposal_service import ProposalService
from src.application.session_service import SessionService
from src.application.state_service import StateService
from src.application.tool_audit import TOOL_PORT_NAMES, ToolCallRecorder, audited
from src.application.unavailable import (
    UnavailableAuditUseCases,
    UnavailableConfirmUseCases,
    UnavailableDestructiveUseCases,
    UnavailableEvidenceUseCases,
    UnavailableExecutor,
    UnavailableProposalUseCases,
    UnavailableSessionUseCases,
)
from src.application.window_diagnosis_handler import INTENT as WINDOW_INTENT
from src.application.window_diagnosis_handler import WindowDiagnosisHandler
from src.config import Settings
from src.domain.result import is_failure
from src.ports.inbound import (
    AuditUseCases,
    ChatUseCases,
    ConfirmUseCases,
    DestructiveUseCases,
    EvidenceUseCases,
    ProposalUseCases,
    SessionUseCases,
    StateUseCases,
)
from src.ports.outbound import (
    AuditStorePort,
    CatalogPort,
    EventStorePort,
    ExecutorPort,
    GroupsPort,
    IdGenPort,
    JobsPort,
    LlmProsePort,
    NodesPort,
    PolicyPort,
    ProposalStorePort,
    ReservationsPort,
    RunbookRegistryPort,
    SessionStorePort,
    UnitOfWorkPort,
    UsersPort,
    WindowsPort,
)

logger = logging.getLogger(__name__)

# A readiness check returns None when healthy, otherwise a human-readable problem.
ReadinessCheck = Callable[[], str | None]

P = TypeVar("P")


@dataclass
class Container:
    settings: Settings
    writer: SqliteWriter | None
    ports: dict[type, object] = field(default_factory=dict)
    readiness: dict[str, ReadinessCheck] = field(default_factory=dict)

    def register_port(
        self, port_type: type[P], adapter: P, check: ReadinessCheck | None = None
    ) -> None:
        """Register ``adapter`` as the implementation of ``port_type``."""
        if not isinstance(adapter, port_type):
            raise TypeError(f"{type(adapter).__name__} does not implement {port_type.__name__}")
        self.ports[port_type] = adapter
        if check is not None:
            self.readiness[port_type.__name__] = check

    def port(self, port_type: type[P]) -> P:
        try:
            return self.ports[port_type]  # type: ignore[return-value]
        except KeyError:
            raise KeyError(f"no adapter registered for {port_type.__name__}") from None

    def close(self) -> None:
        if self.writer is not None:
            self.writer.close()


def configure_logging(level: str) -> None:
    """Apply ``M12_LOG_LEVEL`` to the ``src`` logger tree (one console handler if none exists)."""
    root = logging.getLogger("src")
    root.setLevel(level)
    if not root.handlers and not logging.getLogger().handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)


def build_container(settings: Settings) -> Container:
    configure_logging(settings.log_level)

    writer: SqliteWriter | None = None
    database_problem: str | None = None
    try:
        writer = SqliteWriter.open(settings.db_path)
        apply_migrations(writer, settings.migrations_dir)
    except (MigrationError, sqlite3.Error, OSError) as exc:
        database_problem = f"{type(exc).__name__}: {exc}"
        logger.error("database/migrations unavailable: %s", database_problem)

    try:
        providers = SimProviders.from_fixtures(settings.fixtures_dir, settings.clock_start)
    except BaseException:
        if writer is not None:
            writer.close()
        raise

    if is_failure(providers.estate):
        logger.error("estate failed to load: %s", "; ".join(providers.estate.observed))

    def dependencies() -> str | None:
        problems = dependency_check.check(settings)
        return "; ".join(problems) if problems else None

    def migrations() -> str | None:
        """Live check: the connection answers and every migration file is recorded."""
        if database_problem or writer is None:
            return database_problem or "database connection unavailable"
        # The connection is shared with the API threads, so the query goes through the store
        # (and so through the writer lock) instead of touching the connection directly.
        read = store.applied_migrations() if store is not None else None
        if read is None:
            return "database connection unavailable"
        if is_failure(read):
            return f"schema_migrations unreadable: {'; '.join(read.observed) or read.code}"
        applied = read.value
        expected = {path.name for path in settings.migrations_dir.glob("*.sql")}
        pending = sorted(expected - applied)
        return f"pending migrations: {pending}" if pending else None

    def estate() -> str | None:
        if is_failure(providers.estate):
            return "; ".join(providers.estate.observed) or providers.estate.code
        return None

    def clock() -> str | None:
        # Probing must not consume a read id: that would change the deterministic sequence.
        return None if providers.clock.available else "CLOCK_UNAVAILABLE"

    # -- the session ring: stores -> id generator (seeded above stored ids) -> pipeline -> service
    store, audit_store, idgen, session_problem = _wire_sessions(
        writer, database_problem, settings.audit_retention_cap
    )
    # Every provider port is wrapped once, so each read made during a turn is a recorded tool call
    # (FR-11, D3, D4); the wrapped instances are the ones every consumer and the registry receive.
    recorder = ToolCallRecorder()
    reads = ParallelReads(budget_seconds=settings.tool_fanout_budget_seconds, recorder=recorder)
    raw_ports = providers.as_ports()
    ports: dict[type, object] = {
        port_type: audited(port_type, raw_ports[port_type], name=name, recorder=recorder)
        for port_type, name in TOOL_PORT_NAMES.items()
    }
    users, catalog, policy = ports[UsersPort], ports[CatalogPort], ports[PolicyPort]
    groups, jobs, nodes = ports[GroupsPort], ports[JobsPort], ports[NodesPort]
    reservations, windows = ports[ReservationsPort], ports[WindowsPort]
    event_store = ports[EventStorePort]
    runbooks = ports[RunbookRegistryPort]
    prose = SimProse()
    pipeline = AnswerPipeline()
    # The diagnoser reads only through the provider ports: with a failed estate every read is a
    # typed PROVIDER_UNAVAILABLE, so the turn fails safely (503) while the app still starts.
    pipeline.register(
        ACCESS_DENIAL_INTENT,
        AccessDenialHandler(
            resolver=EntityResolver(users=users, catalog=catalog, policy=policy),
            assembler=EvidenceAssembler(policy=policy, events=event_store, reads=reads),
            prose=prose,
            idgen=idgen,
        ),
    )
    pipeline.register(
        WINDOW_INTENT,
        WindowDiagnosisHandler(
            resolver=EntityResolver(users=users, catalog=catalog, groups=groups, policy=policy),
            jobs=jobs,
            windows=windows,
            prose=prose,
            idgen=idgen,
        ),
    )
    pipeline.register(
        NODE_TRIAGE_INTENT,
        NodeTriageHandler(
            resolver=EntityResolver(users=users, catalog=catalog, nodes=nodes),
            nodes=nodes,
            runbooks=runbooks,
            prose=prose,
            idgen=idgen,
        ),
    )
    # a destructive request is refused after its target resolves; read-only ports only (AD-1, AD-4)
    pipeline.register(
        DESTRUCTIVE_INTENT,
        DestructiveRefusalHandler(
            resolver=EntityResolver(
                users=users, catalog=catalog, groups=groups, nodes=nodes, jobs=jobs
            )
        ),
    )
    # state inspection needs no database: a failed estate is a typed failure on every read
    state = StateService(
        users=users,
        catalog=catalog,
        policy=policy,
        groups=groups,
        jobs=jobs,
        nodes=nodes,
        reservations=reservations,
        windows=windows,
        event_store=event_store,
    )
    use_cases: SessionUseCases
    evidence: EvidenceUseCases
    audit_pages: AuditUseCases
    destructive: DestructiveUseCases
    confirm: ConfirmUseCases
    proposal_uc: ProposalUseCases
    executor: ExecutorPort
    if store is None or audit_store is None or writer is None or session_problem is not None:
        use_cases = UnavailableSessionUseCases(session_problem or "session store unavailable")
        evidence = UnavailableEvidenceUseCases(session_problem or "session store unavailable")
        audit_pages = UnavailableAuditUseCases(session_problem or "session store unavailable")
        destructive = UnavailableDestructiveUseCases(session_problem or "session store unavailable")
        confirm = UnavailableConfirmUseCases(session_problem or "session store unavailable")
        proposal_uc = UnavailableProposalUseCases(session_problem or "session store unavailable")
        executor = UnavailableExecutor(session_problem or "session store unavailable")
    else:
        use_cases = SessionService(
            store=store,
            clock=providers.clock,
            idgen=idgen,
            pipeline=pipeline,
            uow=writer,
            audit=AuditWriter(audit_store, idgen),
            recorder=recorder,
        )
        evidence = EvidenceService(
            store=store,
            users=users,
            catalog=catalog,
            policy=policy,
            groups=groups,
            jobs=jobs,
            nodes=nodes,
            reservations=reservations,
            windows=windows,
            event_store=event_store,
        )
        audit_pages = AuditService(
            sessions=store, audit=audit_store, retention_cap=settings.audit_retention_cap
        )
        destructive = DryRunService(
            sessions=store,
            proposals=SqliteProposalStore(writer),
            clock=providers.clock,
            idgen=idgen,
            resolver=EntityResolver(
                users=users, catalog=catalog, groups=groups, nodes=nodes, jobs=jobs
            ),
            jobs=jobs,
            nodes=nodes,
            uow=writer,
            audit=AuditWriter(audit_store, idgen),
            recorder=recorder,
            token_ttl_seconds=settings.gate_token_ttl_seconds,
        )
        proposal_store = SqliteProposalStore(writer)
        # the simulated executor: the only writer of simulated state, and the replacement point
        executor = SimExecutor(
            clock=providers.clock, stores=providers.executor_stores, proposals=proposal_store
        )
        confirm = ConfirmationService(
            proposals=proposal_store,
            sessions=store,
            clock=providers.clock,
            idgen=idgen,
            jobs=jobs,
            nodes=nodes,
            uow=writer,
            audit=AuditWriter(audit_store, idgen),
            recorder=recorder,
            dispatcher=ProposalDispatcher(
                proposals=proposal_store,
                executor=executor,
                clock=providers.clock,
                uow=writer,
                audit=AuditWriter(audit_store, idgen),
            ),
            token_ttl_seconds=settings.gate_token_ttl_seconds,
        )
        proposal_uc = ProposalService(proposals=proposal_store, dry_run=destructive)

    def sessions() -> str | None:
        if store is None or session_problem is not None:
            return session_problem or "session store unavailable"
        probe = store.get("sess-0000000000000000")  # a cheap primary-key lookup
        return probe.code if is_failure(probe) else None

    def audit() -> str | None:
        if audit_store is None or session_problem is not None:
            return session_problem or "audit store unavailable"
        probe = audit_store.page("sess-0000000000000000", 0, 1)  # an indexed miss
        return probe.code if is_failure(probe) else None

    logger.info("container built (fixtures=%s)", settings.fixtures_dir)
    container = Container(
        settings=settings,
        writer=writer,
        ports={**raw_ports, **ports},
        readiness={
            "dependencies": dependencies,
            "migrations": migrations,
            "estate": estate,
            "clock": clock,
            "sessions": sessions,
            "audit": audit,
        },
    )
    if store is not None:
        container.register_port(SessionStorePort, store)
    if audit_store is not None and writer is not None:
        container.register_port(ProposalStorePort, SqliteProposalStore(writer))
        container.register_port(AuditStorePort, audit_store)
        container.register_port(UnitOfWorkPort, writer)
    container.register_port(ToolCallRecorder, recorder)
    container.register_port(IdGenPort, idgen)
    container.register_port(LlmProsePort, prose)
    container.register_port(AnswerPipeline, pipeline)
    container.register_port(SessionUseCases, use_cases)
    container.register_port(EvidenceUseCases, evidence)
    container.register_port(AuditUseCases, audit_pages)
    container.register_port(DestructiveUseCases, destructive)
    container.register_port(ConfirmUseCases, confirm)
    container.register_port(ExecutorPort, executor)
    container.register_port(ProposalUseCases, proposal_uc)
    container.register_port(ChatUseCases, ChatService(sessions=use_cases, destructive=destructive))
    container.register_port(StateUseCases, state)
    return container


def _wire_sessions(
    writer: SqliteWriter | None, database_problem: str | None, retention_cap: int
) -> tuple[SqliteSessionStore | None, SqliteAuditStore | None, IdGenPort, str | None]:
    """The stores and a seeded id generator, plus the reason they are unusable (if any).

    The generator continues above every id already stored by a store (E43), so a restart on a file
    database never reissues a session, answer, claim, tool-call, audit or proposal id. Gate tokens
    are the exception: they are unguessable, never a sequence (story 2.2, IR-06).
    """
    if writer is None or database_problem:
        return None, None, _ids(), database_problem or "database connection unavailable"
    store = SqliteSessionStore(writer)
    audit_store = SqliteAuditStore(writer, retention_cap)
    counters = {}
    proposals = SqliteProposalStore(writer)
    for read in (
        store.highest_counters(),
        audit_store.highest_counters(),
        proposals.highest_counters(),
    ):
        if is_failure(read):  # also proves the schema is really there
            return store, audit_store, _ids(), "; ".join(read.observed) or read.code
        counters.update(read.value)
    return store, audit_store, _ids(counters), None


def _ids(counters: dict[str, int] | None = None) -> IdGenPort:
    """Deterministic ids for everything but the gate token, which is unguessable."""
    return SecureTokenIdGen(SimIdGen.from_counters(counters or {}))
