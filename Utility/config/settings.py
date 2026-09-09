"""Centralized configuration loaded from the project .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Utility/config/settings.py -> Utility/config -> Utility -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _get_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes")


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _get_extensions(name: str, default: str) -> frozenset[str]:
    raw = os.getenv(name, default)
    return frozenset(ext.strip().lower().lstrip(".") for ext in raw.split(",") if ext.strip())


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT

    # OpenAI
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    chat_model: str = field(default_factory=lambda: os.getenv("CHAT_MODEL", "gpt-4o-mini"))
    embed_model: str = field(default_factory=lambda: os.getenv("EMBED_MODEL", "text-embedding-3-small"))

    # Vector store
    chroma_persist_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / os.getenv("CHROMA_PERSIST_DIR", "ChromaKnowledgeBaseDB")
    )

    # Retrieval / RAG
    top_k: int = field(default_factory=lambda: _get_int("TOP_K", 4))
    confidence_threshold: float = field(default_factory=lambda: _get_float("CONFIDENCE_THRESHOLD", 0.7))

    # Chunking
    chunk_size_tokens: int = field(default_factory=lambda: _get_int("CHUNK_SIZE_TOKENS", 800))
    chunk_overlap_tokens: int = field(default_factory=lambda: _get_int("CHUNK_OVERLAP_TOKENS", 100))

    # Uploads
    max_upload_mb: int = field(default_factory=lambda: _get_int("MAX_UPLOAD_MB", 20))
    allowed_extensions: frozenset[str] = field(
        default_factory=lambda: _get_extensions("ALLOWED_EXTENSIONS", "pdf,txt,csv,xlsx,xls,docx,doc")
    )

    # Chat history / retention
    sqlite_db_path: Path = field(
        default_factory=lambda: PROJECT_ROOT / os.getenv("SQLITE_DB_PATH", "Utility/storage/app_data.db")
    )
    default_retention_days: int = field(default_factory=lambda: _get_int("DEFAULT_RETENTION_DAYS", 30))

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
