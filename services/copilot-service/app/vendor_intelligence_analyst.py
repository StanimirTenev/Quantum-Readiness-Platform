"""Vendor Intelligence Analyst: the third deterministic Copilot subagent.
Reads indexed vendor documents (from agents/doc-ingestion, via
retrieval-service's document index) and extracts PQC readiness claims with
a confidence/uncertainty classification -- roadmap language ("we plan to
support...") is flagged uncertain rather than treated as an achieved fact.
No LLM call, no writes -- pattern-based extraction over already-ingested
document text, same safety boundary as Risk Narrator / Discovery Analyst.

`claimed_readiness` reuses pqc-readiness-service's own state taxonomy
(classical_only / hybrid_capable / pqc_ready / vendor_blocked / unknown) so
a vendor's self-reported state is directly comparable to QRP's own
deterministic classification of what's actually observed in evidence.
"""

from __future__ import annotations

import re
from typing import Any

PQC_TERMS = [
    "post-quantum", "postquantum", "pqc", "quantum-safe", "quantum-resistant",
    "ml-kem", "ml-dsa", "slh-dsa", "kyber", "dilithium", "falcon",
]

CERTAINTY_PHRASES = [
    "now supports", "currently supports", "already supports", "generally available",
    "certified", "shipped", "available today", "supports today",
]

UNCERTAIN_PHRASES = [
    "plan to", "planned", "roadmap", "expected", "targeting", "will support",
    "intends to", "future release", "upcoming", "aims to",
]
_QUARTER_YEAR_PATTERN = re.compile(r"\bq[1-4]\s+20\d{2}\b", re.IGNORECASE)

BLOCKER_PHRASES = [
    "not yet", "no support", "does not support", "doesn't support", "unsupported",
    "no plans to", "unavailable", "not available", "blocked", "pending", "discontinued",
]


def _contains_any(lowered_text: str, phrases: list[str]) -> bool:
    return any(phrase in lowered_text for phrase in phrases)


def _classify_claim(text: str) -> dict[str, Any] | None:
    lowered = text.lower()
    if not _contains_any(lowered, PQC_TERMS):
        return None  # not a PQC readiness claim at all

    is_blocker = _contains_any(lowered, BLOCKER_PHRASES)
    is_hybrid = "hybrid" in lowered
    is_certain = _contains_any(lowered, CERTAINTY_PHRASES)
    is_uncertain = _contains_any(lowered, UNCERTAIN_PHRASES) or bool(_QUARTER_YEAR_PATTERN.search(lowered))

    if is_blocker:
        claimed_readiness = "vendor_blocked"
    elif is_hybrid:
        claimed_readiness = "hybrid_capable"
    else:
        claimed_readiness = "pqc_ready"

    if is_certain and not is_uncertain:
        confidence = "certain"
    elif is_uncertain:
        confidence = "uncertain"
    else:
        confidence = "unknown"

    return {
        "claimed_readiness": claimed_readiness,
        "confidence": confidence,
        "is_migration_blocker": is_blocker,
    }


def _product_hint(doc_id: str | None) -> str:
    """Best-effort human label for the document's subject, derived from its
    filename -- not NLP-extracted from the document body. A v1 heuristic:
    the doc, not a parsed product name, is the unit of the readiness matrix."""
    if not doc_id:
        return "unknown"
    stem = doc_id.rsplit("/", 1)[-1]
    for ext in (".md", ".txt", ".pdf"):
        if stem.lower().endswith(ext):
            stem = stem[: -len(ext)]
            break
    return stem.replace("-", " ").replace("_", " ").strip().title() or "unknown"


def _extract_claims(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Classifies at paragraph granularity within each chunk, not the whole
    chunk at once -- a chunk can span multiple paragraph-sized claims (a
    "now supports X" statement and a separate "does not support Y" statement
    are common in the same vendor doc section), and classifying the merged
    chunk text as one claim would conflate distinct, sometimes contradictory
    statements into a single confidence/readiness verdict."""
    claims: list[dict[str, Any]] = []
    for doc in documents:
        doc_id = doc.get("doc_id")
        product_hint = _product_hint(doc_id)
        for chunk in doc.get("chunks") or []:
            text = chunk.get("text") or ""
            for paragraph in text.split("\n\n"):
                paragraph = paragraph.strip()
                # Skip short lines (headings, list bullets) -- a real claim
                # reads as a sentence, not a title.
                if len(paragraph) < 40 or paragraph.startswith("#"):
                    continue
                classification = _classify_claim(paragraph)
                if classification is None:
                    continue
                claims.append({
                    "doc_id": doc_id,
                    "product_hint": product_hint,
                    "chunk_index": chunk.get("chunk_index"),
                    "excerpt": paragraph[:300],
                    **classification,
                })
    return claims


_READINESS_RANK = {"vendor_blocked": 0, "unknown": 1, "hybrid_capable": 2, "pqc_ready": 3}


def _build_readiness_matrix(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_doc: dict[str, list[dict[str, Any]]] = {}
    for claim in claims:
        by_doc.setdefault(claim["doc_id"], []).append(claim)

    matrix: list[dict[str, Any]] = []
    for doc_id, doc_claims in by_doc.items():
        # A blocker note always takes precedence over an "available" claim in
        # the same document, since both being true is itself worth flagging as
        # inconsistent vendor messaging. Confidence must then describe the
        # blocker claim itself, not an unrelated positive claim elsewhere in
        # the doc -- otherwise "vendor_blocked (certain)" could be reporting
        # the certainty of a completely different, non-blocking statement.
        blocker_claims = [c for c in doc_claims if c["is_migration_blocker"]]
        if blocker_claims:
            certain_blockers = [c for c in blocker_claims if c["confidence"] == "certain"]
            best = (certain_blockers or blocker_claims)[0]
            claimed_readiness = "vendor_blocked"
            confidence = best["confidence"]
        else:
            certain_claims = [c for c in doc_claims if c["confidence"] == "certain"]
            pool = certain_claims or doc_claims
            best = max(pool, key=lambda c: _READINESS_RANK.get(c["claimed_readiness"], 1))
            claimed_readiness = best["claimed_readiness"]
            confidence = best["confidence"]

        matrix.append({
            "doc_id": doc_id,
            "product_hint": doc_claims[0]["product_hint"],
            "claimed_readiness": claimed_readiness,
            "confidence": confidence,
            "has_migration_blocker": bool(blocker_claims),
            "claim_count": len(doc_claims),
        })
    return matrix


def build_vendor_intelligence_summary(documents: list[dict[str, Any]]) -> dict[str, Any]:
    claims = _extract_claims(documents)
    matrix = _build_readiness_matrix(claims)

    uncertain_count = sum(1 for c in claims if c["confidence"] != "certain")
    blocker_count = sum(1 for c in claims if c["is_migration_blocker"])
    doc_count = len({c["doc_id"] for c in claims})

    narrative_parts = [
        f"Extracted {len(claims)} PQC readiness claim(s) from {doc_count} document(s)."
    ]
    if claims:
        narrative_parts.append(
            f"{uncertain_count} claim(s) use uncertain/roadmap language and should not be treated as achieved fact."
        )
        if blocker_count:
            narrative_parts.append(f"{blocker_count} migration blocker note(s) were found.")
        else:
            narrative_parts.append("No migration blocker notes were found.")
    else:
        narrative_parts.append("No PQC-relevant claims were found in the indexed documents.")

    return {
        "narrative": " ".join(narrative_parts),
        "claims": claims,
        "readiness_matrix": matrix,
    }
