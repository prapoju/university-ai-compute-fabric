"""Write-time redaction of audit summaries (NFR-11, I15, D45)."""

from __future__ import annotations

import copy

import pytest

from src.domain.redaction import REDACTED, redact

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "key",
    [
        "api_key", "apikey", "token", "secret", "password", "authorization", "credential",
        "API_KEY", "ApiKey", "Token", "client_secret", "db_password", "Authorization",
        "aws_credentials", "refresh_token",
    ],
)  # fmt: skip
def test_every_secret_key_pattern_is_redacted_case_insensitively(key: str) -> None:
    assert redact({key: "hunter2", "model": "deepseek-coder"}) == {
        key: REDACTED,
        "model": "deepseek-coder",
    }


def test_a_secret_key_hides_a_structured_value_too() -> None:
    assert redact({"credential": {"user": "u", "pw": "p"}}) == {"credential": REDACTED}


def test_nesting_through_dicts_lists_and_tuples() -> None:
    value = {
        "outer": [{"token": "t1"}, ("api_key=abc123", "user#alex")],
        "n": 3,
        "none": None,
    }
    assert redact(value) == {
        "outer": [{"token": REDACTED}, (f"api_key={REDACTED}", "user#alex")],
        "n": 3,
        "none": None,
    }


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Authorization: Bearer sk-live-123", f"Authorization: {REDACTED}"),
        ("use bearer sk-live-123 please", f"use bearer {REDACTED} please"),
        ("BEARER abc.def-ghi", f"BEARER {REDACTED}"),
        ("api_key=abc123", f"api_key={REDACTED}"),
        ("API_KEY = abc123, next", f"API_KEY = {REDACTED}, next"),
        ("token: t0ps3cret", f"token: {REDACTED}"),
        ("password:hunter2;user=bob", f"password:{REDACTED};user=bob"),
        (
            "alex denied, Authorization: Bearer sk-live-123 api_key=abc123 token: t0ps3cret",
            f"alex denied, Authorization: {REDACTED} api_key={REDACTED} token: {REDACTED}",
        ),
    ],
)
def test_value_patterns_inside_strings(text: str, expected: str) -> None:
    assert redact(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('api_key="abc123"', f'api_key="{REDACTED}"'),
        ("api_key='abc123'", f"api_key='{REDACTED}'"),
        ('password = "my secret pass"', f'password = "{REDACTED}"'),
        ('{"api_key": "abc123"}', f'{{"api_key": "{REDACTED}"}}'),
        ('{"token":"t0ps3cret","ok":"alex"}', f'{{"token":"{REDACTED}","ok":"alex"}}'),
        ("Authorization: Basic dXNlcjpwYXNz", f"Authorization: {REDACTED}"),
        ("x-api-key=abc123", f"x-api-key={REDACTED}"),
        ("X-Api-Key: abc123", f"X-Api-Key: {REDACTED}"),
    ],
)
def test_quoted_json_basic_and_hyphenated_forms_inside_strings(text: str, expected: str) -> None:
    redacted = redact(text)
    assert redacted == expected
    assert "abc123" not in redacted and "t0ps3cret" not in redacted and "dXNl" not in redacted


def test_a_hyphenated_secret_key_is_redacted() -> None:
    assert redact({"Api-Key": "x", "x-auth-token": "y", "user": "alex"}) == {
        "Api-Key": REDACTED,
        "x-auth-token": REDACTED,
        "user": "alex",
    }


def test_sets_and_frozensets_are_walked_and_keep_their_type() -> None:
    walked = redact({"s": {"api_key=abc123", "user#alex"}, "f": frozenset({"token: t1"})})
    assert walked == {
        "s": {f"api_key={REDACTED}", "user#alex"},
        "f": frozenset({f"token: {REDACTED}"}),
    }
    assert isinstance(walked["s"], set) and isinstance(walked["f"], frozenset)


@pytest.mark.parametrize(
    "benign",
    [
        "user#alex", "deepseek-coder", "policy#catalog.4.2", "model#deepseek-coder",
        "group#CS-101", "ws-gpu-11", "diagnose_access_denial", "q=alex", "status: ok",
    ],
)  # fmt: skip
def test_benign_values_are_untouched(benign: str) -> None:
    assert redact(benign) == benign
    assert redact({"ref": benign}) == {"ref": benign}


def test_the_input_is_never_mutated() -> None:
    value = {"token": "t", "items": [{"password": "p"}], "text": "api_key=abc123"}
    before = copy.deepcopy(value)
    result = redact(value)
    assert value == before
    assert result is not value and result["items"] is not value["items"]


def test_non_string_scalars_and_non_string_keys_pass_through() -> None:
    assert redact({1: "x", "count": 2, "ok": True, "ratio": 0.5}) == {
        1: "x",
        "count": 2,
        "ok": True,
        "ratio": 0.5,
    }
