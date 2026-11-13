#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA="${MARIONETTE_DATA_DIR:-$ROOT/data}"
command -v python >/dev/null || { echo 'Python 3.11+ is required; see the setup guide.' >&2; exit 1; }
mapfile -t PATHS < <(python - "$ROOT" <<'PY'
import json, os, sys
from pathlib import Path
root = Path(sys.argv[1])
manifest = json.loads((root / 'scripts/native-linux/downloads.json').read_text())
runtime = manifest['runtime']
apps_root = Path(os.environ.get('MARIONETTE_APPS_DIR') or Path.home() / 'AI Infrastructure' / 'AI Apps').expanduser().resolve()
print(apps_root / runtime['directory'] / runtime['version'] / runtime['executable'])
models_root = Path(os.environ.get('MARIONETTE_MODELS_DIR') or Path.home() / 'AI Infrastructure' / 'AI Local Models').expanduser().resolve()
print(models_root / manifest['model']['directory'] / manifest['model']['filename'])
PY
)
if (( ${#PATHS[@]} != 2 )); then
    echo 'Cannot read runtime/model paths from downloads.json.' >&2
    exit 1
fi
CLI="${PATHS[0]}"
MODEL="${PATHS[1]}"
if [[ ! -x "$CLI" || ! -f "$MODEL" ]]; then
    echo 'Run python scripts/native-linux/setup.py first.' >&2
    exit 1
fi
if (( $# == 1 )); then
    case "$1" in --help|--version|--list-devices) exec "$CLI" "$1" ;; esac
fi
for source in vault_tool.py conversation_vault.py conversation_refs.py log_tool.py log_query.py operator_status.py setup_datasheet.py log_metadata.py memory_reset.py reset_boundary.py data_migration.py storage.py retention.py ram_logs.py soul.py contact_notes.py coordination.py commands.py inference.py context.py conversation.py terminal.py diagnostics.py permissions.py contacts.py session.py log_router.py connection.py style.py log_view.py; do
    if [[ ! -f "$ROOT/src/marionette/$source" ]]; then
        echo "Application source missing: src/marionette/$source. Restore the complete checkout." >&2
        exit 1
    fi
done
AGENT_PYTHON="$ROOT/runtime/agent/bin/python"
if [[ ! -x "$AGENT_PYTHON" ]]; then
    echo 'Run ./scripts/native-linux/setup-agent.sh first.' >&2
    exit 1
fi
# The client owns server lifetime and structured messages.
for arg in "$@"; do
    case "${arg%%=*}" in
        --host|--port|--parallel|-np|--api-key|--api-key-file|--tools|--agent|-ag|--path|--chat-template|--chat-template-file|--server-base|-p|--prompt|-f|--file|-sys|--system-prompt|-sysf|--system-prompt-file|--no-conversation|-no-cnv|--no-jinja|--log-disable|--log-file|--prompt-cache|--prompt-cache-all|--prompt-cache-ro)
            echo "This launcher requires a fresh interactive session; unsupported override: ${arg%%=*}" >&2
            exit 1 ;;
    esac
done
REQUIRED=(date mkdir chmod bash flock script xdg-terminal-exec)
for tool in "${REQUIRED[@]}"; do
    command -v "$tool" >/dev/null || { echo "Missing required command: $tool" >&2; exit 1; }
done

# Private session records; an override keeps synthetic tests out of real logs.
umask 077
mkdir -p "$ROOT/data" "$DATA"
DATA="$(cd -- "$DATA" && pwd)"
export MARIONETTE_DATA_DIR="$DATA"
exec 9>"$ROOT/data/.chat.lock"
flock -n 9 || { echo 'A chat is already running. Stop it before starting another.' >&2; exit 1; }
LOG_DIR="${MARIONETTE_LOG_DIR:-$DATA/conversations}"
mkdir -p -- "$LOG_DIR"
LOG_DIR="$(cd -- "$LOG_DIR" && pwd)"
export MARIONETTE_LOG_DB="$LOG_DIR/marionette.sqlite3"
export MARIONETTE_LOG_SESSION
MARIONETTE_LOG_SESSION="$(python "$ROOT/src/marionette/storage.py" "$MARIONETTE_LOG_DB" start)"
# Existing recorder keeps routine diagnostics in RAM and saves the retained buffer at EOF.
exec 3> >(trap '' INT; python "$ROOT/src/marionette/storage.py" "$MARIONETTE_LOG_DB" capture "$MARIONETTE_LOG_SESSION" diagnostic)
ROUTER_PID=$!
finish() {
    local status=$?
    printf '\nSession ended: %s\nExit status: %s\n' "$(date --iso-8601=seconds)" "$status" >&3
    exec 3>&-
    if ! wait "$ROUTER_PID"; then
        echo 'Diagnostic log writer failed; saved logs may be incomplete.' >&2
        status=1
    fi
    if (( status != 0 )); then
        printf 'Chat exited with status %s. Details: %s\n' "$status" "$MARIONETTE_LOG_DB" >&2
    fi
    python "$ROOT/src/marionette/storage.py" "$MARIONETTE_LOG_DB" end "$MARIONETTE_LOG_SESSION" || status=1
    # Both main recorders have drained; publish the final saved conversation state.
    local data_root="$DATA"
    if python "$ROOT/src/marionette/conversation_vault.py" "$MARIONETTE_LOG_DB" \
        --profiles "$data_root/contacts/profiles.json" \
        --contact-notes "$data_root/contact_notes" --docs "$ROOT/docs" >/dev/null; then
        printf 'Conversation vault refreshed.\n'
    else
        echo 'Conversation vault refresh failed; saved SQLite records remain. Run sync-conversation-vault.sh to retry.' >&2
        status=1
    fi
    rm -f "$DATA/session/log-session.json"
    trap - EXIT
    if [[ -t 1 && "${TERM:-}" != dumb ]]; then printf '\033[0m'; fi
    exit "$status"
}
trap finish EXIT
COMMAND=("$CLI" --model "$MODEL" --offline --device "${MARIONETTE_DEVICE:-Vulkan0}"
    --cache-ram 5120
    --gpu-layers all --ctx-size 65536 --jinja --reasoning on --reasoning-format deepseek --reasoning-budget -1
    --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 1.5 --repeat-penalty 1.0 --repeat-last-n 65536
    "$@"
    --host 127.0.0.1 --port 0 --parallel 1 --no-webui --no-context-shift
    --log-colors off --no-log-jsonl --verbose --log-prefix --log-timestamps)
{
    printf 'Session started: %s\n' "$(date --iso-8601=seconds)"
    printf 'Database: %s\nSession: %s\n' "$MARIONETTE_LOG_DB" "$MARIONETTE_LOG_SESSION"
    printf 'Command:'; printf ' %q' "${COMMAND[@]}"; printf '\n'
    MARIONETTE_RUNTIME_VERSION_OBSERVATION="$("$CLI" --version 2>&1)"
    export MARIONETTE_RUNTIME_VERSION_OBSERVATION
    printf '%s\n' "$MARIONETTE_RUNTIME_VERSION_OBSERVATION"
    script --version
} >&3 2>&1
if [[ -t 1 && "${TERM:-}" != dumb ]]; then printf '\033[97m'; fi
printf 'Conversation and diagnostic database: %s\nSession: %s\n' "$MARIONETTE_LOG_DB" "$MARIONETTE_LOG_SESSION"
printf 'Diagnostics: 500 MB rolling RAM buffer; saved on orderly shutdown.\n'
printf 'To exit, type /exit or press Ctrl+D at an empty prompt. Use /clear for a fresh conversation.\n'
mkdir -p "$DATA/session"
chmod 700 "$DATA/session"
export MARIONETTE_SESSION_SOCKET="$DATA/session/chat.sock"
python - "$DATA/session/log-session.json" <<'PYTHON'
import json, os, sys, sqlite3
from pathlib import Path
with sqlite3.connect(os.environ['MARIONETTE_LOG_DB']) as database:
    generation = database.execute('SELECT generation FROM memory_epoch').fetchone()[0]
Path(sys.argv[1]).write_text(json.dumps({'database': os.environ['MARIONETTE_LOG_DB'], 'session': os.environ['MARIONETTE_LOG_SESSION'], 'generation': generation}))
PYTHON

# Viewers read the existing recorder RAM socket, falling back to saved rows after exit.
for view in server model; do
    case "$view" in
        server) title='Marionette — Connections and requests' ;;
        model) title='Marionette — Model processing' ;;
    esac
    (
        exec 3>&- 9>&-
        if ! xdg-terminal-exec --title="$title" -- \
            bash "$ROOT/scripts/native-linux/view-log.sh" "$MARIONETTE_LOG_DB" "$MARIONETTE_LOG_SESSION" "$view" "$$"; then
            warning="Debug window could not open or exited with an error ($view). Recording continues in RAM; shutdown destination: $MARIONETTE_LOG_DB"
            printf '%s\n' "$warning" >&2
        fi
    ) &
done

# Record terminal output (including echoed messages), not raw keystrokes.
# Keep the launcher as parent of the separate viewer, not the recorder.
# The coordinator keeps runtime diagnostics separate and prepares rollover between turns.
printf -v RECORD_COMMAND '%q ' "$AGENT_PYTHON" -u "$ROOT/src/marionette/session.py" \
    "${COMMAND[@]}"
RECORD_COMMAND+=' 2>&3 3>&-'
SHELL=/bin/bash script --quiet --flush --return --echo always \
    --command "$RECORD_COMMAND" /dev/null 2>&3 | \
    (trap '' INT; exec python "$ROOT/src/marionette/storage.py" "$MARIONETTE_LOG_DB" capture "$MARIONETTE_LOG_SESSION" terminal)
