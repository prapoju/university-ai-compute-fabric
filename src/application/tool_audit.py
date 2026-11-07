"""Tool-call recording for the audit log (FR-11, contracts.md Q-port-3, story 1.5 D3, D4).

The composition root wraps each provider port once with :func:`audited`. The wrapper delegates to
the adapter and, while a turn is active, records ``toolcall.<port>.<method>`` with its bound
arguments, status and result size. The active turn lives in a ``contextvars.ContextVar``, so no
handler, resolver or port signature changes, and the session-less evidence and state routes,
which share the same wrapped ports, record nothing.

Pure application ring: stdlib and ports only (R3).
"""

from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, TypeVar

from src.domain.result import Failure, Result
from src.ports.outbound import (
    CatalogPort,
    EventStorePort,
    GroupsPort,
    JobsPort,
    NodesPort,
    PolicyContentPort,
    PolicyPort,
    ReservationsPort,
    RunbookRegistryPort,
    UsersPort,
    WindowsPort,
)

P = TypeVar("P")

# D3: the provider ports whose calls are tool calls. Clock, idgen, prose and stores are not.
TOOL_PORT_NAMES: dict[type, str] = {
    UsersPort: "users_port",
    CatalogPort: "catalog_port",
    PolicyPort: "policy_port",
    GroupsPort: "groups_port",
    JobsPort: "jobs_port",
    NodesPort: "nodes_port",
    ReservationsPort: "reservations_port",
    WindowsPort: "windows_port",
    EventStorePort: "event_store_port",
    PolicyContentPort: "policy_content_port",
    RunbookRegistryPort: "runbook_registry_port",
}


@dataclass(frozen=True)
class RecordedCall:
    tool_name: str
    params: Mapping[str, Any]
    status: str  # "ok" | "failure"
    error_code: str | None = None
    result_count: int | None = None
    result: Mapping[str, Any] = field(default_factory=dict)  # extra summary fields (head call)


class ToolCallRecorder:
    """The calls of the active turn, in call order.

    Forward constraint for story 1-6: a parallel fan-out appends in completion order, so
    ``ParallelReads`` must reserve the slots in argument order before the gather (D-2.1/2.3).
    """

    def __init__(self) -> None:
        self._calls: ContextVar[list[RecordedCall] | None] = ContextVar(
            f"tool_calls_{id(self)}", default=None
        )

    @contextmanager
    def turn(self) -> Iterator[list[RecordedCall]]:
        calls: list[RecordedCall] = []
        token = self._calls.set(calls)
        try:
            yield calls
        finally:
            self._calls.reset(token)

    def record(self, call: RecordedCall) -> None:
        """Append ``call`` to the active turn; a no-op when no turn is active."""
        calls = self._calls.get()
        if calls is not None:
            calls.append(call)


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if isinstance(value, list | tuple):
        return [_dump(item) for item in value]
    return value


def _count(value: Any, optional: bool) -> int | None:
    if isinstance(value, list | tuple):
        return len(value)
    if value is None:
        return 0
    return 1 if optional else None


def _delegate(
    port_type: type, adapter: Any, tool: str, method: str, recorder: ToolCallRecorder
) -> Callable[..., Result[Any]]:
    signature = inspect.signature(getattr(port_type, method))
    optional = "None" in str(signature.return_annotation)
    target = getattr(adapter, method)

    def call(self: Any, *args: Any, **kwargs: Any) -> Result[Any]:
        result = target(*args, **kwargs)
        bound = signature.bind(self, *args, **kwargs)
        params = {k: _dump(v) for k, v in list(bound.arguments.items())[1:]}  # drop self
        if isinstance(result, Failure):
            recorded = RecordedCall(tool, params, "failure", error_code=result.code)
        else:
            recorded = RecordedCall(tool, params, "ok", result_count=_count(result.value, optional))
        recorder.record(recorded)
        return result

    call.__name__ = method
    call.__doc__ = getattr(port_type, method).__doc__
    return call


def audited(port_type: type[P], adapter: P, *, name: str, recorder: ToolCallRecorder) -> P:
    """An instance of ``port_type`` that delegates to ``adapter`` and records each call.

    Generic over the port's abstract methods, so a new port needs no new code (NFR-10).
    """
    methods = {
        method: _delegate(port_type, adapter, f"toolcall.{name}.{method}", method, recorder)
        for method in sorted(port_type.__abstractmethods__)
    }
    wrapper = type(f"Audited{port_type.__name__}", (port_type,), methods)
    return wrapper()
