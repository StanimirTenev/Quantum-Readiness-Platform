# Retrieval Service

## What this service does
- Aggregates platform data for overview, asset-level lookup, and keyword search.
- `POST /search` also searches ingested documents (vendor PDFs/runbooks from
  `agents/doc-ingestion`) when a document index is configured, returning
  matched chunks with citations (`doc_id`, `source_path`, `chunk_index`, `page`).

## Current role in the prototype
- Working prototype retrieval layer used by copilot and UI workflows.

## Main endpoints or functions
- `GET /health`, `GET /overview`, `GET /asset`
- `POST /search`

## Inputs / outputs
- Input: optional `asset_name` query parameter and search query JSON (`{ "query": "..." }`).
- Output: JSON overview metrics, asset bundles, and ranked search results
  (`results.documents` carries any matched document chunks).

## Document search
- `DOC_INDEX_PATH` env var points at a JSON index produced by
  `agents/doc-ingestion/ingest.py` (default:
  `reports/doc-index/latest/doc-index.json`, mirroring graph-service's
  `GRAPH_SNAPSHOT_PATH` pattern). Missing/invalid index is not an error —
  document search silently returns no matches, since it's a best-effort
  source alongside assets/scans/risks/tasks.
- Matching is keyword substring search (case-insensitive), not
  semantic/vector search — see `app/document_index.py`.

## Current status
- Working prototype service. Document search verified live against a real
  ingested PDF, both directly and through `copilot-service`'s `/query`.

## How to run tests
- `pytest services/retrieval-service/tests`

## Known limitations
- Structured search (assets/scans/risks/tasks) is in-memory and rule-based;
  no dedicated indexing backend is used.
- Document search is keyword substring matching only — no synonym/semantic
  matching (e.g. "PQC" won't match "post-quantum" unless both literally
  appear).
