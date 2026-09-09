"""Ingestion agent - loads, chunks, embeds, and stores newly uploaded files."""
from __future__ import annotations

import time
from pathlib import Path

from Utility.graph.state import GraphState
from Utility.ingestion.chunking import chunk_segments
from Utility.ingestion.loaders import DocumentLoadError, UnsupportedFileTypeError, load_document
from Utility.llm.openai_client import LLMClientError, OpenAIClient
from Utility.vectorstore.chroma_store import ChromaStore


def ingestion_node(
    state: GraphState,
    client: OpenAIClient | None = None,
    store: ChromaStore | None = None,
) -> dict:
    """Ingest every file path listed in state['new_files'] into the vector store."""
    files = state.get("new_files", [])
    if not files:
        return {}

    try:
        llm = client or OpenAIClient()
        vector_store = store or ChromaStore(session_id=state.get("session_id"))
    except LLMClientError as exc:
        return {"status": "error", "error": str(exc)}

    metrics = list(state.get("metrics", []))
    errors: list[str] = []

    for file_path in files:
        path = Path(file_path)
        start = time.perf_counter()
        try:
            segments = load_document(path)
            chunks = chunk_segments(segments)
            if not chunks:
                continue
            embeddings = llm.embed([c.text for c in chunks])
            vector_store.add_chunks(path.name, chunks, embeddings.vectors)
        except (UnsupportedFileTypeError, DocumentLoadError, LLMClientError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue

        latency_ms = (time.perf_counter() - start) * 1000
        metrics.append(
            {
                "node": "ingestion",
                "latency_ms": latency_ms,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": embeddings.total_tokens,
            }
        )

    update: dict = {"new_files": [], "metrics": metrics}
    if errors:
        update["error"] = "; ".join(errors)
    return update
