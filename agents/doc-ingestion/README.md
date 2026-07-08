# Doc Ingestion

## What this service does
- Extracts text from vendor PDFs, runbooks, and Markdown/plain-text docs, and
  chunks it into a JSON index that `retrieval-service` can keyword-search.
- No embeddings, no vector store, no LLM call — deterministic text
  extraction + paragraph chunking, consistent with the platform's
  local-first, no-mandatory-external-dependency boundary.

## Current role in the prototype
- Working prototype agent. First half of the Document Ingestion → Retrieval
  → Copilot chain (see `services/retrieval-service` for the search side and
  `services/copilot-service`'s Risk Narrator for the first Copilot subagent
  consumer).

## Main endpoints or functions
- CLI entrypoint: `ingest.py`
- Core functions: `ingest_directory`, `ingest_document`, `chunk_text`,
  `extract_text_pages`

## Inputs / outputs
- Input: CLI flags (`--docs-dir`, optional `--out`).
- Output: JSON document index (stdout or `--out` file):
  ```json
  {
    "generated_at": "2026-07-08T12:00:00Z",
    "docs_dir": "/path/to/docs",
    "document_count": 2,
    "total_chunk_count": 40,
    "documents": [
      {
        "doc_id": "vendor-roadmap.pdf",
        "source_path": "/path/to/docs/vendor-roadmap.pdf",
        "format": "pdf",
        "chunk_count": 24,
        "chunks": [
          {"chunk_index": 0, "page": 1, "text": "...", "char_count": 812}
        ]
      }
    ],
    "errors": []
  }
  ```

## Run
```bash
cd agents/doc-ingestion
python3 ingest.py --docs-dir /path/to/vendor-docs --out /tmp/doc-index.json
```

Point `retrieval-service` at the output via `DOC_INDEX_PATH=/tmp/doc-index.json`.

## Current status
- Working prototype. Verified live against real PDF (24-page, Cyrillic text)
  and Markdown documents, and end-to-end through
  `retrieval-service`'s `/search` and `copilot-service`'s `/query`.

## How to run tests
- `cd agents/doc-ingestion && PYTHONPATH=. python3 -m pytest -q`

## Known limitations
- Supported formats: `.md`, `.txt`, `.pdf` only — no `.docx`, HTML, or image/
  OCR support.
- Keyword substring search only (via `retrieval-service`), not semantic/
  vector search — a document mentioning "post-quantum" won't match a query
  for "PQC" unless the literal term appears in the text.
- One malformed file is skipped (recorded in `errors`) rather than aborting
  the whole ingest run; a corrupt PDF, empty file, or garbage bytes will
  appear there instead of failing the CLI.
