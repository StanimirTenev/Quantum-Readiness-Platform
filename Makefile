.PHONY: dev-up dev-down demo test

dev-up:
	bash scripts/start_all.sh

dev-down:
	bash scripts/stop_all.sh

demo:
	bash scripts/run_product_demo.sh

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
