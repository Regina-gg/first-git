from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


class LLMClient(Protocol):
    def complete(self, messages: List[ChatMessage]) -> str:
        ...


class OpenAILLMClient:
    """Lazy OpenAI SDK adapter reserved for model-backed agent upgrades."""

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    def complete(self, messages: List[ChatMessage]) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("OpenAI SDK is not installed. Install it before enabling model-backed agents.") from exc
        client = OpenAI()
        response = client.responses.create(
            model=self.model,
            input=[{"role": item.role, "content": item.content} for item in messages],
        )
        return response.output_text


class RuleBasedLLMClient:
    """Default V1 fallback; keeps local dry-runs deterministic and dependency-free."""

    def complete(self, messages: List[ChatMessage]) -> str:
        return messages[-1].content if messages else ""
