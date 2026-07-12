#!/usr/bin/env bash
# DB migration smoke test (Postgres-only path -- see
# docs/adr/0001-product-v1-architecture.md). Proves:
#   1. a clean Postgres database can be created via Alembic migrations
#      (inventory-service + workflow-service, each with its own
#      version_table since they share one physical database);
#   2. an already-migrated database can be "upgraded" again safely
#      (idempotent re-run, standing in for a real future upgrade until a
#      second migration exists to test against);
#   3. `alembic current` reports the expected head revision for both.
#
# Requires DATABASE_URL to already point at a reachable Postgres database
# (e.g. `docker compose up -d postgres` in infra/docker, or a local
# instance) -- this script does not start one itself, matching
# `make db-migrate`/`make db-check`'s own assumption. SQLite is not
# involved at all; this only exercises the Postgres/production path.
#
# Writes reports/db-migration-smoke-report.md and exits non-zero on any
# check failure.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_PATH="$ROOT_DIR/reports/db-migration-smoke-report.md"

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "DATABASE_URL is not set -- point it at a reachable Postgres database first" >&2
    echo "(e.g.: cd infra/docker && docker compose up -d postgres, then" >&2
    echo " DATABASE_URL=postgresql://qrp:qrp@127.0.0.1:5432/qrp bash scripts/run_db_migration_smoke.sh)" >&2
    exit 1
fi

declare -a NAMES=()
declare -a STATUSES=()
declare -a DETAILS=()

record() {
    NAMES+=("$1")
    STATUSES+=("$2")
    DETAILS+=("$3")
}

run_alembic() {
    local service_dir="$1"
    shift
    (cd "$ROOT_DIR/services/$service_dir" && DATABASE_URL="$DATABASE_URL" alembic "$@")
}

overall="PASS"

for service in inventory-service workflow-service; do
    if out="$(run_alembic "$service" upgrade head 2>&1)"; then
        record "$service: apply migrations" "PASS" "upgrade head succeeded"
    else
        record "$service: apply migrations" "FAIL" "$out"
        overall="FAIL"
    fi

    if out="$(run_alembic "$service" upgrade head 2>&1)"; then
        record "$service: re-apply (idempotency / upgrade check)" "PASS" "second upgrade head succeeded (no-op)"
    else
        record "$service: re-apply (idempotency / upgrade check)" "FAIL" "$out"
        overall="FAIL"
    fi

    current="$(run_alembic "$service" current 2>&1 || true)"
    if echo "$current" | grep -q "0001 (head)"; then
        record "$service: verify head revision" "PASS" "$(echo "$current" | tail -1)"
    else
        record "$service: verify head revision" "FAIL" "$current"
        overall="FAIL"
    fi
done

{
    echo "# DB Migration Smoke Report"
    echo
    echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo
    echo "| Check | Status | Detail |"
    echo "| --- | --- | --- |"
    for i in "${!NAMES[@]}"; do
        detail_escaped="${DETAILS[$i]//|/\\|}"
        echo "| ${NAMES[$i]} | ${STATUSES[$i]} | ${detail_escaped:0:200} |"
    done
    echo
    echo "## Result: $overall"
} > "$REPORT_PATH"

echo "Report written: $REPORT_PATH"
if [[ "$overall" == "PASS" ]]; then
    echo "== Summary: PASS =="
    exit 0
else
    echo "== Summary: FAIL =="
    exit 1
fi
