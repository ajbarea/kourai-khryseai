#!/bin/bash
# Common utilities for Kourai Khryseai

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

setup_unicode_env() {
    export PYTHONIOENCODING="utf-8"
}
