##
## Kourai Khryseai - Makefile
## Optional compatibility wrapper around kourai-dev CLI.
##
## Canonical workflow:
##   uv run kourai-dev <command> [-- <args...>]
##
## This Makefile delegates every target to the cross-platform Python CLI,
## so `make <target>` and `uv run kourai-dev <target>` are equivalent.
##
## Quality gates are fix-first: `make fix` runs every auto-fixer (ruff format,
## ruff check --fix) without the check pass, so subsequent `make lint` runs
## measure intent, not trivial formatting noise.
##

.PHONY: help check-env setup setup-artifacts upgrade yolo dev dev-vn up down restart rebuild status gui cli vn docs fix lint validate test test-unit test-integration test-performance audit deps clean clean-cache clean-tests prune logs logs-tail sandbox-image
.DEFAULT_GOAL := help

UV_DEV := uv run --no-active --package kourai-common kourai-dev

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

check-env:                 ## Verify uv, Python, and Docker are available
	@$(UV_DEV) check-env

# ---------------------------------------------------------------------------
# Setup & Maintenance
# ---------------------------------------------------------------------------

setup:                     ## Install all Python dependencies + optional HF Storage Buckets
	@$(UV_DEV) setup

setup-artifacts:           ## Create HF Storage Bucket for agent artifacts
	@$(UV_DEV) setup-artifacts

upgrade:                   ## Update all dependencies to latest versions
	@$(UV_DEV) upgrade

yolo:                      ## Nuke and rebuild: clean -> down -> setup -> upgrade -> clean
	@$(UV_DEV) yolo

# ---------------------------------------------------------------------------
# Development Workflows
# ---------------------------------------------------------------------------

dev:                       ## Start services + GUI (full development stack)
	@$(UV_DEV) dev

dev-vn:                    ## Start services + Ren'Py VN (visual novel stack)
	@$(UV_DEV) dev-vn

up:                        ## Start all agents + infrastructure (fast: reuses containers)
	@$(UV_DEV) up

down:                      ## Stop all services and remove containers
	@$(UV_DEV) down

restart:                   ## Restart all services (down + up)
	@$(UV_DEV) restart

rebuild:                   ## Full rebuild with Docker cache clear
	@$(UV_DEV) rebuild

status:                    ## Show current service status and health
	@$(UV_DEV) status

# ---------------------------------------------------------------------------
# Client Interfaces
# ---------------------------------------------------------------------------

gui:                       ## Launch Pygame GUI (runs on host machine)
	@$(UV_DEV) gui

gui-demo:                  ## Launch GUI in scripted demo mode (no network, no LLM — for poster screenshots)
	@uv run --no-active --package kourai-common python -m hosts.gui --demo

cli:                       ## Launch terminal CLI client (runs on host machine)
	@$(UV_DEV) cli

cli-demo:                  ## Launch CLI in scripted demo mode (no network, no LLM — for poster screenshots)
	@uv run --no-active --package kourai-common python -m hosts.cli --demo

vn:                        ## Launch Ren'Py Visual Novel GUI (runs on host machine)
	@$(UV_DEV) vn

vn-demo:                   ## Launch VN in scripted demo mode (no bridge, no Docker — for poster screenshots)
	@KOURAI_POSTER_DEMO=1 $(UV_DEV) vn

# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------

docs:                      ## Serve project documentation (Zensical on http://localhost:8000)
	@$(UV_DEV) docs

# ---------------------------------------------------------------------------
# Quality Gates
# ---------------------------------------------------------------------------

fix:                       ## Run every auto-fixer (ruff format, ruff check --fix); skip check pass
	@$(UV_DEV) fix

lint:                      ## Run code quality checks (ruff format, ruff check, ty)
	@$(UV_DEV) lint

validate:                  ## Quick validation: lint + unit tests only (fast feedback)
	@$(UV_DEV) validate

test:                      ## Run full test suite (unit + integration + performance)
	@$(UV_DEV) test

test-unit:                 ## Run unit tests only (parallel with auto CPU detection)
	@$(UV_DEV) test-unit

test-integration:          ## Run integration tests only (auto-starts containers)
	@$(UV_DEV) test-integration

test-performance:          ## Run performance tests only
	@$(UV_DEV) test-performance

audit:                     ## Audit dependencies for security vulnerabilities
	@$(UV_DEV) audit

# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

deps:                      ## Show dependency tree
	@$(UV_DEV) deps

clean:                     ## Remove build artifacts, cache, and temp files
	@$(UV_DEV) clean

clean-cache:               ## Remove cache directories only
	@$(UV_DEV) clean-cache

clean-tests:               ## Remove test artifacts only
	@$(UV_DEV) clean-tests

prune:                     ## Remove stopped containers, dangling images, unused build cache
	@$(UV_DEV) prune

# ---------------------------------------------------------------------------
# Logs
#   These do NOT go through kourai-dev — scripts truncate dev-latest.log when
#   they open, which would erase what we're trying to read.
# ---------------------------------------------------------------------------

logs:                      ## Show the last 200 lines of logs/dev-latest.log
	@tail -n 200 logs/dev-latest.log 2>/dev/null || echo "no logs yet — run any make target first"

logs-tail:                 ## Follow logs/dev-latest.log (Ctrl-C to exit)
	@tail -f logs/dev-latest.log

# ---------------------------------------------------------------------------
# Sandbox (player project execution)
# ---------------------------------------------------------------------------

sandbox-image:             ## Build the kourai-sandbox image used when KOURAI_SANDBOX=container
	@docker build -f docker/sandbox.Dockerfile -t kourai-sandbox:latest .

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

help:                      ## Show this help message
	@$(UV_DEV) help
