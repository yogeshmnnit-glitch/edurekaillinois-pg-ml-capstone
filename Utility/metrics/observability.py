"""Cross-cutting observability: persists per-node metrics and summarizes them for the UI panel."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from Utility.graph.state import GraphState
from Utility.storage.db import ChatStore


@dataclass(frozen=True)
class SimilarityStats:
    count: int
    average: Optional[float]
    minimum: Optional[float]
    maximum: Optional[float]


@dataclass(frozen=True)
class TurnSummary:
    total_tokens: int
    total_latency_ms: float
    per_node: list[dict[str, Any]]
    similarity: SimilarityStats


@dataclass(frozen=True)
class TokenDashboard:
    today_tokens: int
    session_tokens: int


def persist_turn_metrics(store: ChatStore, thread_id: str, state: GraphState) -> None:
    """Write every per-node metric recorded during this graph run into the token_usage_log."""
    for metric in state.get("metrics", []):
        store.log_token_usage(
            thread_id=thread_id,
            node=metric["node"],
            prompt_tokens=metric.get("prompt_tokens", 0),
            completion_tokens=metric.get("completion_tokens", 0),
            total_tokens=metric.get("total_tokens", 0),
            latency_ms=metric.get("latency_ms", 0.0),
        )


def _similarity_stats(state: GraphState) -> SimilarityStats:
    scores = [chunk["similarity"] for chunk in state.get("retrieved_chunks", [])]
    if not scores:
        return SimilarityStats(count=0, average=None, minimum=None, maximum=None)
    return SimilarityStats(
        count=len(scores),
        average=sum(scores) / len(scores),
        minimum=min(scores),
        maximum=max(scores),
    )


def summarize_turn(state: GraphState) -> TurnSummary:
    """Build a human-readable summary of this graph run's metrics for the observability panel."""
    metrics = state.get("metrics", [])
    per_node = [
        {
            "node": m["node"],
            "latency_ms": m.get("latency_ms", 0.0),
            "total_tokens": m.get("total_tokens", 0),
        }
        for m in metrics
    ]
    return TurnSummary(
        total_tokens=sum(m.get("total_tokens", 0) for m in metrics),
        total_latency_ms=sum(m.get("latency_ms", 0.0) for m in metrics),
        per_node=per_node,
        similarity=_similarity_stats(state),
    )


def get_token_dashboard(store: ChatStore, thread_id: str) -> TokenDashboard:
    """Fetch the 'today vs this session' token totals for the active thread."""
    return TokenDashboard(
        today_tokens=store.get_today_tokens(thread_id),
        session_tokens=store.get_lifetime_tokens(thread_id),
    )
