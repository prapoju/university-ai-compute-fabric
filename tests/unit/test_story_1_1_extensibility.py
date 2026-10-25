"""Story 1.1 - adding an entity type touches nothing that already exists (NFR-10).

Scenario: Adding an entity type needs no change elsewhere

The new ``widgets`` store, its port and its adapter all live in this test module; the only thing
it uses from production code is the public extension seam (``RecordStore`` + the container's
port registry). If extending the estate ever required editing an existing port, adapter,
route or test, this file could not pass without doing so.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from src.adapters.outbound.sim.record_store import RecordStore
from src.bootstrap import build_container
from src.config import Settings
from src.domain.result import Result, is_ok
from src.ports.outbound import NodesPort, UsersPort

pytestmark = pytest.mark.unit


class WidgetDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    colour: str


class WidgetsPort(ABC):
    @abstractmethod
    def get(self, id: str) -> Result[WidgetDTO | None]: ...

    @abstractmethod
    def browse(self, q: str, page: int, page_size: int) -> Result[list[WidgetDTO]]: ...


class FixtureWidgets(WidgetsPort):
    def __init__(self, store: RecordStore[WidgetDTO]) -> None:
        self._store = store

    def get(self, id: str) -> Result[WidgetDTO | None]:
        return self._store.get(id)

    def browse(self, q: str, page: int, page_size: int) -> Result[list[WidgetDTO]]:
        return self._store.browse(q, page, page_size)


def _widgets(tmp_path: Path) -> FixtureWidgets:
    path = tmp_path / "widgets.json"
    rows = [{"id": "widget#w-2", "colour": "red"}, {"id": "widget#w-1", "colour": "blue"}]
    path.write_text(json.dumps(rows), encoding="utf-8")
    records = [WidgetDTO.model_validate(row) for row in json.loads(path.read_text("utf-8"))]
    return FixtureWidgets(RecordStore(records, id_of=lambda w: w.id))


def test_a_new_entity_type_is_one_fixture_set_one_port_one_registration(tmp_path: Path) -> None:
    container = build_container(Settings.from_env({}))
    container.register_port(WidgetsPort, _widgets(tmp_path))

    widgets = container.port(WidgetsPort)
    assert [w.id for w in widgets.browse("", 1, 10).value] == ["widget#w-1", "widget#w-2"]
    assert widgets.get("WIDGET#W-1").value.colour == "blue"
    assert widgets.get("widget#nope").value is None


def test_existing_ports_are_unaffected_by_the_new_registration(tmp_path: Path) -> None:
    container = build_container(Settings.from_env({}))
    before = container.port(UsersPort).browse("", 1, 100).value
    container.register_port(WidgetsPort, _widgets(tmp_path))
    assert container.port(UsersPort).browse("", 1, 100).value == before
    assert len(container.port(NodesPort).browse("", 1, 100).value) == 32


def test_registering_an_object_that_does_not_implement_the_port_is_refused(tmp_path: Path) -> None:
    container = build_container(Settings.from_env({}))
    with pytest.raises(TypeError, match="WidgetsPort"):
        container.register_port(WidgetsPort, object())


def test_asking_for_an_unregistered_port_is_a_clear_error() -> None:
    container = build_container(Settings.from_env({}))
    with pytest.raises(KeyError, match="WidgetsPort"):
        container.port(WidgetsPort)


def test_the_container_wires_all_twelve_standard_ports() -> None:
    container = build_container(Settings.from_env({}))
    assert is_ok(container.port(UsersPort).get("user#alex"))
    assert len(container.ports) == 12
