#!/usr/bin/env bash
# On-demand private conversation mirror; no daemon or model tool.
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA="${MARIONETTE_DATA_DIR:-$ROOT/data}"
exec python "$ROOT/src/marionette/conversation_vault.py" \
  "${MARIONETTE_LOG_DIR:-$DATA/conversations}/marionette.sqlite3" \
  --profiles "$DATA/contacts/profiles.json" \
  --contact-notes "$DATA/contact_notes" \
  --docs "$ROOT/docs" "$@"
