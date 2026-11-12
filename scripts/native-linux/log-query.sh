#!/usr/bin/env bash
# Operator-only request form on stdin. No model registration.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
exec python "$ROOT/src/marionette/log_query.py" "$@"
