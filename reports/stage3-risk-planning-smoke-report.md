# Stage 3 Risk/Planning Smoke Report

## Validation Date
2026-05-09T08:30:50Z

## Scope
- enriched evidence ingest
- risk confidence_score
- risk_dimensions
- Stage 2 evidence signals
- planner priority_score
- planner wave rationale

## Services Checked

| Service | Endpoint | Status |
|---|---|---|
| inventory-service | http://127.0.0.1:8001/health | PASS |
| risk-engine | http://127.0.0.1:8002/health | PASS |
| planner-service | http://127.0.0.1:8004/health | PASS |

## Inventory Results

- host scan_id: de0090d1-9037-451d-9198-74080470aa47
- host created: 1
- host asset_ids count: 1
- network scan_id: 20282d35-d824-4f03-8955-c2052409b4ee
- network created: 1
- network asset_ids count: 1

## Risk Results

- score: 100.0
- confidence_score: 100.0
- risk_dimensions: {
  "exposure": 100.0,
  "impact": 100.0,
  "urgency": 100.0,
  "migration_complexity": 53.0
}
- evidence signals: {
  "crypto_packages_detected": true,
  "certificate_files_detected": true,
  "private_key_files_detected": true,
  "tls_config_detected": true,
  "ssh_config_detected": true,
  "tls_detected": true,
  "weak_public_key_detected": true,
  "expiring_certificate_detected": true,
  "certificate_chain_available": true
}
- reasons: {
  "criticality": 4.5,
  "confidentiality_lifetime": 4.0,
  "quantum_exposure": 4.8,
  "blast_radius": 4.2,
  "vendor_lock_in": 2.5,
  "migration_difficulty": 3.8,
  "dependency_count": 7,
  "vendor_blocked": false,
  "crypto_packages_detected": true,
  "certificate_files_detected": true,
  "private_key_files_detected": true,
  "tls_config_detected": true,
  "ssh_config_detected": true,
  "tls_detected": true,
  "weak_public_key_detected": true,
  "expiring_certificate_detected": true,
  "certificate_chain_available": true,
  "confidence_score_computed": "yes",
  "risk_dimensions_computed": "yes",
  "exposure_dimension_from_tls": true,
  "impact_dimension_from_criticality": true,
  "urgency_dimension_from_expiring_certificate": true,
  "migration_complexity_from_private_key_files": true
}

## Planner Results

- assigned wave: wave_1
- priority_score: 88.0
- planning reasons: priority_score_computed, priority_from_normalized_score
- wave cap check: PASS

## Result

PASS
