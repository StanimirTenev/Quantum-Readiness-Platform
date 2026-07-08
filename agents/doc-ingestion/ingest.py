"""Document ingestion CLI: extract text from vendor PDFs / runbooks / docs
and chunk it into a JSON index that retrieval-service can search.

No embeddings, no vector store -- deterministic text extraction + paragraph
chunking, consistent with the platform's local-first, no-mandatory-external
-dependency boundary. retrieval-service does keyword search over the
resulting chunks (see services/retrieval-service/app/document_index.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}
MAX_CHUNK_CHARS = 1500


def extract_text_pages(path: Path) -> list[str]:
    """Return a list of page/section texts for one document (one entry for
    .md/.txt files, one entry per page for .pdf)."""
    suffix = path.suffix.lower()
    if suffix in (".md", ".txt"):
        return [path.read_text(encoding="utf-8", errors="ignore")]
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [(page.extract_text() or "") for page in reader.pages]
    raise ValueError(f"unsupported extension: {suffix}")


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text into chunks bounded by max_chars, breaking on paragraph
    boundaries (blank lines) where possible so chunks stay coherent."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def ingest_document(path: Path, doc_id: str) -> dict[str, Any]:
    pages = extract_text_pages(path)
    chunks: list[dict[str, Any]] = []
    for page_index, page_text in enumerate(pages):
        for piece in chunk_text(page_text):
            chunks.append({
                "chunk_index": len(chunks),
                "page": page_index + 1 if path.suffix.lower() == ".pdf" else None,
                "text": piece,
                "char_count": len(piece),
            })
    return {
        "doc_id": doc_id,
        "source_path": str(path),
        "format": path.suffix.lower().lstrip("."),
        "chunk_count": len(chunks),
        "chunks": chunks,
    }


def ingest_directory(docs_dir: Path) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for file_path in sorted(docs_dir.rglob("*")):
        if not file_path.is_file() or file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        rel_path = file_path.relative_to(docs_dir).as_posix()
        try:
            documents.append(ingest_document(file_path, doc_id=rel_path))
        except Exception as exc:  # noqa: BLE001 - best-effort ingest, one bad file shouldn't abort the run
            errors.append({"source_path": rel_path, "error": str(exc)})

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "docs_dir": str(docs_dir),
        "document_count": len(documents),
        "total_chunk_count": sum(d["chunk_count"] for d in documents),
        "documents": documents,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest vendor docs/runbooks into a searchable JSON index.")
    parser.add_argument("--docs-dir", required=True, help="Directory to scan for .md/.txt/.pdf files.")
    parser.add_argument("--out", help="Write the JSON index to this file instead of stdout.")
    args = parser.parse_args(argv)

    docs_dir = Path(args.docs_dir).resolve()
    if not docs_dir.is_dir():
        print(f"error: docs dir not found: {docs_dir}", file=sys.stderr)
        return 1

    index = ingest_directory(docs_dir)
    output_text = json.dumps(index, indent=2)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_text + "\n", encoding="utf-8")
    else:
        print(output_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
