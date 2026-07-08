"""Loads the JSON document index produced by agents/doc-ingestion/ingest.py
and provides keyword search over its chunks with citations. Mirrors
graph-service's GRAPH_SNAPSHOT_PATH pattern: local files only, missing index
is not an error (documents are an optional, best-effort search source)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DOC_INDEX = REPO_ROOT / "reports" / "doc-index" / "latest" / "doc-index.json"


def load_document_index() -> dict[str, Any]:
    """Returns {"documents": [...]}; empty if no index is configured/found."""
    raw_path = os.getenv("DOC_INDEX_PATH")
    if raw_path and raw_path.lower().startswith(("http://", "https://")):
        return {"documents": []}

    path = Path(raw_path) if raw_path else DEFAULT_DOC_INDEX
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        return {"documents": []}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"documents": []}

    return {"documents": data.get("documents") or []}


def search_documents(query: str, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keyword substring search over document chunks. Returns matches with a
    citation (source_path, chunk_index, page) and the matched chunk text."""
    q = query.strip().lower()
    if not q:
        return []

    matches: list[dict[str, Any]] = []
    for doc in documents:
        for chunk in doc.get("chunks") or []:
            if q in (chunk.get("text") or "").lower():
                matches.append({
                    "doc_id": doc.get("doc_id"),
                    "source_path": doc.get("source_path"),
                    "chunk_index": chunk.get("chunk_index"),
                    "page": chunk.get("page"),
                    "text": chunk.get("text"),
                })
    return matches
