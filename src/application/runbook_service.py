"""``get_runbook`` (contracts.md section 2, story 3.3): a pure registry read, never a generation.

The route returns the registered template's steps and provenance as two separate sections (AD-9).
Nothing is written and nothing is audited: a session-less read (story 1.5 D2). The id check runs
before any read, so a malformed code is a 400 and never reaches the registry.
"""

from __future__ import annotations

import re

from src.domain import canonical_strings as cs
from src.domain.error_catalog import fail
from src.domain.result import Failure, Ok, Result, is_failure
from src.domain.runbook import is_renderable
from src.dto import GetRunbookResponse
from src.ports.inbound import RunbookUseCases
from src.ports.outbound import RunbookRegistryPort

_ERROR_CODE = re.compile(r"[A-Za-z0-9._-]{1,64}")  # contracts.md get_runbook P1


class RunbookService(RunbookUseCases):
    def __init__(self, *, registry: RunbookRegistryPort) -> None:
        self._registry = registry

    def get_runbook(self, error_code: str) -> Result[GetRunbookResponse]:
        if not _ERROR_CODE.fullmatch(error_code):
            return Failure(
                "VALIDATION_MALFORMED_BODY",
                observed=(f"error_code {error_code!r} does not match the contract pattern",),
            )
        found = self._registry.get(error_code)  # exact-code lookup (AD-9)
        if is_failure(found):
            return found
        if found.value is None:
            return Failure("RUNBOOK_NOT_FOUND", message=cs.S_RBX.format(code=error_code))
        template = found.value
        if not is_renderable(template):
            return fail("RUNBOOK_TEMPLATE_UNSOURCED", template_id=template.template_id)
        return Ok(
            GetRunbookResponse(
                steps=list(template.steps),
                provenance={"source": template.approved_source, "version": template.version},
            )
        )
