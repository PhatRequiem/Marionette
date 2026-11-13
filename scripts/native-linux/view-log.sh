#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
MODE=diagnostic
case "${3:-}" in
    server) title='Connections and requests' ;;
    model) title='Model processing' ;;
    reasoning) title='Reasoning'; MODE=reasoning ;;
    *) echo 'Usage: view-log.sh DATABASE SESSION_ID server|model|reasoning' >&2; exit 1 ;;
esac
OWNER=()
if [[ -n "${4:-}" ]]; then OWNER=(--owner-pid "$4"); fi
printf 'Marionette — %s\nLive RAM / saved database: %s\n\n' "$title" "$1"
python -u "$ROOT/src/marionette/storage.py" "$1" view "$2" "$3" --follow "${OWNER[@]}" | python -u "$ROOT/src/marionette/log_view.py" "$MODE"
printf '\nChat ended. Saved records remain in the database. Press Enter to close.\n'
read -r _ || true
