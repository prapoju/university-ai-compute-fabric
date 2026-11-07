"""The evidence and citation reads (story 1.4): ``get_answer_evidence`` and ``get_citation``.

Read-only over two sources: the Module-12-owned answer store, for what an answer cited and the
snippet it stored, and the read-only provider ports, for the record a citation names today. A
citation resolves only if a stored answer cites it (AD-8) and its source is still in state;
anything else is ``S_ENF``, never a guess. A provider failure passes through as the typed 503
(AD-12). Unrelated to ``evidence_assembler``, which gathers records for a diagnosis.

``EvidenceService._sources`` is the single map from citation type to the port that holds its
records: a new entity type adds one row (NFR-10). Clock reads are not records: they are rebuilt
from the stored entry (D4).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import get_args

from src.domain.diagnosis import clock_read_from_entry
from src.domain.error_catalog import fail
from src.domain.result import Failure, Ok, Result, is_failure
from src.dto import EvidenceDTO, GetAnswerEvidenceResponse, GetCitationResponse, RecordDTO
from src.ports.inbound import EvidenceUseCases
from src.ports.outbound import (
    CatalogPort,
    EventStorePort,
    GroupsPort,
    JobsPort,
    NodesPort,
    PolicyPort,
    ReservationsPort,
    SessionStorePort,
    UsersPort,
    WindowsPort,
)

CITATION_TYPES = frozenset(get_args(EvidenceDTO.model_fields["source_type"].annotation))
SourceReader = Callable[[str], Result[RecordDTO | None]]


class EvidenceService(EvidenceUseCases):
    def __init__(
        self,
        *,
        store: SessionStorePort,
        users: UsersPort,
        catalog: CatalogPort,
        policy: PolicyPort,
        groups: GroupsPort,
        jobs: JobsPort,
        nodes: NodesPort,
        reservations: ReservationsPort,
        windows: WindowsPort,
        event_store: EventStorePort,
    ) -> None:
        self._store = store
        self._sources: dict[str, SourceReader] = {
            "user": users.get,
            "model": catalog.get,
            "policy": policy.get,
            "group": groups.get,
            "job": jobs.get,
            "node": nodes.get,
            "reservation": reservations.get,
            "window": windows.get,
            "event": event_store.get,
        }

    @property
    def source_types(self) -> frozenset[str]:
        """The citation types resolved through a provider port (every type but ``clock``)."""
        return frozenset(self._sources)

    def get_answer_evidence(self, answer_id: str) -> Result[GetAnswerEvidenceResponse]:
        stored = self._store.answer_evidence(answer_id)
        if is_failure(stored):
            return stored
        if stored.value is None:
            return _not_found(answer_id)
        return Ok(GetAnswerEvidenceResponse(evidence=stored.value))

    def get_citation(self, citation_id: str) -> Result[GetCitationResponse]:
        kind, separator, rest = citation_id.partition("#")
        if not (separator and rest) or kind not in CITATION_TYPES:
            return _not_found(citation_id)  # D6: a malformed id cannot name a source (P2)
        snippet = self._store.cited_snippet(citation_id)
        if is_failure(snippet):
            return snippet
        if snippet.value is None:
            return _not_found(citation_id)  # no stored answer cites it (AD-8)
        if kind == "clock":
            clock_read = clock_read_from_entry(citation_id, snippet.value)
            if clock_read is None:
                return _not_found(citation_id)
            return Ok(GetCitationResponse(source_record=clock_read, snippet=snippet.value))
        record = self._sources[kind](citation_id)
        if is_failure(record):
            return record
        if record.value is None:
            return _not_found(citation_id)  # the source is no longer in state
        return Ok(GetCitationResponse(source_record=record.value, snippet=snippet.value))


def _not_found(ref: str) -> Failure:
    return fail("ENTITY_NOT_FOUND", ref_list=ref)
