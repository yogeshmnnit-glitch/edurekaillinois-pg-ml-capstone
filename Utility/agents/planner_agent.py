"""Planner agent - classifies the active query's telecom domain to tag/route the workflow."""
from __future__ import annotations

import time

from Utility.config.prompts import PLANNER_SYSTEM_PROMPT
from Utility.graph.state import GraphState, NodeMetric
from Utility.llm.openai_client import LLMClientError, OpenAIClient

_VALID_DOMAINS = {"3G", "4G", "5G", "6G", "AI_TELECOM", "OTHER"}


def planner_node(state: GraphState, client: OpenAIClient | None = None) -> dict:
    """Classify state['query'] into a telecom domain label (3G/4G/5G/6G/AI_TELECOM/OTHER)."""
    query = state.get("query", "").strip()
    if not query:
        return {"status": "error", "error": "Planner received an empty query."}

    start = time.perf_counter()
    try:
        llm = client or OpenAIClient()
        result = llm.chat(
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0,
        )
    except LLMClientError as exc:
        return {"status": "error", "error": str(exc)}
    latency_ms = (time.perf_counter() - start) * 1000

    label = result.content.strip().upper()
    domain = label if label in _VALID_DOMAINS else "OTHER"

    metric: NodeMetric = {
        "node": "planner",
        "latency_ms": latency_ms,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,
    }
    return {"classified_domain": domain, "metrics": [*state.get("metrics", []), metric]}
