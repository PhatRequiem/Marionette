#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="$ROOT/runtime/discord/bin/python"
[[ -x "$PYTHON" ]] || { echo 'Run ./scripts/native-linux/setup-discord.sh first.' >&2; exit 1; }
[[ -S "$ROOT/data/session/chat.sock" ]] || { echo 'Launch her with ./scripts/native-linux/chat.sh first and wait until ready.' >&2; exit 1; }
"$PYTHON" "$ROOT/src/marionette/discord_bot.py" --check-config
if (( $# == 0 )); then
    exec xdg-terminal-exec --title='Marionette — Discord connection' -- bash "$0" --run
fi
[[ "$*" == --run ]] || { echo 'Usage: discord.sh' >&2; exit 1; }
umask 077
exec 9>"$ROOT/data/discord/.connection.lock"
flock -n 9 || { echo 'Discord is already connected.' >&2; exit 1; }
LOG_DIR="${MARIONETTE_LOG_DIR:-$ROOT/data/conversations}"
mkdir -p "$LOG_DIR"
LOG_FILE="$(mktemp "$LOG_DIR/$(date +%Y-%m-%d_%H-%M-%S)_XXXXXX-discord.txt")"
printf 'Discord log: %s\nCtrl+C disconnects Discord; main chat keeps running.\n' "$LOG_FILE"
"$PYTHON" -u "$ROOT/src/marionette/discord_bot.py" 2>&1 | tee -a "$LOG_FILE"
