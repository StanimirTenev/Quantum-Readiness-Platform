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
- `GET /documents` — the full loaded document index (not search-filtered); used by consumers
  that need to walk every ingested document, e.g. the Discovery Analyst Copilot subagent.
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
- Matching is BM25-ranked (Okapi BM25 over chunk tokens, no external ML
  dependency) with a small domain synonym table (`SYNONYM_GROUPS` in
  `app/document_index.py`) -- e.g. a query for "PQC" also matches a chunk
  that only says "post-quantum", "HNDL" also matches "harvest now decrypt
  later", "kyber" also matches "ML-KEM". Matches are ranked by relevance
  score (returned as `score`), not insertion order. A light suffix-stripping
  stemmer (plurals only) keeps "certificate" matching "certificates", which
  exact-substring search used to do for free.

## Current status
- Working prototype service. Document search verified live against a real
  ingested PDF, both directly and through `copilot-service`'s `/query`.

## How to run tests
- `pytest services/retrieval-service/tests`

## Known limitations
- Structured search (assets/scans/risks/tasks) is in-memory and rule-based;
  no dedicated indexing backend is used.
- BM25 + a curated synonym table is not true embedding-based semantic search
  -- it still requires token overlap (direct or via a known synonym group),
  so a paraphrase using neither a literal term nor a listed synonym won't
  surface. Chosen deliberately over a local embedding model
  (`sentence-transformers`/`torch`) to keep this service's zero-external-ML-
  dependency baseline; a real embedding-based upgrade remains a future option
  if the synonym-table approach proves insufficient.
- Compound technical terms tokenize on word boundaries, not as atomic units
  (e.g. "ML-KEM" and "ML-DSA" both contain the token "ml"), so an unrelated
  query can weakly partial-match a document via a shared generic sub-term --
  BM25's scoring ranks such partial matches well below true matches, but
  doesn't eliminate them outright.
