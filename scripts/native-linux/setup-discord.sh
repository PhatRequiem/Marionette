#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
command -v uv >/dev/null || { echo 'Install uv first; see docs/discord.md.' >&2; exit 1; }
umask 077
mkdir -p "$ROOT/runtime/discord" "$ROOT/data/discord"
exec 9>"$ROOT/data/discord/.setup.lock"
flock -n 9 || { echo 'Discord setup is already running.' >&2; exit 1; }
if [[ ! -x "$ROOT/runtime/discord/bin/python" ]]; then
    uv venv --python python "$ROOT/runtime/discord"
fi
uv pip sync --python "$ROOT/runtime/discord/bin/python" --require-hashes "$ROOT/scripts/native-linux/discord-requirements.txt"
if [[ ! -f "$ROOT/data/discord/.env" ]]; then
    cp "$ROOT/.env.example" "$ROOT/data/discord/.env"
fi
chmod 600 "$ROOT/data/discord/.env"
printf 'Discord dependencies installed. Fill in data/discord/.env, then run ./scripts/native-linux/discord.sh\n'

# Storage uses Python's standard-library SQLite module, with no pip dependency.
"$ROOT/runtime/discord/bin/python" -c 'import sqlite3; print("SQLite available:", sqlite3.sqlite_version)'
