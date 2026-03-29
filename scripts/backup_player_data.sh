#!/bin/bash

##############################################################################
# Backup Player Data to HuggingFace Buckets
#
# This script performs automatic backups of Kourai player data to HuggingFace
# Storage Buckets for disaster recovery. Designed to run daily via cron.
#
# Features:
# - Versioned backups by date (YYYYMMDD_HHMMSS)
# - Automatic cleanup of old backups (>30 days by default)
# - Dry-run mode for testing
# - Error handling and logging
# - Idempotent (safe to run multiple times)
#
# Usage:
#   # Run actual backup
#   bash scripts/backup_player_data.sh
#
#   # Test backup without uploading (dry-run)
#   BACKUP_DRY_RUN=1 bash scripts/backup_player_data.sh
#
#   # Custom retention period (keep backups >14 days old)
#   BACKUP_RETENTION_DAYS=14 bash scripts/backup_player_data.sh
#
# Environment Variables (set in .env or pass on command line):
#   HF_TOKEN                 - HuggingFace API token (required)
#   BACKUP_USER              - HuggingFace username (default: extracted from HF_TOKEN metadata)
#   BACKUP_BUCKET_NAME       - Bucket name (default: kourai-backups)
#   BACKUP_RETENTION_DAYS    - Days to keep backups (default: 30)
#   BACKUP_DRY_RUN           - If 1, show what would happen without doing it
#   BACKUP_LOG_DIR           - Log directory (default: ./logs/backups/)
#
##############################################################################

set -euo pipefail

# === Configuration ===

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source .env if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    # shellcheck disable=SC1090
    source "$PROJECT_ROOT/.env"
fi

# Defaults
BACKUP_USER="${BACKUP_USER:-}"
BACKUP_BUCKET_NAME="${BACKUP_BUCKET_NAME:-kourai-backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
BACKUP_DRY_RUN="${BACKUP_DRY_RUN:-0}"
BACKUP_LOG_DIR="${BACKUP_LOG_DIR:-$PROJECT_ROOT/logs/backups}"
BACKUP_DATA_DIR="${HOME}/.kourai_khryseai/profiles"

# Create log directory
mkdir -p "$BACKUP_LOG_DIR"

# Log file
LOG_FILE="$BACKUP_LOG_DIR/backup_$(date +%Y%m%d_%H%M%S).log"

# === Functions ===

log() {
    local level="$1"
    shift
    local msg="$*"
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] [$level] $msg" | tee -a "$LOG_FILE"
}

error() {
    log "ERROR" "$@" >&2
    exit 1
}

warn() {
    log "WARN" "$@"
}

info() {
    log "INFO" "$@"
}

