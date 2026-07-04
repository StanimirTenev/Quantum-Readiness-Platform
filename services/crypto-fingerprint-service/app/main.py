from __future__ import annotations

import re
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Crypto Fingerprint Service", version="0.1.0")

CONTRACT_VERSION = "cfp-v1"

# ---------------------------------------------------------------------------
# Deterministic algorithm knowledge base
# ---------------------------------------------------------------------------
# Classification values:
#   classical_vulnerable  -> public-key algorithm broken by a large quantum
#                            computer (Shor). This is the core QRP concern.
#   pqc_ready             -> post-quantum algorithm (NIST PQC / draft names).
#   symmetric_reduced     -> symmetric cipher; only weakened by Grover, not
#                            broken. Not a migration blocker on its own.
#   hash                  -> hash primitive of acceptable strength.
#   deprecated_weak       -> broken/deprecated primitive regardless of quantum.
#   unknown               -> could not be classified.

Classification = Literal[
    "classical_vulnerable",
    "pqc_ready",
    "symmetric_reduced",
    "hash",
    "deprecated_weak",
    "unknown",
]

Usage = Literal["signature", "public_key", "key_exchange", "cipher", "explicit"]

# Ordered most-specific-first. The first token found in the squashed value wins.
# fields: token, family, classification, kind, hndl_capable
_PUBLIC_KEY_FAMILIES: list[tuple[str, str, str, str, bool]] = [
    # Post-quantum
    ("MLKEM", "ML-KEM", "pqc_ready", "key_exchange", False),
    ("KYBER", "ML-KEM", "pqc_ready", "key_exchange", False),
    ("MLDSA", "ML-DSA", "pqc_ready", "signature", False),
    ("DILITHIUM", "ML-DSA", "pqc_ready", "signature", False),
    ("SLHDSA", "SLH-DSA", "pqc_ready", "signature", False),
    ("SPHINCS", "SLH-DSA", "pqc_ready", "signature", False),
    ("FALCON", "Falcon", "pqc_ready", "signature", False),
    ("FRODO", "FrodoKEM", "pqc_ready", "key_exchange", False),
    # Classical elliptic-curve (specific before generic EC)
    ("ECDSA", "ECDSA", "classical_vulnerable", "signature", False),
    ("EDDSA", "EdDSA", "classical_vulnerable", "signature", False),
    ("ED25519", "Ed25519", "classical_vulnerable", "signature", False),
    ("ED448", "Ed448", "classical_vulnerable", "signature", False),
    ("X25519", "X25519", "classical_vulnerable", "key_exchange", True),
    ("X448", "X448", "classical_vulnerable", "key_exchange", True),
    ("ECDH", "ECDH", "classical_vulnerable", "key_exchange", True),
    ("ECPUBLICKEY", "EC", "classical_vulnerable", "public_key", True),
    # Classical RSA / DSA / DH
    ("RSASSA", "RSA", "classical_vulnerable", "public_key", True),
    ("RSAPSS", "RSA", "classical_vulnerable", "public_key", True),
    ("RSA", "RSA", "classical_vulnerable", "public_key", True),
    ("DSA", "DSA", "classical_vulnerable", "signature", False),
    ("DIFFIEHELLMAN", "DH", "classical_vulnerable", "key_exchange", True),
    ("DHE", "DH", "classical_vulnerable", "key_exchange", True),
    ("DH", "DH", "classical_vulnerable", "key_exchange", True),
    ("EC", "EC", "classical_vulnerable", "public_key", True),
]

# Weak / deprecated tokens that can co-occur (e.g. a weak signature hash).
_WEAK_TOKENS: list[tuple[str, str]] = [
    ("MD5", "MD5 is cryptographically broken"),
    ("SHA1", "SHA-1 is deprecated and collision-prone"),
    ("RC4", "RC4 is insecure"),
    ("TRIPLEDES", "3DES is deprecated"),
    ("3DES", "3DES is deprecated"),
    ("DES", "DES is broken"),
]

_SYMMETRIC_TOKENS: list[tuple[str, str]] = [
    ("CHACHA", "ChaCha20"),
    ("AES", "AES"),
]

_HASH_TOKENS: list[tuple[str, str]] = [
    ("SHA512", "SHA-512"),
    ("SHA384", "SHA-384"),
    ("SHA256", "SHA-256"),
    ("SHA224", "SHA-224"),
    ("SHA3", "SHA-3"),
]

_SEVERITY_RANK: dict[str, int] = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

WEAK_RSA_MIN_BITS = 2048


def _squash(value: str) -> str:
    """Uppercase and strip non-alphanumeric chars for robust token matching."""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _find_public_key_family(squashed: str) -> tuple[str, str, str, str, bool] | None:
    for entry in _PUBLIC_KEY_FAMILIES:
        if entry[0] in squashed:
            return entry
    return None


