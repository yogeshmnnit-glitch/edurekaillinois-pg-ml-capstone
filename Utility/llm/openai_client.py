"""Thin wrapper around the OpenAI SDK for chat completions and embeddings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from openai import OpenAI, OpenAIError

from Utility.config.prompts import ROOT_SYSTEM_PROMPT
from Utility.config.settings import settings


class LLMClientError(Exception):
    """Raised when a call to the OpenAI API fails."""


@dataclass(frozen=True)
class ChatResult:
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    total_tokens: int


class OpenAIClient:
    """Wraps chat completion and embedding calls, surfacing token usage for observability."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.openai_api_key
        if not key:
            raise LLMClientError("OPENAI_API_KEY is not set. Add it to your .env file.")
        self._client = OpenAI(api_key=key)

    def chat(
        self,
        messages: Sequence[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> ChatResult:
        try:
            full_messages = [{"role": "system", "content": ROOT_SYSTEM_PROMPT}] + list(messages)
            response = self._client.chat.completions.create(
                model=model or settings.chat_model,
                messages=full_messages,
                temperature=temperature,
            )
        except OpenAIError as exc:
            raise LLMClientError(f"Chat completion failed: {exc}") from exc

        usage = response.usage
        return ChatResult(
            content=response.choices[0].message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
        )

    def embed(self, texts: Sequence[str], model: str | None = None) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(vectors=[], total_tokens=0)
        try:
            response = self._client.embeddings.create(
                model=model or settings.embed_model,
                input=list(texts),
            )
        except OpenAIError as exc:
            raise LLMClientError(f"Embedding request failed: {exc}") from exc

        vectors = [item.embedding for item in response.data]
        total_tokens = response.usage.total_tokens if response.usage else 0
        return EmbeddingResult(vectors=vectors, total_tokens=total_tokens)
