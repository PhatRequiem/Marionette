# Marionette

Local terminal chat with Qwen3.5 4B using llama.cpp. Runs in the foreground with no background service, account, or personality file. Replies stream directly into the terminal; conversations are not saved.

## Quick start

From this checkout on x86_64 Linux:

```bash
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

Setup downloads and verifies the pinned runtime and model. Subsequent chat runs are offline. See the short [terminal chat guide](docs/native-linux/chat.md) for everyday launch and exit commands.

## Status and architecture

Verified on an AMD Radeon RX 7900 XT with Vulkan: model download checksums, repeat setup, and a generated offline response. The launcher executes `llama-cli` directly, loading the Q4_K_M model with an 8,192-token context and reasoning disabled. No custom system prompt is supplied.

## Folder map

- `scripts/native-linux/`: setup, launch, and pinned download manifest.
- `docs/native-linux/`: setup requirements, operation, and decisions.
- `docs/licenses.md`: active dependency versions and licenses.
- `runtime/llama.cpp/`: downloaded runtime and bundled licenses; ignored by Git.
- `data/models/`: local model weights; ignored by Git.
- `data/downloads/`: verified runtime archive; ignored by Git.
- `visual design/`: existing visual references, independent of terminal chat.
- `src/`, `public/`, `tests/`, `model/`: existing scaffolding; unused by this setup. `model/` is ignored to protect weights.

See [native Linux setup and operation](docs/native-linux/setup.md) and [licenses](docs/licenses.md).