def _find_weak_token(squashed: str) -> tuple[str, str] | None:
    for token, note in _WEAK_TOKENS:
        if token in squashed:
            return token, note
    return None


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class FingerprintRequest(BaseModel):
    asset_name: str = Field(..., min_length=1)
    algorithms: list[str] | None = None
    tls_metadata: dict[str, Any] | None = None
    crypto_evidence: dict[str, Any] | None = None


class Finding(BaseModel):
    source: str
    location: str
    raw_value: str
    algorithm_family: str
    classification: Classification
    quantum_vulnerable: bool
    harvest_now_decrypt_later: bool
    weak_key: bool
    severity: str
    reason: str


class FingerprintSummary(BaseModel):
    total_findings: int
    quantum_vulnerable_count: int
    pqc_ready_count: int
    weak_count: int
    hndl_exposure: bool
    highest_severity: str
    pqc_readiness: str


class FingerprintResponse(BaseModel):
    contract_version: str
    asset_name: str
    findings: list[Finding]
    summary: FingerprintSummary


# ---------------------------------------------------------------------------
# Core classifier
# ---------------------------------------------------------------------------
def classify_algorithm(
    raw_value: str,
    usage: Usage,
    *,
    source: str,
    location: str,
    key_size: int | None = None,
) -> Finding:
    """Classify a single algorithm string deterministically."""
    squashed = _squash(raw_value or "")
    weak = _find_weak_token(squashed)
    family_entry = _find_public_key_family(squashed)

    if family_entry is not None:
        _token, family, classification, kind, hndl_capable = family_entry

        if classification == "pqc_ready":
            return Finding(
                source=source,
                location=location,
                raw_value=raw_value,
                algorithm_family=family,
                classification="pqc_ready",
                quantum_vulnerable=False,
                harvest_now_decrypt_later=False,
                weak_key=False,
                severity="info",
                reason=f"{family} is a post-quantum algorithm; quantum-resistant.",
            )

        # classical_vulnerable public-key algorithm
        weak_key = bool(
            family == "RSA" and key_size is not None and 0 < key_size < WEAK_RSA_MIN_BITS
        )
        # HNDL only applies to confidentiality primitives (key exchange / key
        # transport). Signatures cannot be harvested-now-decrypted-later.
        if usage == "signature":
            hndl = False
        elif usage in ("public_key", "key_exchange", "explicit"):
            hndl = hndl_capable
        else:
            hndl = False

        severity = "high"
        reasons = [f"{family} is broken by a large-scale quantum computer (Shor's algorithm)."]
        if weak_key:
            severity = "critical"
            reasons.append(f"RSA key size {key_size} is below the {WEAK_RSA_MIN_BITS}-bit minimum.")
        if weak is not None:
            severity = "critical"
            reasons.append(weak[1] + ".")
        if hndl:
            reasons.append("Recorded traffic is exposed to harvest-now-decrypt-later.")

        return Finding(
            source=source,
            location=location,
            raw_value=raw_value,
            algorithm_family=family,
            classification="classical_vulnerable",
            quantum_vulnerable=True,
            harvest_now_decrypt_later=hndl,
            weak_key=weak_key,
            severity=severity,
            reason=" ".join(reasons),
        )

    # No public-key family. Handle weak-only, symmetric, hash, unknown.
    if weak is not None:
        return Finding(
            source=source,
            location=location,
            raw_value=raw_value,
            algorithm_family=weak[0],
            classification="deprecated_weak",
            quantum_vulnerable=False,
            harvest_now_decrypt_later=False,
            weak_key=False,
            severity="high",
            reason=weak[1] + ".",
        )

    for token, label in _SYMMETRIC_TOKENS:
        if token in squashed:
            return Finding(
                source=source,
                location=location,
                raw_value=raw_value,
                algorithm_family=label,
                classification="symmetric_reduced",
                quantum_vulnerable=False,
                harvest_now_decrypt_later=False,
                weak_key=False,
                severity="low",
                reason=f"{label} is symmetric; Grover halves effective strength but does not break it.",
            )

    for token, label in _HASH_TOKENS:
        if token in squashed:
            return Finding(
                source=source,
                location=location,
                raw_value=raw_value,
                algorithm_family=label,
                classification="hash",
                quantum_vulnerable=False,
                harvest_now_decrypt_later=False,
                weak_key=False,
                severity="info",
                reason=f"{label} hash is of acceptable strength.",
            )

    return Finding(
        source=source,
        location=location,
        raw_value=raw_value,
        algorithm_family="unknown",
        classification="unknown",
        quantum_vulnerable=False,
        harvest_now_decrypt_later=False,
        weak_key=False,
        severity="low",
        reason="Algorithm could not be classified; manual review recommended.",
    )


