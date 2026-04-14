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

## Current status
- Working prototype service.

## How to run tests
- `cd agents/linux-host-agent && go test ./...`

## Known limitations
- Evidence depth depends on host permissions, installed tools, and available config paths.
