#!/usr/bin/env bash
# Standalone read-only preview; never starts or contacts the model.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
exec python "$ROOT/src/marionette/startup_snapshot.py" "$@"
