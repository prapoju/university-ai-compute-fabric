"""Seeded GPU fleet (test double for the operational estate behind OP-6 `nodes_port`).

The hardware brief (``docs/project - university_ai_compute_management_platform_brief.md``)
specifies a *heterogeneous* local GPU fleet: **many** machines with 24 GB GPUs and
**one** stronger machine with **two 48 GB GPUs**. The brief does not fix a count, so
``DEFAULT_STANDARD_NODE_COUNT`` is a *fixture knob*, not a contract value — tune it per
test. The default is large enough to include `node#ws-gpu-11` (scenario S3 / UJ-3).

Contract refs:
  - ``contracts.md`` §0.3 `NodeRecord`
    ``{id, hostname, gpu_memory_gb, status, cordoned, error_code, health}`` —
    "extra fields are a contract violation".
  - §3 OP-6 `nodes_port`: ``get`` / ``select`` / ``browse``.
  - §0.1 `EntityKey` `{type}#{id}` -> node refs are ``node#<hostname>``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

from support.ids import IdFactory

# §0.3 NodeRecord.status
NODE_STATUSES = ("available", "reserved", "active", "fault")

STANDARD_PER_GPU_VRAM_GB = 24
BIG_GPU_COUNT = 2
BIG_PER_GPU_VRAM_GB = 48

# Fixture default (see module docstring). Not a contract constant.
DEFAULT_STANDARD_NODE_COUNT = 31

# Scenario S3 subject — must exist in the seeded fleet.
TRIAGE_NODE_REF = "node#ws-gpu-11"
TRIAGE_ERROR_CODE = "ERR_THERMAL_88"


@dataclass(frozen=True)
class NodeRecord:
    """§0.3 `NodeRecord` — exactly these seven fields, no more, no less."""

    id: str
    hostname: str
    gpu_memory_gb: int
    status: str
    cordoned: bool
    error_code: str | None
    health: str

    FIELDS = ("id", "hostname", "gpu_memory_gb", "status", "cordoned", "error_code", "health")

    def __post_init__(self) -> None:
        if self.status not in NODE_STATUSES:
            raise ValueError(f"status outside §0.3 enum: {self.status!r}")

    def as_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.FIELDS}


@dataclass(frozen=True)
class NodeSpec:
    """Static hardware spec of a fleet member (fixture-only; not a contract record)."""

    node_id: str
    hostname: str
    gpu_count: int
    per_gpu_vram_gb: int

    @property
    def total_vram_gb(self) -> int:
        return self.gpu_count * self.per_gpu_vram_gb

    @property
    def is_big(self) -> bool:
        return self.gpu_count > 1

    def as_record(
        self,
        *,
        status: str = "available",
        cordoned: bool = False,
        error_code: str | None = None,
        health: str = "healthy",
    ) -> NodeRecord:
        """Project the spec into a contract-exact `NodeRecord`.

        `gpu_memory_gb` is the node's *aggregate* VRAM (24 for a standard 1x24
        machine, 96 for the 2x48 machine); the per-GPU breakdown stays on the spec.
        """
        return NodeRecord(
            id=self.node_id,
            hostname=self.hostname,
            gpu_memory_gb=self.total_vram_gb,
            status=status,
            cordoned=cordoned,
            error_code=error_code,
            health=health,
        )


@dataclass
class Fleet:
    """Mutable in-memory estate. Fresh per test; never touches a real provider."""

    specs: list[NodeSpec] = field(default_factory=list)
    ids: IdFactory = field(default_factory=IdFactory)
    # node_id -> overrides applied on top of the healthy default
    _state: dict[str, dict[str, Any]] = field(default_factory=dict)

    # -- construction ------------------------------------------------------
    @classmethod
    def build(
        cls,
        standard_nodes: int = DEFAULT_STANDARD_NODE_COUNT,
        *,
        big_node_number: int | None = None,
        seed: int = 12,
    ) -> "Fleet":
        if standard_nodes < 1:
            raise ValueError("a fleet needs at least one standard node")
        number_of_big = big_node_number or standard_nodes + 1
        ids = IdFactory(seed=seed)
        specs: list[NodeSpec] = []
        for n in range(1, standard_nodes + 1):
            hostname = f"ws-gpu-{n:02d}"
            specs.append(NodeSpec(f"node#{hostname}", hostname, 1, STANDARD_PER_GPU_VRAM_GB))
        big_hostname = f"ws-gpu-{number_of_big:02d}"
        specs.append(
            NodeSpec(
                f"node#{big_hostname}",
                big_hostname,
                BIG_GPU_COUNT,
                BIG_PER_GPU_VRAM_GB,
            )
        )
        return cls(specs=specs, ids=ids)

    # -- lookup ------------------------------------------------------------
    def __len__(self) -> int:
        return len(self.specs)

    def __iter__(self) -> Iterator[NodeSpec]:
        return iter(self.specs)

    @property
    def big_node(self) -> NodeSpec:
        return next(spec for spec in self.specs if spec.is_big)

    @property
    def standard_nodes(self) -> list[NodeSpec]:
        return [spec for spec in self.specs if not spec.is_big]

    def spec(self, node_id: str) -> NodeSpec:
        for spec in self.specs:
            if spec.node_id == node_id or spec.hostname == node_id:
                return spec
        raise KeyError(f"unknown node: {node_id}")

    def get(self, node_id: str) -> NodeRecord | None:
        """OP-6 ``get`` — `NodeRecord | null`."""
        try:
            spec = self.spec(node_id)
        except KeyError:
            return None
        return spec.as_record(**self._state.get(spec.node_id, {}))

    def records(self) -> list[NodeRecord]:
        return [self.get(spec.node_id) for spec in self.specs]  # type: ignore[misc]

    # -- mutation (the estate responding to telemetry) ---------------------
    def update(self, node_id: str, **changes: Any) -> NodeRecord:
        spec = self.spec(node_id)
        current = {"status": "available", "cordoned": False, "error_code": None, "health": "healthy"}
        current.update(self._state.get(spec.node_id, {}))
        current.update(changes)
        self._state[spec.node_id] = current
        return spec.as_record(**current)

    def cordon(self, node_id: str, *, error_code: str | None = None) -> NodeRecord:
        return self.update(node_id, cordoned=True, error_code=error_code)

    def uncordon(self, node_id: str) -> NodeRecord:
        return self.update(node_id, cordoned=False, error_code=None, status="available", health="healthy")

    def fault(self, node_id: str, error_code: str, *, cordon: bool = True) -> NodeRecord:
        """Mark a node faulted (and cordoned, as the monitoring alert does in S3)."""
        return self.update(
            node_id,
            status="fault",
            cordoned=cordon,
            error_code=error_code,
            health="fault",
        )

    # -- selection (mirrors OP-6 `select`) --------------------------------
    def select(self, **filters: Any) -> list[NodeRecord]:
        out: list[NodeRecord] = []
        for record in self.records():
            if all(getattr(record, key) == value for key, value in filters.items()):
                out.append(record)
        return out

    def faulted(self) -> list[NodeRecord]:
        return self.select(status="fault")

    def cordoned(self) -> list[NodeRecord]:
        return self.select(cordoned=True)

    def assert_all_healthy(self) -> None:
        for record in self.records():
            assert record.health == "healthy", record
            assert record.status == "available", record
            assert record.cordoned is False, record
            assert record.error_code is None, record


def build_fleet(
    standard_nodes: int = DEFAULT_STANDARD_NODE_COUNT,
    *,
    big_node_number: int | None = None,
    seed: int = 12,
) -> Fleet:
    return Fleet.build(standard_nodes=standard_nodes, big_node_number=big_node_number, seed=seed)
