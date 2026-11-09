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
        -p|--prompt|-f|--file|-sys|--system-prompt|-sysf|--system-prompt-file|--no-conversation|-no-cnv|--no-jinja|--log-disable|--log-file|--prompt-cache|--prompt-cache-all|--prompt-cache-ro)
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
DEBUG_FILE="${CHAT_FILE%-chat.txt}-debug.txt"
(set -o noclobber; : > "$DEBUG_FILE")
finish() {
    local status=$?
    printf '\nSession ended: %s\nExit status: %s\n' "$(date --iso-8601=seconds)" "$status" >> "$DEBUG_FILE"
    if (( status != 0 )); then
        printf 'Chat exited with status %s. Details: %s\n' "$status" "$DEBUG_FILE" >&2
    fi
}
trap finish EXIT
COMMAND=("$CLI" --model "$MODEL" --offline --device "${MARIONETTE_DEVICE:-Vulkan0}"
    --gpu-layers all --ctx-size 8192 --conversation --jinja --reasoning off
    "$@"
    --simple-io --log-colors off --no-log-jsonl --verbose --log-prefix --log-timestamps)
{
    printf 'Session started: %s\n' "$(date --iso-8601=seconds)"
    printf 'Chat file: %s\nDebug file: %s\n' "$CHAT_FILE" "$DEBUG_FILE"
    printf 'Command:'; printf ' %q' "${COMMAND[@]}"; printf '\n'
    "$CLI" --version
    script --version
} >> "$DEBUG_FILE" 2>&1
printf 'Conversation log: %s\nDebug log: %s\n' "$CHAT_FILE" "$DEBUG_FILE"
printf 'Setup report: %s (generated after model loading)\n' "${CHAT_FILE%-chat.txt}-setup.json"
printf 'To exit, press Ctrl+D at an empty chat prompt. Restart for a fresh conversation.\n'

# The viewer may be closed independently. Recording stays with the chat process.
(
    if ! xdg-terminal-exec --title='Marionette debug log' -- \
        bash "$ROOT/scripts/native-linux/view-log.sh" "$DEBUG_FILE" "$$" 2>> "$DEBUG_FILE"; then
        warning="Debug window could not open or exited with an error. Logs are still saved: $DEBUG_FILE"
        printf '%s\n' "$warning" >&2
        printf '%s\n' "$warning" >> "$DEBUG_FILE"
    fi
) &

# Record terminal output (including echoed messages), not raw keystrokes.
# Keep the launcher as parent of the separate viewer, not the recorder.
# The coordinator keeps runtime diagnostics separate and supplies verified startup context.
printf -v RECORD_COMMAND '%q ' python "$ROOT/scripts/native-linux/session.py" \
    "$DEBUG_FILE" "${COMMAND[@]}"
SHELL=/bin/bash script --quiet --flush --return --echo always \
    --command "$RECORD_COMMAND" "$CHAT_FILE" 2>> "$DEBUG_FILE"
