#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
export MARIONETTE_MODE=discord
exec "$ROOT/scripts/native-linux/chat.sh" "$@"
