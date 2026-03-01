.PHONY: setup cli up down status test lint clean jaeger docker-up docker-down docker-build docker-status docs upgrade

# ──────────────── Local Development ────────────────

setup:                     ## Install all dependencies
	uv sync --all-packages

docs:                      ## Serve documentation (Zensical)
	uv run zensical serve

upgrade:                   ## Update dependencies to latest versions
	@bash update_dependencies.sh

jaeger:                    ## Start Jaeger observability
	docker compose up -d jaeger
	@echo "🔍 Jaeger UI: http://localhost:16686"

cli:                       ## Launch the interactive CLI client
	uv run python -m hosts.cli

up: jaeger                 ## Start all agents locally (+ Jaeger)
	@echo "🔥 Starting Kourai Khryseai..."
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

docker-build:              ## Build all agent Docker images
	docker compose --profile full build

docker-up:                 ## Start all agents in Docker containers
	docker compose --profile full up -d
	@echo "✅ All agents running in Docker"
	@echo "🔍 Jaeger: http://localhost:16686"

docker-down:               ## Stop all Docker containers
	docker compose --profile full down
	@echo "🛑 All containers stopped"

docker-status:             ## Check Docker container health
	docker compose --profile full ps

docker-logs:               ## Tail logs from all containers
	docker compose --profile full logs -f

# ──────────────── Testing & Quality ────────────────

lint:                      ## Run all quality checks (ruff, mypy)
	@bash scripts/lint.sh

test:                      ## Run all quality checks and the full test suite
	@bash scripts/lint.sh --test

coverage:                  ## Run tests with coverage reporting
	@echo "📊 Collecting coverage..."
	@mkdir -p logs
	@uv run pytest --cov=. --cov-report=xml:logs/coverage.xml --cov-report=html:logs/coverage_html --cov-report=term-missing tests/

check: test                ## Alias for full quality check

format: lint               ## Alias for proactive linting

clean:                     ## Clean build artifacts
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -f .coverage coverage.xml 2>/dev/null || true
	@rm -rf logs/coverage_html 2>/dev/null || true

help:                      ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
