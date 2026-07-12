.PHONY: dev-up dev-down demo test db-migrate db-check

dev-up:
	bash scripts/start_all.sh

dev-down:
	bash scripts/stop_all.sh

demo:
	bash scripts/run_product_demo.sh

# Postgres-only (see docs/adr/0001-product-v1-architecture.md): applies both
# services' Alembic migrations to whatever DATABASE_URL points at. Requires
# DATABASE_URL to be exported and alembic/psycopg installed locally (or use
# infra/docker's inventory-migrate/workflow-migrate one-shot containers
# instead, which run automatically on `docker compose up`).
db-migrate:
	cd services/inventory-service && alembic upgrade head
	cd services/workflow-service && alembic upgrade head

db-check:
	cd services/inventory-service && alembic current
	cd services/workflow-service && alembic current

test:
	for d in services/*/; do \
		if [ -d "$${d}tests" ]; then \
			(cd "$$d" && PYTHONPATH=. python3 -m pytest -q) || exit 1; \
		fi; \
	done
	PYTHONPATH=. python3 -m pytest tools/graph_projection tools/report -q
	cd agents/repo-ci-scanner && PYTHONPATH=. python3 -m pytest -q
	cd agents/doc-ingestion && PYTHONPATH=. python3 -m pytest -q
	cd agents/linux-host-agent && go build ./... && go test ./...
	cd agents/network-scanner && go build ./... && go test ./...
	node --check frontend/web-ui/public/app.js
