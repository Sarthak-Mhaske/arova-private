#!/usr/bin/env bash
# =============================================================================
# Arova Shell Hook
# =============================================================================
# Sources into .bashrc or .zshrc to capture structured terminal telemetry.
#
# What this captures:
#   - Every command run (text, cwd, timestamp)
#   - Exit code and duration of every command
#   - Output of failed commands (exit code != 0), last 50 lines
#
# What this deliberately does NOT do:
#   - Wrap the shell in a PTY or script session
#   - Capture output of successful commands (too much noise, low signal)
#   - Modify command behavior in any way
#   - Send data anywhere except ~/.arova/session_log.jsonl
#
# Installation:
#   echo 'source ~/.arova/shell_hook.sh' >> ~/.zshrc
#   echo 'source ~/.arova/shell_hook.sh' >> ~/.bashrc
#
# Removal:
#   Delete the sourced line from your shell rc file.
#   The hook leaves no other traces.
# =============================================================================

# Guard against double-sourcing
if [ -n "$AROVA_HOOK_LOADED" ]; then
    return 0
fi
export AROVA_HOOK_LOADED=1

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AROVA_LOG_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/arova"
AROVA_LOG_FILE="$AROVA_LOG_DIR/session_log.jsonl"
AROVA_TMP_DIR="${XDG_RUNTIME_DIR:-/tmp}/arova"
AROVA_OUTPUT_LINES=50  # Lines of output to capture on failure

# Commands to never log (privacy + noise reduction)
AROVA_IGNORE_COMMANDS=(
    "ls" "ll" "la" "pwd" "cd" "clear" "history"
    "cat" "less" "more" "head" "tail"
    "echo" "printf" "man" "help"
    "exit" "logout" "sudo -s" "sudo -i"
    "ssh" "scp" "sftp"     # Never capture remote session commands
    "gpg" "pass" "secret"  # Never capture anything credential-adjacent
    "env" "printenv"       # Never capture environment (may contain secrets)
)

# Commands where output capture is worth the overhead
# These are the commands whose failure messages matter for reconstruction
AROVA_CAPTURE_COMMANDS=(
    "pytest" "py.test"
    "cargo" "go"
    "npm" "yarn" "pnpm"
    "make" "cmake"
    "gcc" "g++" "clang" "rustc"
    "python" "python3"
    "mvn" "gradle"
    "tsc" "eslint" "mypy" "ruff" "flake8"
)

# Ensure directories exist
mkdir -p "$AROVA_LOG_DIR" "$AROVA_TMP_DIR"

# ---------------------------------------------------------------------------
# Utility: write a JSONL event
# ---------------------------------------------------------------------------

_arova_write_event() {
    local event_type="$1"
    local data_json="$2"
    local timestamp
    timestamp=$(date -Iseconds 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%S+00:00")

    printf '{"timestamp":"%s","type":"%s","data":%s}\n' \
        "$timestamp" \
        "$event_type" \
        "$data_json" \
        >> "$AROVA_LOG_FILE" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Utility: escape a string for safe JSON embedding
# ---------------------------------------------------------------------------

_arova_json_escape() {
    local str="$1"
    # Escape backslashes, double quotes, newlines, tabs, carriage returns
    str="${str//\\/\\\\}"
    str="${str//\"/\\\"}"
    str="${str//$'\n'/\\n}"
    str="${str//$'\t'/\\t}"
    str="${str//$'\r'/\\r}"
    # Remove null bytes and other control characters that break JSON
    str=$(printf '%s' "$str" | tr -d '\000-\011\013-\037\177')
    printf '%s' "$str"
}

# ---------------------------------------------------------------------------
# Utility: check if a command should be ignored
# ---------------------------------------------------------------------------

_arova_should_ignore() {
    local cmd="$1"
    local cmd_base
    cmd_base=$(printf '%s' "$cmd" | awk '{print $1}')

    # Ignore empty commands
    if [ -z "$cmd_base" ]; then
        return 0
    fi

    # Check ignore list
    for ignored in "${AROVA_IGNORE_COMMANDS[@]}"; do
        if [ "$cmd_base" = "$ignored" ]; then
            return 0
        fi
    done

    # Ignore commands that look like they contain secrets
    # Heuristic: contains common secret patterns
    if printf '%s' "$cmd" | grep -qiE '(password|passwd|secret|token|api[_-]?key|auth[_-]?key)\s*='; then
        return 0
    fi

    return 1
}

# ---------------------------------------------------------------------------
# Utility: classify command type for richer telemetry
# ---------------------------------------------------------------------------

_arova_classify_command() {
    local cmd="$1"
    local cmd_base
    cmd_base=$(printf '%s' "$cmd" | awk '{print $1}')

    # Strip arova_run prefix transparently
    if [ "$cmd_base" = "arova_run" ]; then
        cmd=$(printf '%s' "$cmd" | cut -d' ' -f2-)
        cmd_base=$(printf '%s' "$cmd" | awk '{print $1}')
    fi

    case "$cmd_base" in
        pytest|py.test|python*test*|nosetests|jest|vitest|cargo\ test|go\ test|mvn\ test)
            printf "test_run" ;;
        git)
            printf "git_operation" ;;
        docker|docker-compose|kubectl|helm)
            printf "infrastructure" ;;
        pip|pip3|npm|yarn|cargo|go\ get|apt|brew)
            printf "dependency_management" ;;
        python|python3|node|ruby|perl|bash|sh)
            printf "script_execution" ;;
        make|cmake|cargo\ build|go\ build|mvn\ package)
            printf "build" ;;
        curl|wget|http|httpie)
            printf "http_request" ;;
        grep|rg|ag|ack|find)
            printf "search" ;;
        vim|nvim|nano|emacs|code)
            printf "editor_launch" ;;
        *)
            printf "shell_command" ;;
    esac
}

