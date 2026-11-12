#!/usr/bin/env bash
# Standalone snapshot; never starts or contacts the model.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
exec python "$ROOT/src/marionette/snapshot.py" "$@"
