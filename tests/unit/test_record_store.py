"""RecordStore is the NFR-10 extension seam, so it must police its own invariants."""

from __future__ import annotations

import pytest

from src.adapters.outbound.sim.record_store import RecordStore
from src.domain.result import is_ok

pytestmark = pytest.mark.unit


def test_duplicate_ids_including_case_only_differences_are_refused() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        RecordStore(["widget#a", "widget#a"], id_of=str)
    with pytest.raises(ValueError, match="duplicate"):
        RecordStore(["widget#a", "WIDGET#A"], id_of=str)


def test_get_and_browse_agree_when_ids_are_unique() -> None:
    store = RecordStore(["widget#b", "widget#a"], id_of=str)
    assert [r for r in store.browse("", 1, 10).value] == ["widget#a", "widget#b"]
    assert store.get("WIDGET#A").value == "widget#a"
    assert is_ok(store.get("widget#zzz")) and store.get("widget#zzz").value is None
