# Network Scanner

## What this service does
- Performs TLS endpoint scans and builds network evidence payloads.
- Collects richer `tls_metadata` for negotiated protocol/cipher details and leaf certificate properties.

## Current role in the prototype
- Working prototype agent for network-side evidence collection and optional ingest into `inventory-service`.

## Main endpoints or functions
- CLI entrypoint: `cmd/scanner/main.go`
- Main flow: `scanner.ScanTLS(target, insecure, timeout)` and optional `client.PostScan(...)`

## Inputs / outputs
- Input: CLI flags (`-target`, `-insecure`, `-timeout`, optional `-ingest`).
- Output: JSON TLS evidence (stdout) or ingest response JSON.

### TLS metadata fields
`tls_metadata` is always present in output JSON and includes:
- `collected`
- `target`
- `port`
- `server_name`
- `protocol_version`
- `cipher_suite`
- `certificate` (or `null` on failure)
  - `subject`
  - `issuer`
  - `not_before`
  - `not_after`
  - `signature_algorithm`
  - `public_key_algorithm`
  - `public_key_size`
  - `fingerprint_sha256`
- `certificate_chain`
  - `available`
  - `length`
  - `certificates`
    - `position`
    - `subject`
    - `issuer`
    - `not_before`
    - `not_after`
    - `signature_algorithm`
    - `public_key_algorithm`
    - `public_key_size`
    - `fingerprint_sha256`
  - `errors`
- `errors`

Collection is best-effort and non-fatal per target: if TLS collection fails, scanning returns stable JSON with `collected=false`, empty protocol/cipher strings, `certificate=null`, and an `errors` list.

`certificate_chain` is a summary of certificates presented by the peer TLS connection state only. It is not a full trust validation result, does not fetch missing intermediates, and does not perform OCSP/AIA lookups.

## Timeout and scanning behavior
- The scanner remains non-aggressive and uses a single TLS dial attempt with configurable timeout (`-timeout`, default `5s`).
- No async or parallel scanning behavior is introduced.

## Sample output (success)
```json
{
  "source": "network",
  "tls_metadata": {
    "collected": true,
    "target": "example.com",
    "port": 443,
    "server_name": "example.com",
    "protocol_version": "TLS 1.3",
    "cipher_suite": "TLS_AES_256_GCM_SHA384",
    "certificate": {
      "subject": "CN=*.example.com,O=Example Corp",
      "issuer": "CN=Example Issuing CA",
      "not_before": "2026-01-01T00:00:00Z",
      "not_after": "2027-01-01T23:59:59Z",
      "signature_algorithm": "SHA256-RSA",
      "public_key_algorithm": "RSA",
      "public_key_size": 2048,
      "fingerprint_sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    },
    "certificate_chain": {
      "available": true,
      "length": 2,
      "certificates": [
        {
          "position": 0,
          "subject": "CN=*.example.com,O=Example Corp",
          "issuer": "CN=Example Issuing CA",
          "not_before": "2026-01-01T00:00:00Z",
          "not_after": "2027-01-01T23:59:59Z",
          "signature_algorithm": "SHA256-RSA",
          "public_key_algorithm": "RSA",
          "public_key_size": 2048,
          "fingerprint_sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
        }
      ],
      "errors": []
    },
    "errors": []
  },
  "assets": [
    {
      "asset_type": "endpoint",
      "name": "example.com:443",
      "criticality": 3,
      "environment": "unknown",
      "lifecycle_years": 3
    }
  ]
}
```

## Current status
- Working prototype service.

## How to run tests
- `cd agents/network-scanner && go test ./...`

## Known limitations
- Current implementation is TLS-focused; SSH/VPN scanning is not implemented.
