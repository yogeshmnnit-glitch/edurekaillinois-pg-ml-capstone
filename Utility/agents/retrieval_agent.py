"""Retrieval agent - embeds the active query and returns the most similar stored chunks."""
from __future__ import annotations

import time

from Utility.graph.state import GraphState, NodeMetric
from Utility.llm.openai_client import LLMClientError, OpenAIClient
from Utility.vectorstore.chroma_store import ChromaStore


def retrieval_node(
    state: GraphState,
    client: OpenAIClient | None = None,
    store: ChromaStore | None = None,
) -> dict:
    """Similarity-search the vector store for chunks relevant to the active query."""
    query = (state.get("pending_query") or state.get("query", "")).strip()
    if not query:
        return {"status": "error", "error": "Retrieval received an empty query."}

    start = time.perf_counter()
    try:
        llm = client or OpenAIClient()
        vector_store = store or ChromaStore(session_id=state.get("session_id"))
        embedding = llm.embed([query])
        results = vector_store.similarity_search(embedding.vectors[0])
        results = [r for r in results if not r.metadata.get("is_suspicious", False)]
    except LLMClientError as exc:
        return {"status": "error", "error": str(exc)}
    latency_ms = (time.perf_counter() - start) * 1000

    retrieved = [{"text": r.text, "metadata": r.metadata, "similarity": r.similarity} for r in results]
    metric: NodeMetric = {
        "node": "retrieval",
        "latency_ms": latency_ms,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": embedding.total_tokens,
    }
    return {
        "retrieved_chunks": retrieved,
        "metrics": [*state.get("metrics", []), metric],
    }
