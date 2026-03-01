.PHONY: setup docs upgrade cli up down status docker-up docker-down lint test clean help

# ──────────────── Local Development ────────────────

setup:                     ## Install all dependencies
	uv sync --all-packages

docs:                      ## Serve documentation (Zensical)
	uv run zensical serve

upgrade:                   ## Update dependencies to latest versions
	@bash update_dependencies.sh

cli:                       ## Launch the interactive CLI client
	uv run python -m hosts.cli

up:                        ## Start all agents locally (+ Jaeger)
	@echo "🔥 Starting Kourai Khryseai..."
	docker compose up -d jaeger
	@mkdir -p logs
	uv run python -m agents.mneme > logs/mneme.log 2>&1 &
	uv run python -m agents.kallos > logs/kallos.log 2>&1 &
	uv run python -m agents.techne > logs/techne.log 2>&1 &
	uv run python -m agents.dokimasia > logs/dokimasia.log 2>&1 &
	uv run python -m agents.metis > logs/metis.log 2>&1 &
	@sleep 2
	uv run python -m agents.hephaestus > logs/hephaestus.log 2>&1 &
	@echo "✅ All agents running"
	@echo "🔍 Jaeger: http://localhost:16686"

down:                      ## Stop all local agents
	@pkill -f "python -m agents" 2>/dev/null || true
	@echo "🛑 All agents stopped"

status:                    ## Check agent health (local)
	@for port in 10000 10001 10002 10003 10004 10005; do \
		name=$$(curl -s http://localhost:$$port/.well-known/agent.json 2>/dev/null | \
		python -c "import json,sys; print(json.load(sys.stdin).get('name','?'))" 2>/dev/null); \
		if [ -n "$$name" ]; then \
			echo "✅ $$name :$$port"; \
		else \
			echo "❌ Port $$port not responding"; \
		fi \
	done

# ──────────────── Docker ────────────────

docker-up:                 ## Start all agents in Docker
	docker compose --profile full up -d --build
	@echo "✅ All agents running in Docker"
	@echo "🔍 Jaeger: http://localhost:16686"

docker-down:               ## Stop all Docker containers
	docker compose --profile full down
	@echo "🛑 All containers stopped"

# ──────────────── Testing & Quality ────────────────

lint:                      ## Run quality checks (ruff, mypy)
	@bash scripts/lint.sh

test:                      ## Run quality checks + full test suite
	@bash scripts/lint.sh --test

clean:                     ## Clean build artifacts
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -f .coverage coverage.xml logs/coverage.xml 2>/dev/null || true
	@rm -f uv.lock.backup* 2>/dev/null || true
	@rm -rf .playwright-mcp/ 2>/dev/null || true

help:                      ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
