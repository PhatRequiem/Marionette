#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
command -v uv >/dev/null || { echo 'Install uv first; see docs/setup.md.' >&2; exit 1; }
umask 077
mkdir -p "$ROOT/runtime/agent" "$ROOT/data"
exec 9>"$ROOT/data/.agent-setup.lock"
flock -n 9 || { echo 'Agent setup is already running.' >&2; exit 1; }
if [[ ! -x "$ROOT/runtime/agent/bin/python" ]]; then
    uv venv --python python "$ROOT/runtime/agent"
fi
uv pip sync --python "$ROOT/runtime/agent/bin/python" --require-hashes "$ROOT/scripts/native-linux/agent-requirements.txt"
printf 'Qwen-Agent installed. Start normally with ./scripts/native-linux/chat.sh\n'
