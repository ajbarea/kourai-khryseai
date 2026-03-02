#!/bin/bash
# Run quality checks and full test suite for Kourai Khryseai
# Usage: ./scripts/lint.sh [--test]

set -e
trap 'echo ""; log_warning "Interrupted."; exit 130' INT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/common.sh"

setup_unicode_env

TEST_MODE=false
for arg in "$@"; do
    case $arg in
        --test) TEST_MODE=true ;;
    esac
done

log_info "⚡ Running ruff format..."
uv run ruff format .

log_info "⚡ Running ruff check --fix..."
uv run ruff check --fix --unsafe-fixes --show-fixes .

log_info "🔍 Running mypy..."
uv run mypy --config-file=pyproject.toml . || log_warning "mypy found some issues"

if [ "$TEST_MODE" = true ]; then
    COV_ARGS="--cov=. --cov-report=xml:logs/coverage.xml --cov-report=term-missing"
    mkdir -p logs

    WORKERS=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
    log_info "🧪 Running unit tests in parallel ($WORKERS workers)..."
    uv run pytest -n "$WORKERS" tests/unit/ -v --tb=short $COV_ARGS

    if [ -d "tests/integration" ]; then
        log_info "🧪 Running integration tests serially..."
        uv run pytest tests/integration/ -v --tb=short --cov=. --cov-append --cov-report=xml:logs/coverage.xml --cov-report=term-missing --ignore-glob="**/conftest.py" || [ $? -eq 5 ]
    fi
fi

echo ""
log_success "🏁 Quality checks and tests finished."
