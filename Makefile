.PHONY: setup docs upgrade cli gui up down restart shutdown status docker-up docker-down lint test clean help
.DEFAULT_GOAL := help

# ──────────────── Portability ────────────────
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export PYTHONIOENCODING=utf-8

# ──────────────── Local Development ────────────────

setup:                     ## Install all dependencies
	uv sync --all-packages

docs:                      ## Serve documentation (Zensical)
	uv run zensical serve

upgrade:                   ## Update dependencies to latest versions
	@bash update_dependencies.sh

cli:                       ## Launch the interactive CLI client (terminal)
	uv run python -m hosts.cli

gui:                       ## Launch the pygame GUI client (portrait window)
	uv run python -m hosts.gui

up:                        ## Start all agents locally (+ Jaeger)
	@uv run python scripts/up.py
	@uv run python scripts/status.py --wait

down:                      ## Stop all local agents
	@uv run python scripts/down.py

restart:                   ## Restart all local agents
	@$(MAKE) down
	@$(MAKE) up

shutdown:                  ## Total system shutdown (local agents + Docker)
	@uv run python scripts/down.py --total
	@docker compose down

status:                    ## Check agent health (local)
	@uv run python scripts/status.py

# ──────────────── Docker ────────────────

docker-up:                 ## Start all agents in Docker
	@uv run python scripts/docker_up.py

docker-down:               ## Stop all Docker containers
	@uv run python scripts/docker_down.py

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
