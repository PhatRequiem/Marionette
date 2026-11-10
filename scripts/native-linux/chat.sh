#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
command -v python >/dev/null || { echo 'Python 3.11+ is required; see the setup guide.' >&2; exit 1; }
mapfile -t PATHS < <(python - "$ROOT" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
manifest = json.loads((root / 'scripts/native-linux/downloads.json').read_text())
runtime = manifest['runtime']
print(root / 'runtime/llama.cpp' / runtime['version'] / runtime['executable'])
print(root / 'data/models' / manifest['model']['filename'])
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
for source in commands.py inference.py context.py conversation.py terminal.py diagnostics.py permissions.py identity.py session.py log_router.py connection.py style.py log_view.py; do
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
REQUIRED=(mktemp date mkdir chmod bash flock script xdg-terminal-exec tail)
for tool in "${REQUIRED[@]}"; do
    command -v "$tool" >/dev/null || { echo "Missing required command: $tool" >&2; exit 1; }
done

# Private, unique transcripts; an override keeps synthetic tests out of real logs.
umask 077
exec 9>"$ROOT/data/.chat.lock"
flock -n 9 || { echo 'A chat is already running. Stop it before starting another.' >&2; exit 1; }
LOG_DIR="${MARIONETTE_LOG_DIR:-$ROOT/data/conversations}"
mkdir -p -- "$LOG_DIR"
LOG_DIR="$(cd -- "$LOG_DIR" && pwd)"
CHAT_FILE="$(mktemp "$LOG_DIR/$(date +%Y-%m-%d_%H-%M-%S)_XXXXXX-chat.txt")"
SERVER_FILE="${CHAT_FILE%-chat.txt}-server.txt"
MODEL_FILE="${CHAT_FILE%-chat.txt}-model.txt"
(set -o noclobber; : > "$SERVER_FILE"; : > "$MODEL_FILE")
# One writer assigns event IDs before routing; no raw debug file is created.
exec 3> >(python "$ROOT/src/marionette/log_router.py" "$SERVER_FILE" "$MODEL_FILE")
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
        printf 'Chat exited with status %s. Details: %s\n' "$status" "$MODEL_FILE" >&2
    fi
    trap - EXIT
    if [[ -t 1 && "${TERM:-}" != dumb ]]; then printf '\033[0m'; fi
    exit "$status"
}
trap finish EXIT
COMMAND=("$CLI" --model "$MODEL" --offline --device "${MARIONETTE_DEVICE:-Vulkan0}"
    --gpu-layers all --ctx-size 65536 --jinja --reasoning on --reasoning-format deepseek --reasoning-budget -1
    --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 1.5 --repeat-penalty 1.0 --repeat-last-n 65536
    "$@"
    --host 127.0.0.1 --port 0 --parallel 1 --no-webui --no-context-shift
    --log-colors off --no-log-jsonl --verbose --log-prefix --log-timestamps)
{
    printf 'Session started: %s\n' "$(date --iso-8601=seconds)"
    printf 'Chat file: %s\nServer log: %s\nModel log: %s\n' "$CHAT_FILE" "$SERVER_FILE" "$MODEL_FILE"
    printf 'Command:'; printf ' %q' "${COMMAND[@]}"; printf '\n'
    "$CLI" --version
    script --version
} >&3 2>&1
if [[ -t 1 && "${TERM:-}" != dumb ]]; then printf '\033[97m'; fi
printf 'Conversation log: %s\nConnections and requests: %s\nModel processing: %s\n' "$CHAT_FILE" "$SERVER_FILE" "$MODEL_FILE"
printf 'To exit, type /exit or press Ctrl+D at an empty prompt. Use /clear for a fresh conversation.\n'
mkdir -p "$ROOT/data/session"
chmod 700 "$ROOT/data/session"
export MARIONETTE_SESSION_SOCKET="$ROOT/data/session/chat.sock"

# Each viewer reads its saved log; neither owns the diagnostic writer.
for view in server model; do
    case "$view" in
        server) title='Marionette — Connections and requests'; log_file="$SERVER_FILE" ;;
        model) title='Marionette — Model processing'; log_file="$MODEL_FILE" ;;
    esac
    (
        exec 3>&- 9>&-
        if ! xdg-terminal-exec --title="$title" -- \
            bash "$ROOT/scripts/native-linux/view-log.sh" "$log_file" "$$" "$view"; then
            warning="Debug window could not open or exited with an error ($view). Logs are still saved: $log_file"
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
    --command "$RECORD_COMMAND" "$CHAT_FILE" 2>&3
