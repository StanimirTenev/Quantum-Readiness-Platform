# Linux Host Agent

## What this service does
- Collects local host inventory and crypto-related evidence from a Linux machine.

## Current role in the prototype
- Working prototype agent for host-side evidence collection and optional ingest into `inventory-service`.

## Main endpoints or functions
- CLI entrypoint: `cmd/agent/main.go`
- Main flow: `collector.Collect()` and optional `client.PostScan(...)` with `-ingest`

## Inputs / outputs
- Input: local OS/files/package state; CLI flags (`-ingest`, `-inventory-url`).
- Output: JSON evidence payload (stdout) or ingest response JSON.
- Output includes `crypto_evidence.package_metadata` with best-effort crypto/security package metadata collection.
- Output includes `crypto_evidence.cert_indicators.certificate_file_indicators` with best-effort certificate/key footprint discovery based on file names only.

## Current status
- Working prototype service.

## How to run tests
- `cd agents/linux-host-agent && go test ./...`

## Known limitations
- Evidence depth depends on host permissions, installed tools, and available config paths.
- Package metadata collection is best-effort and non-fatal. If collection fails, `package_metadata.collected` is `false`, `package_manager` becomes `unknown`, and the error is recorded in `package_metadata.errors`.
- Certificate file discovery is limited to standard paths, max traversal depth 3, and max 200 files to avoid broad filesystem scans.
- Certificate file discovery does not read or parse certificate/key contents; it only inspects path names and extensions.

## Certificate file discovery
- Standard paths inspected (if present):
  - `/etc/ssl`
  - `/etc/pki`
  - `/etc/ca-certificates`
  - `/usr/local/share/ca-certificates`
  - `/etc/letsencrypt`
  - `/etc/nginx`
  - `/etc/apache2`
  - `/etc/httpd`
  - `/etc/haproxy`
  - `/etc/openvpn`
  - `/etc/ipsec.d`
  - `/etc/strongswan`
  - `/etc/ssh`
- Matching/classification is deterministic and based on file names/extensions only:
  - `certificate`: `.crt`, `.cer`, `.pem`, `.der`
  - `key`: `.key`, `id_rsa`, `id_ecdsa`, `id_ed25519`
  - `keystore`: `.jks`, `.p12`, `.pfx`, `keystore`
  - `truststore`: `cacerts`, `truststore`
  - `unknown`: crypto-looking names that do not map to a stronger class
- Best-effort and non-fatal: inaccessible directories/files are recorded in `errors`, while the agent continues collection.

## Package metadata collection
- Supported package managers: `dpkg`/`apt` (via `dpkg-query`), `rpm`, `apk`, and `pacman`.
- If no supported package manager is detected, the agent returns:
  - `package_manager: "unknown"`
  - `collected: true`
  - `packages: []`
  - `errors: []`
- The agent only keeps crypto/security-relevant package names (for example: OpenSSL/libssl, SSH, certificates, TLS/network security tooling, Java/OpenJDK/keytool, and common TLS termination services).

### Sample JSON block
```json
{
  "certificate_file_indicators": {
    "collected": true,
    "searched_paths": [
      "/etc/ssl",
      "/etc/pki",
      "/usr/local/share/ca-certificates"
    ],
    "files": [
      {
        "path": "/etc/ssl/certs/ca-certificates.crt",
        "type": "certificate",
        "extension": ".crt",
        "readable": true,
        "source": "standard_path"
      }
    ],
    "counts": {
      "certificate": 1,
      "key": 0,
      "keystore": 0,
      "truststore": 0,
      "unknown": 0
    },
    "errors": []
  }
}
```
