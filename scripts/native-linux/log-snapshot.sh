#!/usr/bin/env bash
# Read-only, on-demand diagnostic snapshot; not attached to the model.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
exec python "$ROOT/src/marionette/log_snapshot.py" "$@"
