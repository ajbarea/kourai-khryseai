#!/bin/bash

##############################################################################
# Setup Automated Daily Backups via Cron
#
# This script configures automated daily backups of player data to HuggingFace
# Buckets. It creates a cron job that runs backup_player_data.sh daily.
#
# Features:
# - Automatic daily backups at 2 AM UTC (configurable)
# - Logs backups to ./logs/backups/
# - Works on Linux (via crontab) and macOS
# - Safety: Creates backup of existing crontab before modifying
#
# Usage:
#   # Install daily backup cron job
#   bash scripts/setup-cron.sh
#
#   # Uninstall cron job
#   bash scripts/setup-cron.sh uninstall
#
# Environment Variables:
#   BACKUP_CRON_HOUR       - Hour to run backup (default: 2 = 2 AM UTC)
#   BACKUP_CRON_MINUTE     - Minute to run backup (default: 0 = on the hour)
#
##############################################################################

set -euo pipefail

# === Configuration ===

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Defaults
BACKUP_CRON_HOUR="${BACKUP_CRON_HOUR:-2}"
BACKUP_CRON_MINUTE="${BACKUP_CRON_MINUTE:-0}"
ACTION="${1:-install}"

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

warn() {
    log "WARN: $*"
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# === Main ===

info "=== Kourai Backup Scheduler Setup ==="

case "$ACTION" in
    install)
        info "Setting up daily backups..."
        info "Backup will run every day at ${BACKUP_CRON_HOUR}:${BACKUP_CRON_MINUTE} UTC"
        
        # Check if crontab exists
        if ! command_exists crontab; then
            error "crontab not found. This system may not support scheduled tasks."
        fi
        
        # Create backup script cron line
        BACKUP_SCRIPT="$PROJECT_ROOT/scripts/backup_player_data.sh"
        CRON_LINE="$BACKUP_CRON_MINUTE $BACKUP_CRON_HOUR * * * source $PROJECT_ROOT/.env.backup 2>/dev/null; $BACKUP_SCRIPT >> $PROJECT_ROOT/logs/backups/cron.log 2>&1"
        
        # Safety: backup existing crontab
        CRONTAB_BACKUP="/tmp/crontab.backup.$(date +%Y%m%d_%H%M%S)"
        if crontab -l > "$CRONTAB_BACKUP" 2>/dev/null; then
            info "Existing crontab backed up to: $CRONTAB_BACKUP"
        else
            info "No existing crontab found (will create new one)"
            touch "$CRONTAB_BACKUP"
        fi
        
        # Check if backup job already exists
        if crontab -l 2>/dev/null | grep -q "backup_player_data.sh"; then
            warn "Backup cron job already installed"
            info "To remove it, run: bash scripts/setup-cron.sh uninstall"
            exit 0
        fi
        
        # Install cron job
        (
            crontab -l 2>/dev/null || true
            echo ""
            echo "# Kourai daily backup (added $(date '+%Y-%m-%d'))"
            echo "$CRON_LINE"
        ) | crontab -
        
        info "✅ Cron job installed successfully"
        info "Schedule: Every day at ${BACKUP_CRON_HOUR}:${BACKUP_CRON_MINUTE} UTC"
        info "Backup location: $BACKUP_SCRIPT"
        info "Logs: $PROJECT_ROOT/logs/backups/"
        info ""
        info "To verify:"
        info "  crontab -l"
        info ""
        info "To uninstall:"
        info "  bash scripts/setup-cron.sh uninstall"
        ;;
    
    uninstall)
        info "Removing backup cron job..."
        
        if ! command_exists crontab; then
            error "crontab not found"
        fi
        
        # Check if job exists
        if ! crontab -l 2>/dev/null | grep -q "backup_player_data.sh"; then
            warn "Backup cron job not found"
            exit 0
        fi
        
        # Remove the backup cron line
        (
            crontab -l 2>/dev/null | grep -v "backup_player_data.sh" || true
        ) | crontab -
        
        info "✅ Cron job removed successfully"
        info "To reinstall, run: bash scripts/setup-cron.sh install"
        ;;
    
    status)
        info "Checking backup cron job status..."
        
        if ! command_exists crontab; then
            warn "crontab not available"
            exit 0
        fi
        
        if crontab -l 2>/dev/null | grep -q "backup_player_data.sh"; then
            info "✅ Backup cron job is installed"
            info ""
            info "Current cron jobs:"
            crontab -l | grep "backup_player_data.sh" || true
        else
            info "❌ Backup cron job is NOT installed"
            info "Install it with: bash scripts/setup-cron.sh install"
        fi
        ;;
    
    *)
        error "Unknown action: $ACTION. Use 'install', 'uninstall', or 'status'"
        ;;
esac

exit 0
