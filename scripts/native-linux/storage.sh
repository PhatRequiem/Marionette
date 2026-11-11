#!/usr/bin/env bash
# Operator-only database views, export, and backup; never a model tool.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
exec python "$ROOT/src/marionette/storage.py" "${MARIONETTE_LOG_DIR:-$ROOT/data/conversations}/marionette.sqlite3" "$@"
