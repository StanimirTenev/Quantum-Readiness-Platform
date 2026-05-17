# Stage 2 E2E Smoke Report

## Validation Date
2026-05-17T06:51:38.264354+00:00

## Scope
- enriched host evidence ingest
- enriched network TLS evidence ingest
- Stage 2 risk signal derivation
- Stage 2 planner prioritization

## Services Checked

| Service | Endpoint | Status |
|---|---|---|
| inventory-service | http://127.0.0.1:8001/health | UP |
| risk-engine | http://127.0.0.1:8002/health | UP |
| planner-service | http://127.0.0.1:8004/health | UP |

## Fixtures Used

| Fixture | Result |
|---|---|
| services/inventory-service/tests/fixtures/stage2_evidence/host_enriched_ingest.json | PASS |
| services/inventory-service/tests/fixtures/stage2_evidence/network_enriched_ingest.json | PASS |

## Inventory Results

- host scan_id: b0a17e6e-724a-4ecd-98ed-b69b5cbf0b29
- host created: 1
- host asset_ids count: 1
- network scan_id: fe20551a-906c-48ed-ae28-f43bb431de89
- network created: 1
- network asset_ids count: 1

## Risk Results

- score: 100.0
- stage2 adjustment: 43.1
- evidence signals: crypto_packages_detected, certificate_files_detected, private_key_files_detected, tls_config_detected, tls_detected, weak_public_key_detected, certificate_chain_available
- reasons: stage2 evidence signals derived from crypto and TLS metadata

## Planner Results

- assigned wave: wave_2
- planning reasons: priority_score_computed, priority_from_normalized_score, stage2_weak_public_key, wave_cap_from_weak_public_key
- no later than wave_2 check: PASS

## Result

PASS
