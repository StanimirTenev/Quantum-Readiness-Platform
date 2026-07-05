from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="PQC Readiness Engine", version="0.1.0")

CONTRACT_VERSION = "pqr-v1"

# ---------------------------------------------------------------------------
# Readiness states (architecture section 6.2).
# ---------------------------------------------------------------------------
# The engine sits between crypto-fingerprint-service (which *identifies* which
# algorithms are present) and risk-engine (which *evaluates* risk). It performs
# a deterministic transitional classification of an asset/service into where it
# sits in the migration, not a risk score.

Readiness = Literal[
    "classical_only",
    "hybrid_capable",
    "pqc_ready",
    "vendor_blocked",
    "unknown",
]

READINESS_STATES: list[dict[str, str]] = [
    {"state": "classical_only",
     "description": "Uses only classical quantum-vulnerable algorithms; no PQC in the current configuration."},
    {"state": "hybrid_capable",
     "description": "Can operate in hybrid mode (classical + PQC in parallel); a transitional state."},
    {"state": "pqc_ready",
     "description": "Configured for post-quantum algorithms."},
    {"state": "vendor_blocked",
     "description": "Migration is blocked because a vendor does not ship a PQC-capable version."},
    {"state": "unknown",
     "description": "Insufficient public-key evidence to classify."},
]


class ReadinessRequest(BaseModel):
    asset_name: str = Field(..., min_length=1)
    # crypto-fingerprint findings (each carries a `classification`, and optionally
    # harvest_now_decrypt_later / weak_key flags). Accepted as loose dicts so the
    # engine stays decoupled from the fingerprint model version.
    findings: list[dict[str, Any]] = Field(default_factory=list)
    vendor_blocked: bool = False
    # Whether the stack is known to support hybrid (classical + PQC) operation
    # even if it currently negotiates classical only.
    hybrid_supported: bool = False


class ReadinessResponse(BaseModel):
    contract_version: str
    asset_name: str
    readiness: Readiness
    confidence: str
    signals: dict[str, bool | int]
    reasons: list[str]


def _flag_any(findings: list[dict[str, Any]], key: str) -> bool:
    return any(bool(f.get(key)) for f in findings if isinstance(f, dict))


def classify_readiness(request: ReadinessRequest) -> ReadinessResponse:
    findings = [f for f in request.findings if isinstance(f, dict)]
    classifications = [f.get("classification") for f in findings]

    has_classical = "classical_vulnerable" in classifications
    has_pqc = "pqc_ready" in classifications
    has_relevant = has_classical or has_pqc

    reasons: list[str] = []

    if request.vendor_blocked:
        readiness: Readiness = "vendor_blocked"
        confidence = "high"
        reasons.append("Migration is blocked by a vendor dependency.")
    elif not has_relevant:
        readiness = "unknown"
        confidence = "low"
        reasons.append("No public-key algorithm evidence available to classify migration state.")
    elif has_pqc and has_classical:
        readiness = "hybrid_capable"
        confidence = "medium"
        reasons.append("Both classical and post-quantum algorithms are present (actively hybrid).")
    elif has_pqc:
        readiness = "pqc_ready"
        confidence = "high"
        reasons.append("Only post-quantum algorithms are present.")
    else:  # only classical vulnerable
        if request.hybrid_supported:
            readiness = "hybrid_capable"
            confidence = "medium"
            reasons.append("Classical only today, but the stack is hybrid-capable.")
        else:
            readiness = "classical_only"
            confidence = "high"
            reasons.append("Only classical quantum-vulnerable algorithms are present.")

    hndl = _flag_any(findings, "harvest_now_decrypt_later")
    weak_key = _flag_any(findings, "weak_key")
    if hndl:
        reasons.append("Recorded traffic is exposed to harvest-now-decrypt-later.")
    if weak_key:
        reasons.append("A weak key was detected.")

    signals: dict[str, bool | int] = {
        "classical_vulnerable_present": has_classical,
        "pqc_present": has_pqc,
        "vendor_blocked": request.vendor_blocked,
        "hybrid_supported": request.hybrid_supported,
        "hndl_exposure": hndl,
        "weak_key_present": weak_key,
        "finding_count": len(findings),
    }

    return ReadinessResponse(
        contract_version=CONTRACT_VERSION,
        asset_name=request.asset_name,
        readiness=readiness,
        confidence=confidence,
        signals=signals,
        reasons=reasons,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pqc-readiness-service"}


@app.get("/readiness-states")
def readiness_states() -> dict[str, list[dict[str, str]]]:
    return {"states": READINESS_STATES}


@app.post("/classify", response_model=ReadinessResponse)
def classify(request: ReadinessRequest) -> ReadinessResponse:
    return classify_readiness(request)
