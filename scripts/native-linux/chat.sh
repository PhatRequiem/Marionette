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
# The post-load report is delivered with the first interactive message.
for arg in "$@"; do
    case "${arg%%=*}" in
        --server-base|-p|--prompt|-f|--file|-sys|--system-prompt|-sysf|--system-prompt-file|--no-conversation|-no-cnv|--no-jinja|--log-disable|--log-file|--prompt-cache|--prompt-cache-all|--prompt-cache-ro)
            echo "This launcher requires a fresh interactive session; unsupported override: ${arg%%=*}" >&2
            exit 1 ;;
    esac
done
for tool in script xdg-terminal-exec tail mktemp date mkdir bash; do
    command -v "$tool" >/dev/null || { echo "Missing required command: $tool" >&2; exit 1; }
done

# Private, unique transcripts; an override keeps synthetic tests out of real logs.
umask 077
LOG_DIR="${MARIONETTE_LOG_DIR:-$ROOT/data/conversations}"
mkdir -p -- "$LOG_DIR"
LOG_DIR="$(cd -- "$LOG_DIR" && pwd)"
CHAT_FILE="$(mktemp "$LOG_DIR/$(date +%Y-%m-%d_%H-%M-%S)_XXXXXX-chat.txt")"
SERVER_FILE="${CHAT_FILE%-chat.txt}-server.txt"
MODEL_FILE="${CHAT_FILE%-chat.txt}-model.txt"
(set -o noclobber; : > "$SERVER_FILE"; : > "$MODEL_FILE")
# One writer assigns event IDs before routing; no raw debug file is created.
exec 3> >(python "$ROOT/scripts/native-linux/log-router.py" "$SERVER_FILE" "$MODEL_FILE")
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
    exit "$status"
}
trap finish EXIT
COMMAND=("$CLI" --model "$MODEL" --offline --device "${MARIONETTE_DEVICE:-Vulkan0}"
    --gpu-layers all --ctx-size 8192 --jinja --reasoning off
    "$@"
    --simple-io --log-colors off --no-log-jsonl --verbose --log-prefix --log-timestamps)
{
    printf 'Session started: %s\n' "$(date --iso-8601=seconds)"
    printf 'Chat file: %s\nServer log: %s\nModel log: %s\n' "$CHAT_FILE" "$SERVER_FILE" "$MODEL_FILE"
    printf 'Command:'; printf ' %q' "${COMMAND[@]}"; printf '\n'
    export MARIONETTE_RUNTIME_VERSION="$("$CLI" --version 2>&1)"
    printf '%s\n' "$MARIONETTE_RUNTIME_VERSION"
    script --version
} >&3 2>&1
printf 'Conversation log: %s\nConnections and requests: %s\nModel processing: %s\n' "$CHAT_FILE" "$SERVER_FILE" "$MODEL_FILE"
printf 'Setup report: %s (generated after model loading)\n' "${CHAT_FILE%-chat.txt}-setup.json"
printf 'To exit, type /exit or press Ctrl+D at an empty prompt. Use /clear for a fresh conversation.\n'

# Each viewer reads its saved log; neither owns the diagnostic writer.
for view in server model; do
    case "$view" in
        server) title='Marionette — Connections and requests'; log_file="$SERVER_FILE" ;;
        model) title='Marionette — Model processing'; log_file="$MODEL_FILE" ;;
    esac
    (
        exec 3>&-
        if ! xdg-terminal-exec --title="$title" -- \
            bash "$ROOT/scripts/native-linux/view-log.sh" "$log_file" "$$" "$view"; then
            warning="Debug window could not open or exited with an error ($view). Logs are still saved: $MODEL_FILE"
            printf '%s\n' "$warning" >&2
        fi
    ) &
done

# Record terminal output (including echoed messages), not raw keystrokes.
# Keep the launcher as parent of the separate viewer, not the recorder.
# The coordinator keeps runtime diagnostics separate and supplies verified startup context.
printf -v RECORD_COMMAND '%q ' python -u "$ROOT/scripts/native-linux/session.py" \
    "$MODEL_FILE" "${COMMAND[@]}"
RECORD_COMMAND+=' 2>&3 3>&-'
SHELL=/bin/bash script --quiet --flush --return --echo always \
    --command "$RECORD_COMMAND" "$CHAT_FILE" 2>&3
