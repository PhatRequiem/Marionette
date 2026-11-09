#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
case "${3:-}" in
    server) title='Connections and requests' ;;
    model) title='Model processing' ;;
    *) echo 'Usage: view-log.sh LOG_FILE CHAT_PID server|model' >&2; exit 1 ;;
esac
printf 'Marionette — %s\nSaved log: %s\n\n' "$title" "$1"
tail --pid="$2" --sleep-interval=0.2 --lines=+1 --follow -- "$1" | python -u "$ROOT/src/marionette/log_view.py" diagnostic
printf '\nChat ended. This log is saved. Press Enter to close.\n'
read -r _ || true
