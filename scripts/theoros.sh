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
SKILL_CONTEXT="${THEOROS_SKILL_CONTEXT_OVERRIDE:-$REPO_ROOT/.claude/skill-context.md}"

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

# Run prerequisite commands listed under `prerequisites:` in the YAML block.
# Each item is { command: <shell command>, message: <user-facing string> }.
# Aborts on first failure with the matching message.
run_prerequisites() {
    local yaml
    yaml="$(extract_theoros_yaml)"
    echo "$yaml" | grep -q '^prerequisites:' || return 0

    local in_section=0
    local current_cmd=""
    local current_msg=""

    while IFS= read -r line; do
        if [[ "$line" =~ ^prerequisites:[[:space:]]*$ ]]; then
            in_section=1
            continue
        fi
        if (( in_section == 0 )); then continue; fi
        # End of section: non-indented line that is not blank.
        if [[ "$line" =~ ^[a-zA-Z] ]]; then break; fi
        if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*command:[[:space:]]*(.*)$ ]]; then
            if [[ -n "$current_cmd" ]]; then
                _check_prerequisite "$current_cmd" "$current_msg"
            fi
            current_cmd="${BASH_REMATCH[1]}"
            current_msg=""
        elif [[ "$line" =~ ^[[:space:]]+message:[[:space:]]*\"(.*)\"[[:space:]]*$ ]]; then
            current_msg="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^[[:space:]]+message:[[:space:]]*(.*)$ ]]; then
            current_msg="${BASH_REMATCH[1]}"
        fi
    done <<< "$yaml"

    if [[ -n "$current_cmd" ]]; then
        _check_prerequisite "$current_cmd" "$current_msg"
    fi
}

_check_prerequisite() {
    local cmd="$1"
    local msg="$2"
    if ! eval "$cmd" >/dev/null 2>&1; then
        err "Prerequisite failed: $msg"
    fi
}

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
    local session repl ops sf
    session="$(get_session_name)"

    # Refuse if the session already exists.
    if tmux has-session -t "$session" 2>/dev/null; then
        local started_at="unknown"
        sf="$(state_file_path)"
        if [[ -f "$sf" ]]; then
            started_at="$(awk -F'"' '/"started_at"/ {print $4}' "$sf" | head -n1)"
        fi
        cat >&2 <<EOF
theoros session '$session' already running (started $started_at).
  Attach:     tmux attach -t $session -r
  Restart:    make theoros-down && make theoros
EOF
        exit 1
    fi

    # Run prerequisites before allocating any tmux state.
    run_prerequisites

    repl="${THEOROS_REPL_OVERRIDE:-$(get_repl_command)}"
    ops="${THEOROS_OPS_OVERRIDE:-$(get_ops_command)}"
    sf="$(state_file_path)"

    tmux new-session -d -s "$session" "$repl"

    local ops_pane_json="null"
    if [[ -n "$ops" ]]; then
        tmux split-window -t "${session}:0" -v -l 40%
        tmux send-keys -t "${session}:0.1" "$ops" Enter
        ops_pane_json="\"${session}:0.1\""
    fi

    local repl_pid driver_pane
    driver_pane="${session}:0.0"
    repl_pid="$(tmux list-panes -t "$driver_pane" -F '#{pane_pid}' | head -n1)"

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
  "ops_pane": $ops_pane_json
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
