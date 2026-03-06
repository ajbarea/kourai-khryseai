#!/usr/bin/env bash
# Stop all Kourai Docker containers.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/common.sh"

setup_unicode_env

if ! docker compose --profile full down; then
    log_error "docker compose down failed"
    exit 1
fi

log_success "All containers stopped"
