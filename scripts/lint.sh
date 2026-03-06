#!/usr/bin/env bash
# Run quality checks and full test suite for Kourai Khryseai
# Usage: ./scripts/lint.sh [--test]

set -euo pipefail
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

LINT_FAIL=false

log_info "⚡ Running ruff format..."
uv run ruff format . || LINT_FAIL=true

log_info "⚡ Running ruff check --fix..."
uv run ruff check --fix --unsafe-fixes --show-fixes . || LINT_FAIL=true

log_info "🔍 Running mypy..."
uv run mypy --config-file=pyproject.toml . || {
    log_error "mypy found some issues"
    LINT_FAIL=true
}

if [ "$TEST_MODE" = true ]; then
    COV_ARGS="--cov=. --cov-report=xml:logs/coverage.xml --cov-report=term-missing"
    mkdir -p logs

    WORKERS=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
    log_info "🧪 Running unit tests in parallel ($WORKERS workers)..."
    uv run pytest -n "$WORKERS" tests/unit/ -v --tb=short $COV_ARGS || LINT_FAIL=true

    if [ -d "tests/integration" ]; then
        log_info "🧪 Running integration tests serially..."
        uv run pytest tests/integration/ -v --tb=short --cov=. --cov-append --cov-report=xml:logs/coverage.xml --cov-report=term-missing --ignore-glob="**/conftest.py" || {
            RET=$?
            if [ $RET -ne 5 ]; then
                LINT_FAIL=true
            fi
        }
    fi
fi

echo ""
if [ "$LINT_FAIL" = true ]; then
    log_error "Quality checks failed. Please fix the issues and try again."
    exit 1
else
    log_success "🏁 Quality checks and tests finished."
fi
