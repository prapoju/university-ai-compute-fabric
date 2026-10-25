"""Simulated ``llm_prose_port`` (OP-14): a deterministic stand-in for the local LLM.

Impl-1 needs no GPU and no Ollama (C-5): this writer returns fixed connective sentences that
never repeat anything from the evidence sections, so the answer's facts stay exactly the ones the
deterministic core produced and cited (AD-2). Tests can script its output (to prove the prose
guard rejects facts), inject an outage, and read back how often it was called and with what.
"""

from __future__ import annotations

import threading
from collections import deque

from src.domain.error_catalog import fail
from src.domain.result import Ok, Result
from src.dto import ProsePromptDTO
from src.ports.outbound import LlmProsePort


class SimProse(LlmProsePort):
    DEFAULT = (
        "Here is what I found. The details below come straight from the records I looked up, "
        "and each one is cited so you can check it yourself."
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._failed = False
        self._script: deque[str] = deque()
        self._calls = 0
        self._last_prompt: ProsePromptDTO | None = None

    # -- LlmProsePort --------------------------------------------------------------------------
    def compose(self, prompt: ProsePromptDTO) -> Result[str]:
        with self._lock:
            self._calls += 1
            self._last_prompt = prompt
            if self._failed:
                return fail("LLM_UNAVAILABLE")
            return Ok(self._script.popleft() if self._script else self.DEFAULT)

    # -- simulation controls and observation (not part of the port) ----------------------------
    @property
    def call_count(self) -> int:
        with self._lock:
            return self._calls

    @property
    def last_prompt(self) -> ProsePromptDTO | None:
        with self._lock:
            return self._last_prompt

    def script(self, *outputs: str) -> None:
        """The next calls return ``outputs`` in order; afterwards the default prose resumes."""
        with self._lock:
            self._script.extend(outputs)

    def fail(self) -> None:
        with self._lock:
            self._failed = True

    def recover(self) -> None:
        with self._lock:
            self._failed = False
