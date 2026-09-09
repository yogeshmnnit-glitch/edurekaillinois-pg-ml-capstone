"""Shared state schema passed between LangGraph nodes."""
from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict


class HistoryTurn(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class RetrievedChunkDict(TypedDict):
    text: str
    metadata: dict[str, Any]
    similarity: float


class NodeMetric(TypedDict):
    node: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class GraphState(TypedDict, total=False):
    # Set per invocation to select the entry point (see workflow_graph.py, Phase 4)
    trigger: Literal["new_query", "doc_added_retry", "new_upload_only"]
    session_id: str
    query: str
    pending_query: Optional[str]
    new_files: list[str]
    history: list[HistoryTurn]

    classified_domain: Optional[str]
    retrieved_chunks: list[RetrievedChunkDict]
    answer: Optional[str]
    citations: list[str]
    confidence: Optional[float]
    status: Optional[Literal["answered", "insufficient_evidence", "error"]]
    error: Optional[str]

    metrics: list[NodeMetric]
