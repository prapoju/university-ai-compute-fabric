"""Scripted GPU / heartbeat / metric injector with fault generation.

Drives the seeded `Fleet` so module tests can reproduce scenario S3 (UJ-3: node
`ws-gpu-11` cordoned with `ERR_THERMAL_88`) and the "node not found" negative without a
real monitoring stack. Every sample is scripted and every time step is taken from the
`FakeClock` — nothing here sleeps or reads wall-clock time.

Module 12 has no telemetry port (see ``ports-and-adapters.md``: the allowed read set is
OP-1..OP-12 + the inbound read routes); telemetry is therefore a *fleet* concern used to
mutate the estate that OP-6 `nodes_port` later reads. `sim_telemetry` never writes to the
Module-12 DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from support.clock import FakeClock
from support.fleet import TRIAGE_ERROR_CODE, TRIAGE_NODE_REF, Fleet

HEARTBEAT = "heartbeat"
GPU_UTIL = "gpu_util"
GPU_MEM_USED_GB = "gpu_mem_used_gb"
GPU_TEMP_C = "gpu_temp_c"
FAULT = "fault"

SAMPLE_KINDS = (HEARTBEAT, GPU_UTIL, GPU_MEM_USED_GB, GPU_TEMP_C, FAULT)

# Fan/airflow inspection is triggered from ~85 C on these units.
DEFAULT_THERMAL_THRESHOLD_C = 85
DEFAULT_THERMAL_RAMP_C = (60, 74, 88)


@dataclass(frozen=True)
class Sample:
    tick: int
    node_id: str
    kind: str
    value: Any
    at: str

    def as_dict(self) -> dict[str, Any]:
        return {"tick": self.tick, "node_id": self.node_id, "kind": self.kind,
                "value": self.value, "at": self.at}


class SimTelemetry:
    def __init__(
        self,
        fleet: Fleet,
        clock: FakeClock,
        *,
        heartbeat_period_s: float = 30,
    ) -> None:
        self.fleet = fleet
        self.clock = clock
        self.heartbeat_period_s = heartbeat_period_s
        self.samples: list[Sample] = []
        self.faults: list[tuple[str, str]] = []
        self._tick = 0

    # -- primitive injectors ----------------------------------------------
    def inject(self, node_id: str, kind: str, value: Any) -> Sample:
        spec = self.fleet.spec(node_id)  # KeyError if unknown -> "node not found"
        if kind not in SAMPLE_KINDS:
            raise ValueError(f"unknown sample kind {kind!r}; expected {SAMPLE_KINDS}")
        sample = Sample(tick=self._tick, node_id=spec.node_id, kind=kind, value=value,
                        at=self.clock.current)
        self.samples.append(sample)
        return sample

    def heartbeat(self, node_id: str) -> Sample:
        return self.inject(node_id, HEARTBEAT, True)

    def gpu_util(self, node_id: str, percent: float) -> Sample:
        return self.inject(node_id, GPU_UTIL, percent)

    def gpu_mem(self, node_id: str, used_gb: float) -> Sample:
        return self.inject(node_id, GPU_MEM_USED_GB, used_gb)

    def temperature(self, node_id: str, celsius: float) -> Sample:
        return self.inject(node_id, GPU_TEMP_C, celsius)

    # -- scripted scenarios ------------------------------------------------
    def tick(self, *, advance_s: float | None = None) -> int:
        """Advance one monitoring tick: heartbeat every healthy node + move clock."""
        self._tick += 1
        for record in self.fleet.select(health="healthy"):
            self.heartbeat(record.id)
        self.clock.advance(seconds=self.heartbeat_period_s if advance_s is None else advance_s)
        return self._tick

    def script_healthy(self, node_id: str) -> list[Sample]:
        """A nominal sample set for one node (no state change)."""
        out = [self.heartbeat(node_id), self.gpu_util(node_id, 12.0), self.temperature(node_id, 41.0)]
        return out

    def script_thermal_fault(
        self,
        node_id: str = TRIAGE_NODE_REF,
        *,
        error_code: str = TRIAGE_ERROR_CODE,
        ramp_c: Iterable[float] = DEFAULT_THERMAL_RAMP_C,
        threshold_c: float = DEFAULT_THERMAL_THRESHOLD_C,
        step_s: float = 5.0,
        cordon: bool = True,
    ) -> list[Sample]:
        """Ramp temperatures; once ``threshold_c`` is crossed, fault the node and cordon it.

        Returns exactly the samples emitted for this script. The node's OP-6 record now
        reports ``status='fault'``, ``cordoned=True``, ``error_code=error_code`` —
        the S3 precondition.
        """
        emitted: list[Sample] = [self.heartbeat(node_id)]
        faulted = False
        for celsius in ramp_c:
            emitted.append(self.temperature(node_id, celsius))
            self.clock.advance(seconds=step_s)
            if celsius >= threshold_c:
                self.fleet.fault(node_id, error_code, cordon=cordon)
                emitted.append(self.inject(node_id, FAULT, error_code))
                self.faults.append((self.fleet.spec(node_id).node_id, error_code))
                faulted = True
                break
        if not faulted:
            raise AssertionError("thermal ramp never crossed the fault threshold")
        return emitted

    def script_restart(self, node_id: str, *, error_code: str | None = None) -> list[Sample]:
        """Recover a node: uncordon it and resume heartbeats."""
        self.fleet.uncordon(node_id)
        if error_code is not None:
            self.inject(node_id, FAULT, f"recovered:{error_code}")
        return [self.heartbeat(node_id), self.gpu_util(node_id, 0.0), self.temperature(node_id, 38.0)]

    # -- inspection --------------------------------------------------------
    def drain(self) -> list[Sample]:
        return list(self.samples)

    def by_kind(self, kind: str) -> list[Sample]:
        return [s for s in self.samples if s.kind == kind]

    def for_node(self, node_id: str) -> list[Sample]:
        ref = self.fleet.spec(node_id).node_id
        return [s for s in self.samples if s.node_id == ref]

    def last(self) -> Sample:
        return self.samples[-1]
