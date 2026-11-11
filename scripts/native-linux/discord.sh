#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="$ROOT/runtime/discord/bin/python"
[[ -x "$PYTHON" ]] || { echo 'Run ./scripts/native-linux/setup-discord.sh first.' >&2; exit 1; }
[[ -S "$ROOT/data/session/chat.sock" ]] || { echo 'Launch her with ./scripts/native-linux/chat.sh first and wait until ready.' >&2; exit 1; }
"$PYTHON" "$ROOT/src/marionette/discord_bot.py" --check-config
(( $# == 0 )) || { echo 'Usage: discord.sh' >&2; exit 1; }
umask 077
exec 9>"$ROOT/data/discord/.connection.lock"
flock -n 9 || { echo 'Discord is already connected.' >&2; exit 1; }
# Use the main session's database, even when its log directory was overridden.
mapfile -t LOG_INFO < <("$PYTHON" - "$ROOT/data/session/log-session.json" <<'PYTHON'
import json, sys
from pathlib import Path
info = json.loads(Path(sys.argv[1]).read_text())
print(info['database'])
print(info['session'])
PYTHON
)
(( ${#LOG_INFO[@]} == 2 )) || { echo 'Cannot read main chat logging session.' >&2; exit 1; }
printf 'Discord logs: %s\nSession: %s\nCtrl+C disconnects Discord; main chat keeps running.\n' "${LOG_INFO[0]}" "${LOG_INFO[1]}"
# Ignore terminal Ctrl+C in the recorder/viewer so they drain the bot's final output.
"$PYTHON" -u "$ROOT/src/marionette/discord_bot.py" 2>&1 | \
    (trap '' INT; exec "$PYTHON" -u "$ROOT/src/marionette/storage.py" "${LOG_INFO[0]}" capture "${LOG_INFO[1]}" discord) | \
    (trap '' INT; exec "$PYTHON" -u "$ROOT/src/marionette/log_view.py" discord)
