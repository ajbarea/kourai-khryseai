#!/bin/bash
# Run quality checks and full test suite for Kourai Khryseai
# Usage: ./scripts/lint.sh [--test]

set -e

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
    log_info "🧪 Running unit tests in parallel (12 workers)..."
    uv run pytest -n auto tests/unit/ -v --tb=short

    if [ -d "tests/integration" ]; then
        log_info "🧪 Running integration tests serially..."
        uv run pytest tests/integration/ -v --tb=short
    fi
fi

echo ""
log_success "🏁 Quality checks and tests finished."
