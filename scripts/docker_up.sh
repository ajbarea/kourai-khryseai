#!/usr/bin/env bash
# Start all Kourai agents in Docker with full profile.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/common.sh"

setup_unicode_env

if ! docker compose --profile full up -d --build; then
    log_error "docker compose up failed"
    exit 1
fi

log_success "All agents running in Docker"
log_info "Jaeger: http://localhost:16686"
log_info "Prometheus: http://localhost:9090"
