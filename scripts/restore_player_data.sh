#!/bin/bash

##############################################################################
# Restore Player Data from HuggingFace Backups
#
# This script recovers player data from a HuggingFace Bucket backup.
# Useful for disaster recovery or migrating player data between machines.
#
# Features:
# - List available backups
# - Restore to current player data directory (with backup of existing data)
# - Dry-run mode for testing
# - Backup before restore (safety)
#
# Usage:
#   # List available backups
#   bash scripts/restore_player_data.sh list
#
#   # Restore specific backup
#   bash scripts/restore_player_data.sh restore 20260325_140000
#
#   # Restore latest backup
#   bash scripts/restore_player_data.sh restore latest
#
#   # Dry run (show what would happen)
#   RESTORE_DRY_RUN=1 bash scripts/restore_player_data.sh restore 20260325_140000
#
# Environment Variables:
#   HF_TOKEN                 - HuggingFace API token (required)
#   BACKUP_USER              - HuggingFace username (default: detected from token)
#   BACKUP_BUCKET_NAME       - Bucket name (default: kourai-backups)
#   RESTORE_DRY_RUN          - If 1, show what would happen without doing it
#
##############################################################################

set -euo pipefail

# === Configuration ===

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source .env.backup if it exists
if [ -f "$PROJECT_ROOT/.env.backup" ]; then
    # shellcheck disable=SC1090
    source "$PROJECT_ROOT/.env.backup"
fi

# Defaults
BACKUP_USER="${BACKUP_USER:-}"
BACKUP_BUCKET_NAME="${BACKUP_BUCKET_NAME:-kourai-backups}"
RESTORE_DRY_RUN="${RESTORE_DRY_RUN:-0}"
RESTORE_DATA_DIR="${HOME}/.kourai_khryseai"

# === Functions ===

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    log "ERROR: $*" >&2
    exit 1
}

info() {
    log "INFO: $*"
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# === Main ===

ACTION="${1:-list}"

# Validate HF_TOKEN
if [ -z "${HF_TOKEN:-}" ]; then
    error "HF_TOKEN not set. Please set HF_TOKEN or source .env.backup"
fi

# Check hf CLI
if ! command_exists hf; then
    error "hf CLI not found. Install: pip install huggingface-hub"
fi

# Detect username if needed
if [ -z "$BACKUP_USER" ]; then
    info "Detecting HuggingFace username..."
    BACKUP_USER=$(curl -s -H "Authorization: Bearer $HF_TOKEN" \
        https://huggingface.co/api/user 2>/dev/null | grep -o '"name":"[^"]*"' | cut -d'"' -f4 || echo "")
    [ -z "$BACKUP_USER" ] && error "Could not detect username. Set BACKUP_USER env var."
    info "Username: $BACKUP_USER"
fi

export HF_TOKEN

case "$ACTION" in
    list)
        info "Available backups in $BACKUP_USER/$BACKUP_BUCKET_NAME:"
        if hf buckets ls "$BACKUP_USER/$BACKUP_BUCKET_NAME/profiles/" --quiet 2>/dev/null; then
            info "Use: bash scripts/restore_player_data.sh restore <date> (e.g., 20260325_140000)"
        else
            warn "No backups found or bucket doesn't exist"
        fi
        ;;
    
    restore)
        BACKUP_DATE="${2:-}"
        [ -z "$BACKUP_DATE" ] && error "Usage: restore_player_data.sh restore <YYYYMMDD_HHMMSS | latest>"
        
        if [ "$BACKUP_DATE" = "latest" ]; then
            info "Finding latest backup..."
            BACKUP_DATE=$(hf buckets ls "$BACKUP_USER/$BACKUP_BUCKET_NAME/profiles/" --quiet 2>/dev/null | \
                sed 's|/||g' | sort -r | head -1)
            [ -z "$BACKUP_DATE" ] && error "No backups found"
            info "Latest backup: $BACKUP_DATE"
        fi
        
        SOURCE_BUCKET="$BACKUP_USER/$BACKUP_BUCKET_NAME/profiles/$BACKUP_DATE"
        
        info "Restoring from: hf://buckets/$SOURCE_BUCKET"
        info "Restore to: $RESTORE_DATA_DIR"
        
        if [ "$RESTORE_DRY_RUN" = "1" ]; then
            info "DRY RUN: Would restore from $SOURCE_BUCKET to $RESTORE_DATA_DIR"
            exit 0
        fi
        
        # Safety: backup current data first
        if [ -d "$RESTORE_DATA_DIR" ]; then
            BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
            SAFETY_BACKUP="$RESTORE_DATA_DIR.backup.$BACKUP_TIMESTAMP"
            info "Creating safety backup: $SAFETY_BACKUP"
            cp -r "$RESTORE_DATA_DIR" "$SAFETY_BACKUP"
            info "Safety backup created (restore this if needed)"
        fi
        
        # Create target directory
        mkdir -p "$RESTORE_DATA_DIR"
        
        # Restore
        info "Downloading from HuggingFace..."
        if hf buckets sync "hf://buckets/$SOURCE_BUCKET" "$RESTORE_DATA_DIR/profiles" --quiet; then
            info "✅ Restore completed successfully"
            info "Player data restored to: $RESTORE_DATA_DIR/profiles"
            
            # Restart agents to load new player data
            info "💡 Tip: Restart agents to load restored player data"
            info "   docker-compose restart"
        else
            error "Restore failed. Check HF_TOKEN and bucket access."
        fi
        ;;
    
    *)
        error "Unknown action: $ACTION. Use 'list' or 'restore <date>'"
        ;;
esac

exit 0