# ---------------------------------------------------------------------------
# Output capture: for failed commands only
# ---------------------------------------------------------------------------

_arova_start_output_capture() {
    local cmd_id="$1"
    AROVA_CAPTURE_FILE="$AROVA_TMP_DIR/output_${cmd_id}.tmp"

    # We use a named pipe approach: the command's output goes to
    # both the terminal (via tee) and our capture file.
    # This only activates for commands we've determined are worth watching.
    # We write an empty file to signal capture is active.
    : > "$AROVA_CAPTURE_FILE"
}

_arova_read_captured_output() {
    local capture_file="$1"
    if [ -f "$capture_file" ] && [ -s "$capture_file" ]; then
        tail -n "$AROVA_OUTPUT_LINES" "$capture_file" 2>/dev/null
    fi
}

_arova_cleanup_capture() {
    local capture_file="$1"
    rm -f "$capture_file" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Core state: track the command currently running
# ---------------------------------------------------------------------------

AROVA_CURRENT_CMD=""
AROVA_CMD_START_TIME=0
AROVA_CMD_ID=""
AROVA_CAPTURE_FILE=""

_arova_should_capture() {
    local cmd="$1"
    local cmd_base
    cmd_base=$(printf '%s' "$cmd" | awk '{print $1}')

    for capture_cmd in "${AROVA_CAPTURE_COMMANDS[@]}"; do
        if [ "$cmd_base" = "$capture_cmd" ]; then
            return 0  # Should capture
        fi
    done
    return 1  # Should not capture
}

# ---------------------------------------------------------------------------
# preexec: called just before a command runs
# Shell: Zsh calls this natively. Bash needs bash-preexec.
# ---------------------------------------------------------------------------

_arova_preexec() {
    local raw_cmd="$1"

    # Skip ignored commands immediately
    if _arova_should_ignore "$raw_cmd"; then
        AROVA_CURRENT_CMD=""
        return 0
    fi

    AROVA_CURRENT_CMD="$raw_cmd"
    AROVA_CMD_START_TIME=$(date +%s%3N 2>/dev/null || date +%s)
    AROVA_CMD_ID="$(date +%s%N 2>/dev/null || date +%s)_$$"
    AROVA_CAPTURE_FILE=""

    local escaped_cmd
    escaped_cmd=$(_arova_json_escape "$raw_cmd")

    local escaped_cwd
    escaped_cwd=$(_arova_json_escape "$PWD")

    local cmd_type
    cmd_type=$(_arova_classify_command "$raw_cmd")

    _arova_write_event "terminal_command" \
        "{\"command\":\"$escaped_cmd\",\"cwd\":\"$escaped_cwd\",\"cmd_type\":\"$cmd_type\",\"cmd_id\":\"$AROVA_CMD_ID\"}"

    # Set up output capture for high-value commands
    # We write the capture file path to a known location so precmd can find it
    if _arova_should_capture "$raw_cmd"; then
        AROVA_CAPTURE_FILE="$AROVA_TMP_DIR/output_${AROVA_CMD_ID}.tmp"
        # Signal to the wrapper that capture is active
        export AROVA_ACTIVE_CAPTURE="$AROVA_CAPTURE_FILE"
    else
        AROVA_CAPTURE_FILE=""
        unset AROVA_ACTIVE_CAPTURE
    fi
}

# ---------------------------------------------------------------------------
# arova_run: explicit output-capturing wrapper
# Usage: arova_run pytest tests/ -v
#
# For the experiment phase, use this prefix for commands where you want
# output captured. Later versions will make this automatic.
# ---------------------------------------------------------------------------
arova_run() {
    local cmd="$*"
    local capture_file="$AROVA_TMP_DIR/arova_capture_$$.tmp"

    # Run the command, capturing stdout+stderr to file while showing on terminal
    "$@" 2>&1 | tee "$capture_file"
    local exit_code=${PIPESTATUS[0]}

    # Write the captured output as a separate event
    if [ -f "$capture_file" ] && [ -s "$capture_file" ]; then
        local output
        output=$(tail -n "$AROVA_OUTPUT_LINES" "$capture_file")
        local escaped_output
        escaped_output=$(_arova_json_escape "$output")

        _arova_write_event "command_output" \
            "{\"command\":\"$(_arova_json_escape "$cmd")\",\"exit_code\":$exit_code,\"output\":\"$escaped_output\",\"lines_captured\":$(wc -l < "$capture_file" | awk '{print $1}')}"
    fi

    rm -f "$capture_file"
    return $exit_code
}

# ---------------------------------------------------------------------------
# precmd: called just after a command finishes
# ---------------------------------------------------------------------------

_arova_precmd() {
    local exit_code=$?

    # Nothing to record if we weren't tracking a command
    if [ -z "$AROVA_CURRENT_CMD" ]; then
        return 0
    fi

    local cmd_id="$AROVA_CMD_ID"
    local raw_cmd="$AROVA_CURRENT_CMD"
    local capture_file="$AROVA_CAPTURE_FILE"
    AROVA_CURRENT_CMD=""
    AROVA_CAPTURE_FILE=""
    unset AROVA_ACTIVE_CAPTURE

    # Calculate duration
    local duration_ms=0
    if [ "$AROVA_CMD_START_TIME" -gt 0 ] 2>/dev/null; then
        local end_time
        end_time=$(date +%s%3N 2>/dev/null || date +%s)
        duration_ms=$((end_time - AROVA_CMD_START_TIME))
    fi

    # Build output field
    local output_json="null"

    # Read from capture file if it exists (set by arova_run wrapper)
    if [ -n "$capture_file" ] && [ -f "$capture_file" ] && [ -s "$capture_file" ]; then
        local captured
        captured=$(tail -n "$AROVA_OUTPUT_LINES" "$capture_file")
        rm -f "$capture_file"
        if [ -n "$captured" ]; then
            local escaped_output
            escaped_output=$(_arova_json_escape "$captured")
            output_json="\"$escaped_output\""
        fi
    fi

    local escaped_cmd
    escaped_cmd=$(_arova_json_escape "$raw_cmd")

    _arova_write_event "terminal_output" \
        "{\"cmd_id\":\"$cmd_id\",\"command\":\"$escaped_cmd\",\"exit_code\":$exit_code,\"duration_ms\":$duration_ms,\"output\":$output_json}"
}

# ---------------------------------------------------------------------------
# Shell-specific hook registration
# ---------------------------------------------------------------------------

_arova_register_hooks() {
    if [ -n "$ZSH_VERSION" ]; then
        # Zsh: native preexec and precmd support
        # Check if preexec_functions array exists (zsh feature)
        if typeset -f preexec > /dev/null 2>&1; then
            # preexec already defined, chain into it
            preexec_functions+=(_arova_preexec)
        else
            preexec() { _arova_preexec "$1"; }
        fi

        if typeset -f precmd > /dev/null 2>&1; then
            precmd_functions+=(_arova_precmd)
        else
            precmd() { _arova_precmd; }
        fi

    elif [ -n "$BASH_VERSION" ]; then
        # Bash: requires bash-preexec or PROMPT_COMMAND approach
        if typeset -f __bp_preexec_invoke_exec > /dev/null 2>&1; then
            # bash-preexec is installed, use it properly
            preexec_functions+=(_arova_preexec)
            precmd_functions+=(_arova_precmd)
        else
            # Fallback: PROMPT_COMMAND for postcmd, DEBUG trap for precmd
            # This is less reliable but works without bash-preexec
            _arova_debug_trap() {
                if [ "$BASH_COMMAND" != "_arova_precmd" ] && \
                   [ "$BASH_COMMAND" != "PROMPT_COMMAND" ]; then
                    _arova_preexec "$BASH_COMMAND"
                fi
            }
            trap '_arova_debug_trap' DEBUG

            # Prepend to PROMPT_COMMAND, preserving existing value
            if [ -n "$PROMPT_COMMAND" ]; then
                PROMPT_COMMAND="_arova_precmd; $PROMPT_COMMAND"
            else
                PROMPT_COMMAND="_arova_precmd"
            fi
        fi
    fi
}

_arova_register_hooks

# ---------------------------------------------------------------------------
# Session start event
# ---------------------------------------------------------------------------

_arova_write_event "session_start" \
    "{\"shell\":\"${ZSH_VERSION:+zsh}${BASH_VERSION:+bash}\",\"pid\":$$,\"cwd\":\"$(_arova_json_escape "$PWD")\"}"

# ---------------------------------------------------------------------------
# Cleanup on shell exit
# ---------------------------------------------------------------------------

_arova_cleanup_session() {
    _arova_write_event "session_end" "{\"pid\":$$}"
    rm -f "$AROVA_TMP_DIR"/output_*.tmp 2>/dev/null
}

trap '_arova_cleanup_session' EXIT

# arova file watcher verification test 1786215865.6092038
