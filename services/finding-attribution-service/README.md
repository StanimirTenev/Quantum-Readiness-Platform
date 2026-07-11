# Finding Attribution Service

Implements the **Finding Location & Application Attribution Contract**: every
crypto-fingerprint finding is enriched with a typed **location** and an
**attribution** to an asset, service/application, and the concrete crypto object
it lives on (certificate / library / pipeline / cipher suite). Each finding
carries an explicit **chain**:

```
vulnerability → location → service/application → asset → certificate/library/pipeline
```

## Main endpoints
- `GET /health`
- `GET /contract` — the contract shape (chain, location kinds, crypto-object kinds).
- `POST /attribute` — attribute a batch of findings for one asset.

## Inputs / outputs

`POST /attribute`:

```json
{
  "asset_name": "payments-api",
  "application": "payments",
  "findings": [ { "source": "tls_certificate", "algorithm_family": "RSA", "classification": "classical_vulnerable", "severity": "high", "raw_value": "RSA" } ],
  "network_evidence": { "target": "api.example.internal", "port": 443, "certificate": { "subject": "CN=api.example.internal", "fingerprint_sha256": "abc123" } }
}
```

returns:

```json
{
  "contract_version": "attr-v1",
  "asset_name": "payments-api",
  "attributed_findings": [
    {
      "finding_id": "finding:...",
      "vulnerability": { "algorithm_family": "RSA", "classification": "classical_vulnerable", "severity": "high", "quantum_vulnerable": true, "harvest_now_decrypt_later": false, "reason": "..." },
      "location": { "kind": "network_endpoint", "value": "api.example.internal:443", "evidence_ref": "tls_metadata.certificate.public_key" },
      "attribution": {
        "asset": "payments-api",
        "service": "api.example.internal:443",
        "application": "payments",
        "crypto_object": { "kind": "certificate", "id": "certificate:abc123", "label": "CN=api.example.internal" }
      },
      "chain": ["RSA (classical_vulnerable)", "api.example.internal:443", "api.example.internal:443", "asset:payments-api", "certificate:CN=api.example.internal"]
    }
  ],
  "summary": { "total": 1, "attributed": 1, "unattributed": 0, "network_endpoint": 1, "package": 0 }
}
```

- Accepts the evidence-normalizer shapes (`network_evidence`, `host_evidence`) or
  the raw scanner shapes (`tls_metadata`, `crypto_evidence`).
- `findings` are crypto-fingerprint-service findings; the finding's `source` /
  `location` decides the location kind and crypto object:
  - `tls_certificate` → network endpoint + certificate
  - `tls_cipher_suite` → network endpoint + cipher suite
  - `host_package` → package + library
  - `repo_ci_pipeline` → config file + pipeline (repo-ci-scanner's CI/CD signing-command findings)
  - `repo_embedded_key` → config file + config (repo-ci-scanner's embedded-private-key findings)
  - `explicit_algorithm` → manual (unattributed)
- `finding_id` is deterministic (stable across runs for the same input).

## Run locally

```bash
cd services/finding-attribution-service
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --port 8014
```

## Tests

```bash
cd services/finding-attribution-service
PYTHONPATH=. pytest -q
```

## Wiring
- API Gateway: `POST /api/attribute`, and folded into `POST /api/assess`
  (fingerprint → pqc-readiness → **attribution** → optional risk).

## Known limitations
- Attributes from supplied findings + evidence context; it does not fetch
  evidence itself.
- `pipeline`/`config` are now reachable via `repo_ci_pipeline`/`repo_embedded_key`
  sources (see above), which crypto-fingerprint-service emits from
  `crypto_evidence.repo_scan.ci_pipeline_findings`/`embedded_key_findings`.
  `source_code_findings`/`iac_findings` algorithm detections still flow through
  the existing `host_package` path (repo-ci-scanner folds them into
  `package_metadata.packages` before ingest), so they attribute as `library`
  rather than a repo-specific crypto object -- accurate for scoring, but the
  location/label doesn't distinguish "found in source" from "an actual host
  package".
