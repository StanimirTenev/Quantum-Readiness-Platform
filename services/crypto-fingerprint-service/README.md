# Crypto Fingerprint Service

## What this service does
- Deterministically classifies cryptographic algorithms for quantum vulnerability.
- Distinguishes classical public-key algorithms broken by Shor's algorithm
  (RSA, DSA, DH, ECDSA, ECDH, Ed25519, X25519) from post-quantum algorithms
  (ML-KEM/Kyber, ML-DSA/Dilithium, SLH-DSA/SPHINCS+, Falcon).
- Flags harvest-now-decrypt-later (HNDL) exposure only for confidentiality
  primitives (key exchange / key transport), not for signatures.
- Flags weak keys (RSA < 2048) and deprecated primitives (SHA-1, MD5, RC4, DES/3DES).

## Current role in the prototype
- Working prototype. Turns raw crypto evidence into explainable findings that
  the risk-engine and planner can consume. No LLM, no external dependency,
  fully deterministic and local-first.

## Main endpoints
- `GET /health` — service health.
- `GET /algorithms` — the deterministic algorithm knowledge base.
- `POST /fingerprint` — classify evidence into findings + a summary.

## Inputs / outputs

`POST /fingerprint` accepts any combination of:
- `asset_name` (required)
- `algorithms` — explicit list of algorithm strings to classify
- `tls_metadata` — network-scanner evidence (`certificate.algorithms.signature`,
  `certificate.algorithms.public_key`, `certificate.key.size_bits`, `cipher_suite`);
  the older flat form (`signature_algorithm`, `public_key_algorithm`,
  `public_key_size`) is also accepted
- `crypto_evidence` — host-agent evidence (`package_metadata.packages[]`)

It returns a list of `findings` and a `summary`:

```json
{
  "contract_version": "cfp-v1",
  "asset_name": "api.example.internal:443",
  "findings": [
    {
      "source": "tls_certificate",
      "location": "tls_metadata.certificate.public_key",
      "raw_value": "RSA",
      "algorithm_family": "RSA",
      "classification": "classical_vulnerable",
      "quantum_vulnerable": true,
      "harvest_now_decrypt_later": true,
      "weak_key": false,
      "severity": "high",
      "reason": "RSA is broken by a large-scale quantum computer (Shor's algorithm). Recorded traffic is exposed to harvest-now-decrypt-later."
    }
  ],
  "summary": {
    "total_findings": 1,
    "quantum_vulnerable_count": 1,
    "pqc_ready_count": 0,
    "weak_count": 0,
    "hndl_exposure": true,
    "highest_severity": "high",
    "pqc_readiness": "classical_only"
  }
}
```

### Classification values
- `classical_vulnerable` — public-key algorithm broken by Shor (core QRP concern).
- `pqc_ready` — post-quantum algorithm.
- `symmetric_reduced` — symmetric cipher; only weakened by Grover, not broken.
- `hash` — hash primitive of acceptable strength.
- `deprecated_weak` — broken/deprecated primitive regardless of quantum risk.
- `unknown` — could not be classified; manual review recommended.

### `pqc_readiness` summary
- `classical_only`, `hybrid_partial`, `pqc_ready`,
  `no_quantum_vulnerable_detected`, or `unknown`.

## Run locally

```bash
cd services/crypto-fingerprint-service
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --port 8003
```

## Tests

```bash
cd services/crypto-fingerprint-service
PYTHONPATH=. pytest -q
```

## Known limitations
- Classification is string/token based on observed algorithm identifiers; it
  does not parse raw certificate DER or private key material.
- Host packages are reported as informational crypto-surface findings only.
- Not wired into the API gateway routing yet.
