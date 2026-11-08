#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
CLI="$ROOT/runtime/llama.cpp/b12211/llama-b12211/llama-cli"
MODEL="$ROOT/data/models/Qwen3.5-4B-Q4_K_M.gguf"
if [[ ! -x "$CLI" || ! -f "$MODEL" ]]; then
    echo 'Run python scripts/native-linux/setup.py first.' >&2
    exit 1
fi
for tool in script xdg-terminal-exec tail mktemp; do
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
COMMAND=("$CLI" --model "$MODEL" --offline --device "${MARIONETTE_DEVICE:-Vulkan0}"
    --gpu-layers all --ctx-size 8192 --reasoning off "$@"
    --simple-io --log-colors off --no-log-jsonl --verbose --log-prefix --log-timestamps)
{
    printf 'Session started: %s\n' "$(date --iso-8601=seconds)"
    printf 'Chat file: %s\nDebug file: %s\n' "$CHAT_FILE" "$DEBUG_FILE"
    printf 'Command:'; printf ' %q' "${COMMAND[@]}"; printf '\n'
    "$CLI" --version
    script --version
} >> "$DEBUG_FILE" 2>&1
finish() {
    local status=$?
    printf '\nSession ended: %s\nExit status: %s\n' "$(date --iso-8601=seconds)" "$status" >> "$DEBUG_FILE"
    if (( status != 0 )); then
        printf 'Chat exited with status %s. Details: %s\n' "$status" "$DEBUG_FILE" >&2
    fi
}
trap finish EXIT
printf 'Conversation log: %s\nDebug log: %s\n' "$CHAT_FILE" "$DEBUG_FILE"

# The viewer may be closed independently. Recording stays with the chat process.
xdg-terminal-exec --title='Marionette debug log' -- \
    bash "$ROOT/scripts/native-linux/view-log.sh" "$DEBUG_FILE" "$$" 2>> "$DEBUG_FILE" &

# Record terminal output (including echoed messages), not raw keystrokes.
# Keep the launcher as parent of the separate viewer, not the recorder.
# Redirect inside the pseudo-terminal so diagnostics never enter the chat transcript.
printf -v RECORD_COMMAND '%q ' bash -c 'debug=$1; shift; exec "$@" 2>> "$debug"' \
    marionette-debug "$DEBUG_FILE" "${COMMAND[@]}"
SHELL=/bin/bash script --quiet --flush --return --echo always \
    --command "$RECORD_COMMAND" "$CHAT_FILE" 2>> "$DEBUG_FILE"