debug() {
    if [ "${DEBUG:-0}" = "1" ]; then
        log "DEBUG" "$@"
    fi
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# === Validation ===

info "=== Kourai Player Data Backup ==="

# Check HF_TOKEN is set
if [ -z "${HF_TOKEN:-}" ]; then
    error "HF_TOKEN not set. Set HF_TOKEN in .env or as an environment variable."
fi

# Check hf CLI is installed
if ! command_exists hf; then
    error "hf CLI not found. Install it with: pip install huggingface-hub"
fi

# Check data directory exists
if [ ! -d "$BACKUP_DATA_DIR" ]; then
    warn "Data directory not found: $BACKUP_DATA_DIR"
    warn "Kourai may not have been initialized yet. Skipping backup."
    exit 0
fi

# Check data directory has files
if [ -z "$(find "$BACKUP_DATA_DIR" -type f 2>/dev/null)" ]; then
    warn "No files found in $BACKUP_DATA_DIR. Nothing to backup."
    exit 0
fi

# === Detect HuggingFace Username ===

if [ -z "$BACKUP_USER" ]; then
    info "Detecting HuggingFace username from HF_TOKEN..."
    
    # Try to get username from whoami API
    if command_exists curl; then
        BACKUP_USER=$(curl -s -H "Authorization: Bearer $HF_TOKEN" \
            https://huggingface.co/api/user 2>/dev/null | grep -o '"name":"[^"]*"' | cut -d'"' -f4 || echo "")
    fi
    
    if [ -z "$BACKUP_USER" ]; then
        error "Could not detect HuggingFace username. Please set BACKUP_USER environment variable."
    fi
    
    info "Detected username: $BACKUP_USER"
fi

# === Create Backup ===

BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BUCKET_PATH="$BACKUP_USER/$BACKUP_BUCKET_NAME/profiles/$BACKUP_DATE"

info "Starting backup to hf://buckets/$BUCKET_PATH"
info "Source: $BACKUP_DATA_DIR"

if [ "$BACKUP_DRY_RUN" = "1" ]; then
    info "DRY RUN: Not actually uploading (use BACKUP_DRY_RUN=0 to actually backup)"
    info "Would sync: $BACKUP_DATA_DIR -> hf://buckets/$BUCKET_PATH"
    
    # Show what would be uploaded
    info "Files that would be backed up:"
    find "$BACKUP_DATA_DIR" -type f -printf "  %P\n" | sort || true
    
    exit 0
fi

# Export HF_TOKEN for hf CLI
export HF_TOKEN

# Run backup using hf buckets sync
if hf buckets sync "$BACKUP_DATA_DIR" "hf://buckets/$BUCKET_PATH" --include ".json" --quiet; then
    info "✅ Backup completed successfully"
    info "Bucket path: hf://buckets/$BUCKET_PATH"
else
    error "Backup failed. Check HF_TOKEN and bucket permissions."
fi

# === Cleanup Old Backups ===

info "Cleaning up backups older than $BACKUP_RETENTION_DAYS days..."

# Calculate cutoff timestamp (30 days ago)
if command_exists date && date --version 2>/dev/null | grep -q GNU; then
    # GNU date (Linux)
    CUTOFF_DATE=$(date -d "$BACKUP_RETENTION_DAYS days ago" +%Y%m%d)
elif command_exists date; then
    # BSD date (macOS)
    CUTOFF_DATE=$(date -v-${BACKUP_RETENTION_DAYS}d +%Y%m%d)
else
    warn "Could not determine cutoff date. Skipping cleanup."
    CUTOFF_DATE=""
fi

if [ -n "$CUTOFF_DATE" ]; then
    info "Cutoff date: $CUTOFF_DATE (keeping backups newer than this)"
    
    # List all backup folders and delete old ones
    # Note: hf buckets list --quiet outputs one path per line (e.g. "20260325_140000/")
    if hf buckets list "$BACKUP_USER/$BACKUP_BUCKET_NAME/profiles/" --quiet 2>/dev/null | while read -r folder; do
        # Extract date from folder name (YYYYMMDD_HHMMSS format)
        folder_date=$(echo "$folder" | cut -d'_' -f1 | tr -d '/')

        if [ -n "$folder_date" ] && [ "$folder_date" -lt "$CUTOFF_DATE" ]; then
            info "Deleting old backup: $folder"
            if [ "$BACKUP_DRY_RUN" = "1" ]; then
                info "DRY RUN: would delete hf://buckets/$BACKUP_USER/$BACKUP_BUCKET_NAME/profiles/$folder"
            elif hf buckets rm "$BACKUP_USER/$BACKUP_BUCKET_NAME/profiles/$folder" --recursive --quiet 2>/dev/null; then
                info "Deleted: $folder"
            else
                debug "Could not delete: $folder"
            fi
        fi
    done; then
        info "✅ Cleanup completed"
    else
        debug "Cleanup encountered issues (non-fatal)"
    fi
else
    warn "Skipping cleanup (could not determine cutoff date)"
fi

# === Summary ===

info "=== Backup Summary ==="
info "Backup date: $BACKUP_DATE"
info "Data directory: $BACKUP_DATA_DIR"
info "Bucket: $BACKUP_USER/$BACKUP_BUCKET_NAME"
info "Retention: $BACKUP_RETENTION_DAYS days"
info "Log: $LOG_FILE"
info "✅ Backup process completed successfully"

exit 0
