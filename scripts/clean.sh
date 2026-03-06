#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/common.sh"

setup_unicode_env

echo "🧹 Cleaning build artifacts and caches..."

readonly -a DIRS_TO_REMOVE=(
    "__pycache__"
    ".pytest_cache"
    ".ruff_cache"
    ".mypy_cache"
    "*.egg-info"
)

for pattern in "${DIRS_TO_REMOVE[@]}"; do
    find . -type d -name "$pattern" -exec rm -rf {} + 2>/dev/null || true
done
rm -rf logs/                      2>/dev/null || true
rm -f  .coverage coverage.xml     2>/dev/null || true
rm -f  logs/coverage.xml          2>/dev/null || true
rm -f  uv.lock.backup*            2>/dev/null || true
rm -rf .playwright-mcp/           2>/dev/null || true
rm -rf site/                      2>/dev/null || true
rm -fr .hypothesis/               2>/dev/null || true

find . -type d -name "__pycache__" -empty -delete 2>/dev/null || true

echo "Done. Workspace cleaned."