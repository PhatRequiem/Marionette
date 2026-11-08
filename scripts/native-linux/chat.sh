#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
CLI="$ROOT/runtime/llama.cpp/b12211/llama-b12211/llama-cli"
MODEL="$ROOT/data/models/Qwen3.5-4B-Q4_K_M.gguf"
if [[ ! -x "$CLI" || ! -f "$MODEL" ]]; then
    echo 'Run python scripts/native-linux/setup.py first.' >&2
    exit 1
fi
# exec keeps inference in the foreground; no daemon or custom system prompt.
exec "$CLI" --model "$MODEL" --offline --device "${MARIONETTE_DEVICE:-Vulkan0}" \
    --gpu-layers all --ctx-size 8192 --reasoning off "$@"
