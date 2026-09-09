"""Token-based chunking for embedding, built on tiktoken."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import tiktoken

from Utility.config.settings import settings
from Utility.ingestion.loaders import LoadedSegment
from Utility.security.sanitizer import sanitize_chunk

_ENCODING = tiktoken.get_encoding("cl100k_base")


@dataclass(frozen=True)
class Chunk:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_segments(
    segments: list[LoadedSegment],
    chunk_size_tokens: int | None = None,
    chunk_overlap_tokens: int | None = None,
) -> list[Chunk]:
    """Split loaded segments into token-bounded chunks, preserving source metadata."""
    size = chunk_size_tokens or settings.chunk_size_tokens
    overlap = chunk_overlap_tokens or settings.chunk_overlap_tokens
    if overlap >= size:
        raise ValueError("chunk_overlap_tokens must be smaller than chunk_size_tokens")

    chunks: list[Chunk] = []
    for segment in segments:
        tokens = _ENCODING.encode(segment.text)
        if not tokens:
            continue

        start = 0
        chunk_index = 0
        while start < len(tokens):
            end = min(start + size, len(tokens))
            chunk_text = _ENCODING.decode(tokens[start:end])
            sanitized = sanitize_chunk(chunk_text)
            metadata = {**segment.metadata, "chunk_index": chunk_index, "is_suspicious": sanitized.is_suspicious}
            chunks.append(Chunk(text=sanitized.clean_text, metadata=metadata))
            chunk_index += 1
            if end == len(tokens):
                break
            start = end - overlap

    return chunks
