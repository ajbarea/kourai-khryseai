##
## Kourai Khryseai — Makefile
## Multi-agent A2A development system with Pygame GUI or CLI interfaces, 
## Dockerized agents, and integrated monitoring (Jaeger + Prometheus)
##
## Usage:
##   make help          Show all available commands
##   make dev           Full development stack: agents + GUI + monitoring
##   make up            Start all services (background)
##   make down          Stop all services
##

.PHONY: help setup upgrade dev dev-vn up down restart status gui cli vn docs lint test test-unit test-integration test-performance clean prune
.DEFAULT_GOAL := help

# ════════════════════════════════════════════════════════════════════════════
# Environment
# ════════════════════════════════════════════════════════════════════════════

export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export PYTHONIOENCODING=utf-8

# Isolate platform-specific virtual environments to prevent binary conflicts
ifeq ($(OS),Windows_NT)
    ifdef WSL_DISTRO_NAME
        export UV_PROJECT_ENVIRONMENT ?= .venv-wsl
    else
        export UV_PROJECT_ENVIRONMENT ?= .venv-win
    endif
else
    # macOS and native Linux use standard .venv
    export UV_PROJECT_ENVIRONMENT ?= .venv
endif

COMPOSE_FULL := docker compose
HOST_UV_RUN := uv run --no-active python scripts/run_in_host_env.py --
GUI_ARGS ?= --agent http://localhost:10000/
CLI_ARGS ?=

# ════════════════════════════════════════════════════════════════════════════
# Setup & Maintenance (run first time, or when dependencies change)
# ════════════════════════════════════════════════════════════════════════════

setup:                     ## Install all Python dependencies (workspace + all packages)
	uv sync --all-packages --no-active

upgrade:                   ## Update all dependencies to latest versions
	uv run --no-active python scripts/upgrade.py

# ════════════════════════════════════════════════════════════════════════════
# Core Development Workflows (primary entry points)
# ════════════════════════════════════════════════════════════════════════════

dev:                       ## Start services + GUI (full development stack in one command)
	@$(MAKE) --no-print-directory down
	@$(MAKE) --no-print-directory up
	@echo
	@echo Starting GUI...
	@$(MAKE) --no-print-directory gui

dev-vn:                    ## Start services + Ren'Py VN (full development stack with visual novel)
	@$(MAKE) --no-print-directory down
	@$(MAKE) --no-print-directory up
	@echo
	@echo Starting Ren\'Py VN...
	@$(MAKE) --no-print-directory vn

up:                        ## Start all agents + infrastructure (background, waits for health)
	$(COMPOSE_FULL) up -d --build --pull always --wait --wait-timeout 180
	@echo All services running and healthy
	@echo Dashboards:
	@echo   Jaeger traces:      http://localhost:16686
	@echo   Prometheus metrics: http://localhost:9090
	@$(COMPOSE_FULL) ps

down:                      ## Stop all services and remove containers
	$(COMPOSE_FULL) down --remove-orphans

restart:                   ## Restart all services (same as: make down && make up)
	@$(MAKE) --no-print-directory down
	@$(MAKE) --no-print-directory up

status:                    ## Show current service status and health
	$(COMPOSE_FULL) ps

# ════════════════════════════════════════════════════════════════════════════
# Client Interfaces (connect to running services)
# ════════════════════════════════════════════════════════════════════════════

gui:                       ## Launch Pygame GUI (runs on host machine)
	$(HOST_UV_RUN) python -m hosts.gui $(GUI_ARGS)

cli:                       ## Launch terminal CLI client (runs on host machine)
	$(HOST_UV_RUN) python -m hosts.cli $(CLI_ARGS)

vn:                        ## Launch Ren'Py Visual Novel GUI (runs on host machine)
	./hosts/vn/renpy-8.5.2-sdk/renpy.exe ./hosts/vn/kourai_vn/

# ════════════════════════════════════════════════════════════════════════════
# Documentation & Utilities
# ════════════════════════════════════════════════════════════════════════════

docs:                      ## Serve project documentation (Zensical on http://localhost:8000)
	uv run --no-active zensical serve

# ════════════════════════════════════════════════════════════════════════════
# Quality Gates (run before commit; cross-platform via Python scripts)
# ════════════════════════════════════════════════════════════════════════════

lint:                      ## Run code quality checks (ruff format, ruff check, mypy)
	uv run --no-active ruff format .
	uv run --no-active ruff check --fix --unsafe-fixes --show-fixes .
	uv run --no-active mypy --config-file=pyproject.toml .

test:                      ## Run full test suite with quality checks (unit + integration + performance)
	@$(MAKE) --no-print-directory lint
	@$(MAKE) --no-print-directory test-unit
	@$(MAKE) --no-print-directory test-integration
	@$(MAKE) --no-print-directory test-performance

test-unit:                 ## Run unit tests only (parallel with auto CPU detection)
	uv run --no-active pytest -n auto tests/unit/ -v --tb=short --cov=. --cov-report=xml:logs/coverage.xml --cov-report=term-missing

test-integration:          ## Run integration tests only
	uv run --no-active pytest tests/integration/ -v --tb=short --cov=. --cov-append --cov-report=xml:logs/coverage.xml --cov-report=term-missing

test-performance:          ## Run performance tests only
	uv run --no-active pytest tests/performance/ -v --tb=short --cov=. --cov-append --cov-report=xml:logs/coverage.xml --cov-report=term-missing

clean:                     ## Remove build artifacts, cache, and temp files
	uv run --no-active python scripts/clean_build.py

clean-cache:               ## Remove cache directories only
	uv run --no-active python scripts/clean_build.py --cache-only

clean-tests:               ## Remove test artifacts only
	uv run --no-active python scripts/clean_build.py --tests-only

prune:                     ## Remove stopped containers, dangling images, and unused build cache
	docker system prune -f

# ════════════════════════════════════════════════════════════════════════════
# Help
# ════════════════════════════════════════════════════════════════════════════

help:                      ## Show this help message
	uv run --no-active python scripts/show_help.py
