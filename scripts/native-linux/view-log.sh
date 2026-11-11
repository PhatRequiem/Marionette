#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
case "${3:-}" in
    server) title='Connections and requests' ;;
    model) title='Model processing' ;;
    *) echo 'Usage: view-log.sh DATABASE SESSION_ID server|model' >&2; exit 1 ;;
esac
OWNER=()
if [[ -n "${4:-}" ]]; then OWNER=(--owner-pid "$4"); fi
printf 'Marionette — %s\nSaved log: %s\n\n' "$title" "$1"
python -u "$ROOT/src/marionette/storage.py" "$1" view "$2" "$3" --follow "${OWNER[@]}" | python -u "$ROOT/src/marionette/log_view.py" diagnostic
printf '\nChat ended. This log is saved. Press Enter to close.\n'
read -r _ || true
