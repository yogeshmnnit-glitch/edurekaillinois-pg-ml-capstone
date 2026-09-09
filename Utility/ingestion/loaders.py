"""Format-specific document loaders that normalize files into text segments with metadata."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from docx import Document as DocxDocument
from docx.opc.exceptions import PackageNotFoundError
from pypdf import PdfReader


class UnsupportedFileTypeError(Exception):
    """Raised when a file extension has no registered loader."""


class DocumentLoadError(Exception):
    """Raised when a file matches a registered loader but fails to parse."""


@dataclass(frozen=True)
class LoadedSegment:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def load_document(file_path: Path | str, source_name: str | None = None) -> list[LoadedSegment]:
    """Load a document into text segments (e.g. one per page/sheet), based on its extension."""
    path = Path(file_path)
    name = source_name or path.name
    ext = path.suffix.lower().lstrip(".")

    loader = _LOADERS.get(ext)
    if loader is None:
        raise UnsupportedFileTypeError(f"No loader registered for '.{ext}' files")
    return loader(path, name)


def _load_txt(path: Path, name: str) -> list[LoadedSegment]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [LoadedSegment(text=text, metadata={"source": name, "segment_type": "text"})]


def _load_pdf(path: Path, name: str) -> list[LoadedSegment]:
    reader = PdfReader(str(path))
    segments = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            segments.append(
                LoadedSegment(text=text, metadata={"source": name, "segment_type": "page", "page": page_number})
            )
    return segments


def _load_docx(path: Path, name: str) -> list[LoadedSegment]:
    try:
        doc = DocxDocument(str(path))
    except PackageNotFoundError as exc:
        # python-docx only reads the modern zip-based .docx format, not legacy binary .doc
        raise DocumentLoadError(
            f"'{name}' could not be read as a Word document. Legacy binary .doc files are not "
            "supported - please re-save it as .docx and re-upload."
        ) from exc

    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [LoadedSegment(text=text, metadata={"source": name, "segment_type": "document"})]


def _load_csv(path: Path, name: str) -> list[LoadedSegment]:
    df = pd.read_csv(path)
    text = df.to_csv(index=False)
    return [LoadedSegment(text=text, metadata={"source": name, "segment_type": "table", "rows": len(df)})]


def _load_excel(path: Path, name: str) -> list[LoadedSegment]:
    sheets = pd.read_excel(path, sheet_name=None)
    segments = []
    for sheet_name, df in sheets.items():
        text = df.to_csv(index=False)
        segments.append(
            LoadedSegment(
                text=text,
                metadata={"source": name, "segment_type": "sheet", "sheet": sheet_name, "rows": len(df)},
            )
        )
    return segments


_LOADERS: dict[str, Callable[[Path, str], list[LoadedSegment]]] = {
    "txt": _load_txt,
    "pdf": _load_pdf,
    "docx": _load_docx,
    "doc": _load_docx,
    "csv": _load_csv,
    "xlsx": _load_excel,
    "xls": _load_excel,
}