# ---------------------------------------------------------------------------
# Evidence extraction
# ---------------------------------------------------------------------------
def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _certificate_algorithms(certificate: dict[str, Any]) -> tuple[str | None, str | None, int | None]:
    """Return (signature, public_key, key_size) from either the Stage 2 nested
    form or the older flat form."""
    algorithms = certificate.get("algorithms")
    if isinstance(algorithms, dict):
        signature = algorithms.get("signature")
        public_key = algorithms.get("public_key")
    else:
        signature = certificate.get("signature_algorithm")
        public_key = certificate.get("public_key_algorithm")

    key = certificate.get("key")
    if isinstance(key, dict) and key.get("size_bits") is not None:
        key_size = _safe_int(key.get("size_bits"))
    else:
        key_size = _safe_int(certificate.get("public_key_size"))

    sig = signature if isinstance(signature, str) and signature.strip() else None
    pub = public_key if isinstance(public_key, str) and public_key.strip() else None
    return sig, pub, key_size


def extract_findings(request: FingerprintRequest) -> list[Finding]:
    findings: list[Finding] = []

    tls = request.tls_metadata or {}
    certificate = tls.get("certificate")
    if isinstance(certificate, dict):
        signature, public_key, key_size = _certificate_algorithms(certificate)
        if public_key is not None:
            findings.append(
                classify_algorithm(
                    public_key,
                    "public_key",
                    source="tls_certificate",
                    location="tls_metadata.certificate.public_key",
                    key_size=key_size,
                )
            )
        if signature is not None:
            findings.append(
                classify_algorithm(
                    signature,
                    "signature",
                    source="tls_certificate",
                    location="tls_metadata.certificate.signature",
                    key_size=key_size,
                )
            )

    cipher_suite = tls.get("cipher_suite")
    if isinstance(cipher_suite, str) and cipher_suite.strip():
        findings.append(
            classify_algorithm(
                cipher_suite,
                "cipher",
                source="tls_cipher_suite",
                location="tls_metadata.cipher_suite",
            )
        )

    packages = (
        ((request.crypto_evidence or {}).get("package_metadata", {}) or {}).get("packages", [])
    )
    if isinstance(packages, list):
        for index, package in enumerate(packages):
            name = package.get("name") if isinstance(package, dict) else None
            if isinstance(name, str) and name.strip():
                findings.append(
                    Finding(
                        source="host_package",
                        location=f"crypto_evidence.package_metadata.packages[{index}]",
                        raw_value=name,
                        algorithm_family=name,
                        classification="unknown",
                        quantum_vulnerable=False,
                        harvest_now_decrypt_later=False,
                        weak_key=False,
                        severity="info",
                        reason="Crypto-relevant package present; expands cryptographic attack surface.",
                    )
                )

    for index, algorithm in enumerate(request.algorithms or []):
        if isinstance(algorithm, str) and algorithm.strip():
            findings.append(
                classify_algorithm(
                    algorithm,
                    "explicit",
                    source="explicit_algorithm",
                    location=f"algorithms[{index}]",
                )
            )

    return findings


def summarize(findings: list[Finding]) -> FingerprintSummary:
    vulnerable = sum(1 for f in findings if f.quantum_vulnerable)
    pqc = sum(1 for f in findings if f.classification == "pqc_ready")
    weak = sum(1 for f in findings if f.classification == "deprecated_weak" or f.weak_key)
    hndl = any(f.harvest_now_decrypt_later for f in findings)

    highest = "info"
    for finding in findings:
        if _SEVERITY_RANK[finding.severity] > _SEVERITY_RANK[highest]:
            highest = finding.severity

    crypto_findings = [f for f in findings if f.classification != "unknown"]
    if vulnerable and pqc:
        readiness = "hybrid_partial"
    elif vulnerable:
        readiness = "classical_only"
    elif pqc:
        readiness = "pqc_ready"
    elif crypto_findings:
        readiness = "no_quantum_vulnerable_detected"
    else:
        readiness = "unknown"

    return FingerprintSummary(
        total_findings=len(findings),
        quantum_vulnerable_count=vulnerable,
        pqc_ready_count=pqc,
        weak_count=weak,
        hndl_exposure=hndl,
        highest_severity=highest,
        pqc_readiness=readiness,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "crypto-fingerprint-service"}


@app.get("/algorithms")
def algorithms() -> dict[str, list[dict[str, Any]]]:
    """Expose the deterministic algorithm knowledge base."""
    known = [
        {"family": family, "classification": classification, "kind": kind, "hndl_capable": hndl}
        for _token, family, classification, kind, hndl in _PUBLIC_KEY_FAMILIES
    ]
    # De-duplicate by family while preserving order.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for entry in known:
        if entry["family"] not in seen:
            seen.add(entry["family"])
            unique.append(entry)
    return {"algorithms": unique}


@app.post("/fingerprint", response_model=FingerprintResponse)
def fingerprint(request: FingerprintRequest) -> FingerprintResponse:
    findings = extract_findings(request)
    return FingerprintResponse(
        contract_version=CONTRACT_VERSION,
        asset_name=request.asset_name,
        findings=findings,
        summary=summarize(findings),
    )
