"""Wrapper around a persistent ChromaDB collection for the knowledge base."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import chromadb

from Utility.config.settings import settings
from Utility.ingestion.chunking import Chunk

_COLLECTION_NAME = "enterprise_knowledge_base"


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    metadata: dict[str, Any]
    similarity: float


class ChromaStore:
    """Adds embedded chunks to and runs similarity search against the persistent Chroma collection."""

    def __init__(self, persist_dir: str | None = None, session_id: str | None = None) -> None:
        path = str(persist_dir or settings.chroma_persist_dir)
        self._client = chromadb.PersistentClient(path=path)
        collection_name = "enterprise_knowledge_base"
        if session_id:
            collection_name = f"enterprise_knowledge_base_{session_id}"
        self._collection = self._client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, source_name: str, chunks: list[Chunk], embeddings: list[list[float]]) -> list[str]:
        if not chunks:
            return []
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must be the same length")

        ids = [f"{source_name}::{uuid4().hex}" for _ in chunks]
        self._collection.add(
            ids=ids,
            documents=[c.text for c in chunks],
            embeddings=embeddings,
            metadatas=[c.metadata for c in chunks],
        )
        return ids

    def similarity_search(self, query_embedding: list[float], k: int | None = None) -> list[RetrievedChunk]:
        top_k = k or settings.top_k
        results = self._collection.query(query_embeddings=[query_embedding], n_results=top_k)

        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]

        return [
            # Chroma's default cosine distance is in [0, 2]; convert to a similarity score
            RetrievedChunk(text=text, metadata=metadata or {}, similarity=1.0 - distance)
            for text, metadata, distance in zip(documents, metadatas, distances)
        ]

    def count(self) -> int:
        return self._collection.count()

    def has_source(self, source_name: str) -> bool:
        """Return whether at least one stored chunk belongs to the source file."""
        result = self._collection.get(where={"source": source_name}, limit=1)
        return bool(result.get("ids"))
