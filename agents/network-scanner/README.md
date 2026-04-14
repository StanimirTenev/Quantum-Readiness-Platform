# Network Scanner

## What this service does
- Performs TLS endpoint scans and builds network evidence payloads.

## Current role in the prototype
- Working prototype agent for network-side evidence collection and optional ingest into `inventory-service`.

## Main endpoints or functions
- CLI entrypoint: `cmd/scanner/main.go`
- Main flow: `scanner.ScanTLS(target, insecure, timeout)` and optional `client.PostScan(...)`

## Inputs / outputs
- Input: CLI flags (`-target`, `-insecure`, `-timeout`, optional `-ingest`).
- Output: JSON TLS evidence (stdout) or ingest response JSON.

## Current status
- Working prototype service.

## How to run tests
- `cd agents/network-scanner && go test ./...`

## Known limitations
- Current implementation is TLS-focused; SSH/VPN scanning is not implemented.
