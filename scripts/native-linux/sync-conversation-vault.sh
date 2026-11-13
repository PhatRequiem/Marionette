#!/usr/bin/env bash
# On-demand private conversation mirror; no daemon or model tool.
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
exec python "$ROOT/src/marionette/conversation_vault.py" \
  "${MARIONETTE_LOG_DIR:-$ROOT/data/conversations}/marionette.sqlite3" \
  --profiles "$ROOT/data/contacts/profiles.json" \
  --contact-notes "$ROOT/data/contact_notes" \
  --docs "$ROOT/docs" "$@"
