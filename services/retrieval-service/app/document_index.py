"""Loads the JSON document index produced by agents/doc-ingestion/ingest.py
and provides BM25-ranked search over its chunks with citations. Mirrors
graph-service's GRAPH_SNAPSHOT_PATH pattern: local files only, missing index
is not an error (documents are an optional, best-effort search source)."""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DOC_INDEX = REPO_ROOT / "reports" / "doc-index" / "latest" / "doc-index.json"

_BM25_K1 = 1.5
_BM25_B = 0.75

_TOKEN_PATTERN = re.compile(r"[a-z0-9+]+")

# Domain-specific synonym groups: terms in the same group are treated as
# interchangeable for search purposes, so a document written with one term
# still matches a query written with another (e.g. "PQC" <-> "post-quantum").
# This is what actually closes the documented search gap -- BM25 alone still
# requires literal token overlap, same as substring matching did.
SYNONYM_GROUPS: list[set[str]] = [
    {"pqc", "post quantum", "post-quantum", "postquantum"},
    {"quantum safe", "quantum-safe", "quantum resistant", "quantum-resistant"},
    {"quantum vulnerable", "quantum-vulnerable", "classical vulnerable", "classically vulnerable"},
    {"ml kem", "ml-kem", "kyber"},
    {"ml dsa", "ml-dsa", "dilithium"},
    {"slh dsa", "slh-dsa", "sphincs", "sphincs+"},
    {"hndl", "harvest now decrypt later", "harvest-now-decrypt-later"},
]


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


def _stem(token: str) -> str:
    """Minimal, deterministic suffix stripping (plurals only) so "certificate"
    matches "certificates" the way substring search used to for free -- exact
    BM25 token matching alone would otherwise regress on this very common case.
    Not a full stemmer (e.g. Porter); good enough for this domain's vocabulary."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokenize(text: str) -> list[str]:
    return [_stem(token) for token in _TOKEN_PATTERN.findall(text.lower())]


_synonym_group_patterns_cache: list[tuple[list[re.Pattern], list[str]]] | None = None


def _synonym_group_patterns() -> list[tuple[list[re.Pattern], list[str]]]:
    """Word-boundary regexes per synonym-group phrase, computed once. Phrase-
    level (not individual-token-level) matching is deliberate: tokenizing each
    phrase and expanding per-token would let short shared words collide across
    unrelated groups (e.g. "ml" appears in both "ml-kem" and "ml-dsa" -- a
    token-level expansion would make a query for one match the other)."""
    global _synonym_group_patterns_cache
    if _synonym_group_patterns_cache is not None:
        return _synonym_group_patterns_cache

    _synonym_group_patterns_cache = [
        ([re.compile(r"\b" + re.escape(phrase) + r"\b") for phrase in group], sorted(group))
        for group in SYNONYM_GROUPS
    ]
    return _synonym_group_patterns_cache


def _expand_query_text(query: str) -> str:
    """Appends every alternative phrasing from a synonym group whenever any
    one of its phrases appears in the query, so tokenizing the expanded text
    captures all equivalent terms (e.g. "PQC" also searches for
    "post-quantum")."""
    q = query.lower()
    extra: list[str] = []
    for patterns, group_phrases in _synonym_group_patterns():
        if any(pattern.search(q) for pattern in patterns):
            extra.extend(group_phrases)
    return f"{q} {' '.join(extra)}" if extra else q


class _ChunkRecord:
    __slots__ = ("doc_id", "source_path", "chunk_index", "page", "text", "tokens")

    def __init__(self, doc_id: Any, source_path: Any, chunk_index: Any, page: Any, text: str) -> None:
        self.doc_id = doc_id
        self.source_path = source_path
        self.chunk_index = chunk_index
        self.page = page
        self.text = text
        self.tokens = _tokenize(text)


def _bm25_rank(query_tokens: set[str], chunks: list[_ChunkRecord]) -> list[tuple[float, _ChunkRecord]]:
    """Okapi BM25 over the given chunks for the given (already synonym-
    expanded) query token set. Ranks by relevance instead of the exact-
    substring, insertion-order behavior this replaced."""
    n = len(chunks)
    if n == 0 or not query_tokens:
        return []

    term_counts = [Counter(chunk.tokens) for chunk in chunks]
    lengths = [len(chunk.tokens) for chunk in chunks]
    avg_len = (sum(lengths) / n) if n else 0.0

    doc_freq: Counter[str] = Counter()
    for counts in term_counts:
        for term in query_tokens:
            if counts.get(term):
                doc_freq[term] += 1

    idf = {
        term: math.log(1 + (n - doc_freq.get(term, 0) + 0.5) / (doc_freq.get(term, 0) + 0.5))
        for term in query_tokens
    }

    scored: list[tuple[float, _ChunkRecord]] = []
    for chunk, counts, length in zip(chunks, term_counts, lengths):
        score = 0.0
        for term in query_tokens:
            f = counts.get(term, 0)
            if f == 0:
                continue
            length_norm = (length / avg_len) if avg_len else 1.0
            denom = f + _BM25_K1 * (1 - _BM25_B + _BM25_B * length_norm)
            score += idf[term] * (f * (_BM25_K1 + 1)) / denom
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def search_documents(query: str, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """BM25-ranked search over document chunks, with a small domain synonym
    table (SYNONYM_GROUPS) so a query and a document using different but
    equivalent terminology still match (e.g. a query for "PQC" matches a
    chunk that only says "post-quantum"). Deterministic, no external ML
    dependency -- keeps this service's zero-external-dependency baseline.
    Returns matches with a citation (source_path, chunk_index, page), the
    matched chunk text, and a relevance score, ranked highest first."""
    query_tokens = set(_tokenize(_expand_query_text(query)))
    if not query_tokens:
        return []

    chunks = [
        _ChunkRecord(
            doc_id=doc.get("doc_id"),
            source_path=doc.get("source_path"),
            chunk_index=chunk.get("chunk_index"),
            page=chunk.get("page"),
            text=chunk.get("text") or "",
        )
        for doc in documents
        for chunk in (doc.get("chunks") or [])
    ]

    return [
        {
            "doc_id": chunk.doc_id,
            "source_path": chunk.source_path,
            "chunk_index": chunk.chunk_index,
            "page": chunk.page,
            "text": chunk.text,
            "score": round(score, 4),
        }
        for score, chunk in _bm25_rank(query_tokens, chunks)
    ]
