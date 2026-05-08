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

## Current status
- Working prototype service.

## How to run tests
- `cd agents/linux-host-agent && go test ./...`

## Known limitations
- Evidence depth depends on host permissions, installed tools, and available config paths.
- Package metadata collection is best-effort and non-fatal. If collection fails, `package_metadata.collected` is `false`, `package_manager` becomes `unknown`, and the error is recorded in `package_metadata.errors`.

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
  "package_metadata": {
    "package_manager": "dpkg",
    "collected": true,
    "packages": [
      {
        "name": "openssl",
        "version": "3.0.2-0ubuntu1",
        "source": "dpkg"
      }
    ],
    "errors": []
  }
}
```
