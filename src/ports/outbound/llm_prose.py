"""OP-14 ``llm_prose_port``: connective prose around an answer whose facts are already fixed.

The LLM is invoked exactly once per answer, for prose only (AD-2): the evidence sections it
receives are delimited data copied verbatim (AD-11), and nothing it returns is ever read as a
diagnosis, claim, citation or recommendation. The port only *generates* text; the prose guard
(domain) and the one-retry rule live in the application ring.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.result import Result
from src.dto import ProsePromptDTO


class LlmProsePort(ABC):
    @abstractmethod
    def compose(self, prompt: ProsePromptDTO) -> Result[str]:
        """Prose for ``prompt``; an unavailable writer is ``Failure("LLM_UNAVAILABLE")``."""
