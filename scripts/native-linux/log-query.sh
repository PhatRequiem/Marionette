#!/usr/bin/env bash
# Operator CLI for the request handler also used by the registered query_logs tool.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
exec python "$ROOT/src/marionette/log_query.py" "$@"
