"""src/dto.py is the contract's DTO module, copied verbatim - drift fails the build (R4)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config import PROJECT_ROOT
from src.dto import ErrorBody, NodeRecordDTO, UserRecordDTO

pytestmark = pytest.mark.unit

CONTRACT_DTO = PROJECT_ROOT / "planning/detailed-design/schemas/dto.py"
LOCAL_DTO = PROJECT_ROOT / "src/dto.py"


def _normalised(path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_dto_module_is_a_verbatim_copy_of_the_contract() -> None:
    assert _normalised(LOCAL_DTO) == _normalised(CONTRACT_DTO)


def test_records_reject_fields_outside_the_contract() -> None:
    # contracts.md section 0.3: "extra fields are a contract violation"
    with pytest.raises(ValidationError):
        UserRecordDTO(id="user#alex", display_name="Alex", role="student", email="a@x.edu")


def test_records_reject_values_outside_the_contract_enums() -> None:
    with pytest.raises(ValidationError):
        NodeRecordDTO(
            id="node#ws-gpu-01", hostname="ws-gpu-01", gpu_memory_gb=24,
            status="exploded", cordoned=False, error_code=None, health="healthy",
        )  # fmt: skip


def test_error_body_only_accepts_codes_from_the_typed_catalog() -> None:
    ok = ErrorBody(code="ENTITY_NOT_FOUND", status=404, message="m", retryable=False)
    assert ok.explanation is None
    with pytest.raises(ValidationError):
        ErrorBody(code="MADE_UP_CODE", status=500, message="m", retryable=False)
