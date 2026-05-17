#!/bin/bash
##############################################################################
# theoros — observed live dev session
#
# Claude drives an interactive REPL in a named tmux session; you spectate via
# `tmux attach -r`. See techne:theoros skill and docs/theoros.md.
#
# Usage:
#   bash scripts/theoros.sh up      # start a session
#   bash scripts/theoros.sh down    # stop and clean up
#   bash scripts/theoros.sh status  # show current state (JSON or message)
#
# Configuration is read from the fenced `yaml` block inside the
# `## theoros` section of `.claude/skill-context.md`.
##############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SKILL_CONTEXT="$REPO_ROOT/.claude/skill-context.md"

# --- Logging ---

info()  { printf '%s\n' "$*"; }
err()   { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# --- YAML parsing ---

# Extract the YAML block content from the `## theoros` section.
# Outputs only the YAML body (no fences, no surrounding markdown).
extract_theoros_yaml() {
    [[ -f "$SKILL_CONTEXT" ]] || err "Skill context not found: $SKILL_CONTEXT"

    awk '
        /^## theoros($|[[:space:]])/ { in_section = 1; next }
        in_section && /^## / { in_section = 0 }
        in_section && /^```yaml[[:space:]]*$/ { in_yaml = 1; next }
        in_section && in_yaml && /^```[[:space:]]*$/ { exit }
        in_section && in_yaml { print }
    ' "$SKILL_CONTEXT"
}

# Get a single scalar field from the YAML block.
# Usage: yaml_get <key>
yaml_get() {
    local key="$1"
    extract_theoros_yaml | awk -v key="$key" '
        $0 ~ "^" key ":[[:space:]]" {
            sub("^" key ":[[:space:]]*", "")
            sub(/[[:space:]]+$/, "")
            print
            exit
        }
    '
}

get_session_name() {
    local name
    name="$(yaml_get session_name)"
    [[ -n "$name" ]] || err "Required field 'session_name' missing from '## theoros' YAML block in $SKILL_CONTEXT"
    printf '%s' "$name"
}

get_repl_command() {
    local cmd
    cmd="$(yaml_get repl_command)"
    [[ -n "$cmd" ]] || err "Required field 'repl_command' missing from '## theoros' YAML block in $SKILL_CONTEXT"
    printf '%s' "$cmd"
}

get_ops_command() {
    yaml_get ops_command || true
}

state_file_path() {
    local session
    session="$(get_session_name)"
    printf '/tmp/%s.state' "$session"
}

# --- Subcommands ---

cmd_status() {
    local sf
    sf="$(state_file_path)"
    if [[ -f "$sf" ]]; then
        cat "$sf"
    else
        info "No theoros session running."
    fi
}

cmd_up() {
    local session repl sf
    session="$(get_session_name)"
    repl="${THEOROS_REPL_OVERRIDE:-$(get_repl_command)}"
    sf="$(state_file_path)"

    # Create the tmux session detached.
    tmux new-session -d -s "$session" "$repl"

    # Capture REPL pane PID for the state file.
    local repl_pid driver_pane
    driver_pane="${session}:0.0"
    repl_pid="$(tmux list-panes -t "$driver_pane" -F '#{pane_pid}' | head -n1)"

    # Write the state file.
    local now
    now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    cat > "$sf" <<EOF
{
  "session": "$session",
  "started_at": "$now",
  "cwd": "$REPO_ROOT",
  "repl_pid": $repl_pid,
  "attach_cmd": "tmux attach -t $session -r",
  "driver_pane": "$driver_pane",
  "ops_pane": null
}
EOF

    info "theoros session ready."
    info "  Spectate:   tmux attach -t $session -r"
    info "  Take over:  tmux attach -t $session"
    info "  Tear down:  make theoros-down"
}

cmd_down() {
    local session sf
    session="$(get_session_name)"
    sf="$(state_file_path)"

    if tmux has-session -t "$session" 2>/dev/null; then
        tmux kill-session -t "$session"
    fi
    rm -f "$sf"
    info "theoros session '$session' stopped."
}

# --- Dispatch ---

# Only dispatch when run directly; allow sourcing for helper-level testing.
if [[ "${BASH_SOURCE[0]:-}" == "${0}" ]]; then
    case "${1:-}" in
        up)     cmd_up ;;
        down)   cmd_down ;;
        status) cmd_status ;;
        *)
            printf 'Usage: bash %s {up|down|status}\n' "$0" >&2
            exit 2
            ;;
    esac
fi
