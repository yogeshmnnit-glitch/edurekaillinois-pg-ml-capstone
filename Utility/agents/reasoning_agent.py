"""Reasoning/RAG agent - generates a grounded answer from retrieved chunks."""
from __future__ import annotations

import time

from Utility.config.prompts import REASONING_SYSTEM_PROMPT, REASONING_USER_TEMPLATE
from Utility.graph.state import GraphState, NodeMetric
from Utility.llm.openai_client import LLMClientError, OpenAIClient

_HISTORY_TURNS = 6


def _format_history(state: GraphState) -> str:
    turns = state.get("history", [])[-_HISTORY_TURNS:]
    if not turns:
        return "(none)"
    return "\n".join(f"{turn['role']}: {turn['content']}" for turn in turns)


def _format_context(state: GraphState) -> str:
    chunks = state.get("retrieved_chunks", [])
    if not chunks:
        return "(no relevant context retrieved)"
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        source = chunk["metadata"].get("source", "unknown")
        parts.append(f"[{i}] (source: {source})\n{chunk['text']}")
    return "\n\n".join(parts)


def _citations_from_chunks(state: GraphState) -> list[str]:
    sources: list[str] = []
    for chunk in state.get("retrieved_chunks", []):
        source = chunk["metadata"].get("source")
        if source and source not in sources:
            sources.append(source)
    return sources


def reasoning_node(state: GraphState, client: OpenAIClient | None = None) -> dict:
    """Generate a grounded answer for the active query using retrieved context."""
    query = (state.get("pending_query") or state.get("query", "")).strip()
    if not query:
        return {"status": "error", "error": "Reasoning received an empty query."}

    user_prompt = REASONING_USER_TEMPLATE.format(
        history=_format_history(state),
        context=_format_context(state),
        question=query,
    )

    start = time.perf_counter()
    try:
        llm = client or OpenAIClient()
        result = llm.chat(
            messages=[
                {"role": "system", "content": REASONING_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
    except LLMClientError as exc:
        return {"status": "error", "error": str(exc)}
    latency_ms = (time.perf_counter() - start) * 1000

    metric: NodeMetric = {
        "node": "reasoning",
        "latency_ms": latency_ms,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,
    }
    return {
        "answer": result.content,
        "citations": _citations_from_chunks(state),
        "metrics": [*state.get("metrics", []), metric],
    }
