# Copilot Offline Smoke Report

## Validation Date
2026-05-17T06:51:59Z

## Scope
- disabled provider default
- offline-safe deterministic response
- no external LLM call
- no network dependency

## Provider Mode
disabled

## Request Summary
request_id: copilot-offline-smoke-001
query: Explain current QRP risk status.

## Response Summary
used_external_provider: false
warnings: copilot_provider_disabled

## Boundary Checks

| Check | Result |
|---|---|
| provider_mode is disabled | PASS |
| used_external_provider is false | PASS |
| warning includes copilot_provider_disabled | PASS |
| deterministic disabled response returned | PASS |
| no external endpoint required | PASS |
| no API key required | PASS |

## Result

PASS
