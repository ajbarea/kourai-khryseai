.PHONY: setup docs upgrade cli gui up down restart status lint test clean help
.DEFAULT_GOAL := help

# ──────────────── Portability ────────────────
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export PYTHONIOENCODING=utf-8

COMPOSE_FULL := docker compose --profile full

# ──────────────── Development ────────────────

setup:                     ## Install all dependencies
	uv sync --all-packages

docs:                      ## Serve documentation (Zensical)
	uv run zensical serve

upgrade:                   ## Update dependencies to latest versions
	@bash scripts/update_dependencies.sh

cli:                       ## Launch the interactive CLI client (terminal)
	uv run python -m hosts.cli

gui:                       ## Launch the pygame GUI client (portrait window)
	uv run python -m hosts.gui

up:                        ## Start all agents in Docker (+ Jaeger)
	$(COMPOSE_FULL) up -d --build --wait --wait-timeout 120
	@echo All services are running and healthy.
	@echo Jaeger UI: http://localhost:16686
	@echo Prometheus: http://localhost:9090
	@$(COMPOSE_FULL) ps

down:                      ## Stop all Docker containers
	$(COMPOSE_FULL) down --remove-orphans

restart:                   ## Restart all agents
	@$(MAKE) --no-print-directory down
	@$(MAKE) --no-print-directory up

status:                    ## Show Docker service status/health
	$(COMPOSE_FULL) ps

dev:					   ## Restart services and launch GUI client
	@$(MAKE) down
	@$(MAKE) up
	@$(MAKE) gui

# ──────────────── Testing & Quality ────────────────

lint:                      ## Run quality checks (ruff, mypy)
	@bash scripts/lint.sh

test:                      ## Run quality checks + full test suite
	@bash scripts/lint.sh --test

clean:                     ## Clean build artifacts
	@bash scripts/clean.sh

help:                      ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
