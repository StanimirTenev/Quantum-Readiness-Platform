# Evidence Normalizer

## What this service does
- Merges raw host and network scanner evidence into a single canonical shape.
- Unifies the two certificate encodings QRP accepts — the Stage 2 nested form
  (`certificate.algorithms.signature`, `certificate.validity.not_after`,
  `subject.display_dn`, `certificate.key.size_bits`, `san.dns_names`) and the
  older flat form (`signature_algorithm`, `not_after`, `public_key_size`,
  `dns_names`) — into one stable `NormalizedCertificate`.
- Extracts crypto packages, certificate/config file indicators, and a private
  key indicator from host evidence.
- Emits `warnings` for missing, coerced, or dropped fields.

## Current role in the prototype
- Working prototype. Provides one canonical evidence document so downstream
  consumers (crypto-fingerprint-service, risk-engine) do not each re-handle the
  flat-vs-nested certificate ambiguity. Deterministic, local-first, no LLM.

## Main endpoints
- `GET /health`
- `POST /normalize`

## Inputs / outputs

`POST /normalize` accepts a raw scan payload:
- `source`, `assets[]`
- `host_inventory` and/or `crypto_evidence` (host-agent evidence)
- `tls_evidence` (or the `tls_metadata` alias) (network-scanner evidence)

It returns a canonical document:

```json
{
  "contract_version": "evn-v1",
  "source": "network",
  "assets": [{"asset_type": "endpoint", "name": "api.example.internal:443", "criticality": 3}],
  "host_evidence": null,
  "network_evidence": {
    "collected": true,
    "target": "api.example.internal",
    "tls_version": "TLS 1.3",
    "certificate": {
      "subject": "CN=api.example.internal,O=Example Internal",
      "signature_algorithm": "RSA-PSS-SHA256",
      "public_key_algorithm": "RSA",
      "dns_names": ["api.example.internal", "app.example.internal"]
    },
    "certificate_chain": {"available": true, "length": 1, "fingerprints": ["11aa..."]}
  },
  "warnings": []
}
```

## Run locally

```bash
cd services/evidence-normalizer
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --port 8009
```

## Tests

```bash
cd services/evidence-normalizer
PYTHONPATH=. pytest -q
```

## Known limitations
- Does not parse raw certificate DER or private key material; works from the
  observed evidence fields only.
- Does not persist normalized output; inventory-service remains the store of
  record. This service is a pure transformation over a single scan payload.
- Wired into the API Gateway as `POST /api/normalize`.
