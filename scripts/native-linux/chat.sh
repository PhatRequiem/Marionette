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
LOG_FILE="$(mktemp "$LOG_DIR/$(date +%Y-%m-%d_%H-%M-%S)_XXXXXX.txt")"
printf 'Conversation log: %s\n' "$LOG_FILE"

# The viewer may be closed independently. Recording stays with the chat process.
xdg-terminal-exec --title='Marionette log' -- \
    bash "$ROOT/scripts/native-linux/view-log.sh" "$LOG_FILE" "$$" &

# Record terminal output (including echoed messages), not raw keystrokes.
# Keep the launcher as parent of the separate viewer, not the recorder.
script --quiet --flush --return --echo always "$LOG_FILE" -- \
    "$CLI" --model "$MODEL" --offline --device "${MARIONETTE_DEVICE:-Vulkan0}" \
    --gpu-layers all --ctx-size 8192 --reasoning off "$@" --simple-io --log-colors off
