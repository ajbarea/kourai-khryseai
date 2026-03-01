#!/bin/bash
# Update Python dependencies using uv lock.
#
# Upgrades all dependencies to their latest compatible versions.
# Creates a backup of uv.lock before making changes.
#
# Usage:
#   ./update_dependencies.sh
#
# Dependencies: uv

set -euo pipefail

# ============================================================================
# Output
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/scripts/common.sh"

setup_unicode_env

# ============================================================================
# Main
# ============================================================================

if ! command -v uv &> /dev/null; then
    log_error "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Backup uv.lock
if [ -f "uv.lock" ]; then
    BACKUP_FILE="uv.lock.backup.$(date +%s)"
    cp uv.lock "${BACKUP_FILE}"
    log_success "Backed up to ${BACKUP_FILE}"
    
    # Keep only the last 3 backups.
    ls -t uv.lock.backup.* 2>/dev/null | tail -n +4 | xargs -r rm -f
fi

log_info "Upgrading dependencies (uv $(uv --version | cut -d' ' -f2))..."
uv lock --upgrade -q
log_success "Lock file updated"

log_info "Syncing local environment..."
uv sync --frozen --all-packages -q
log_success "Environment synced"

echo ""
log_warning "Next: Review (git diff), Test (make test), and Commit."

# Minimal restore instructions
log_info "Restore: latest=\"\$(ls -t uv.lock.backup.* | head -n1)\"; cp \"\$latest\" uv.lock; uv sync"
