# Marionette

Local terminal chat with Qwen3.5 4B using llama.cpp’s `llama-cli`. Runs in the foreground with an embedded local HTTP server, no persistent background service, account, or personality file. Each launch opens a live debug terminal and saves dated chat/debug text files and a generated setup snapshot locally. Previous logs are not loaded as memory.

## Quick start

From this checkout on x86_64 Linux:

```bash
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

Setup downloads and verifies the pinned runtime and model. Subsequent chat runs are offline. See the short [terminal chat guide](docs/native-linux/chat.md) for everyday launch and exit commands.

## Status and architecture

Verified on an AMD Radeon RX 7900 XT with Vulkan: model download checksums, repeat setup, and a generated offline response. The launcher records the foreground `llama-cli` session, loading the Q4_K_M model with an 8,192-token context and reasoning disabled. A generated setup report supplies factual system context after model loading. A text-only Qwen formatting template closes the empty thinking block; the server listens on `127.0.0.1` at a temporary port and stops when the chat process exits.

Baseline 1 is preserved at Git tag `baseline-v1`. The current version uses local-server terminal chat and [generated startup context](docs/native-linux/startup-context.md). See [baseline scope, checks, and limitations](docs/native-linux/baseline.md) before adding features.

## Folder map

- `scripts/native-linux/`: setup, launch, and pinned download manifest.
- `docs/native-linux/`: setup requirements, operation, and decisions.
- `docs/licenses.md`: active dependency versions and licenses.
- `runtime/llama.cpp/`: downloaded runtime and bundled licenses; ignored by Git.
- `data/conversations/`: dated chat transcripts, full debug logs, and setup snapshots; ignored by Git.
- `data/models/`: local model weights; ignored by Git.
- `data/downloads/`: verified runtime archive; ignored by Git.
- `visual design/`: existing visual references, independent of terminal chat.
- `tests/native-linux/`: isolated setup and logging regression checks.
- `src/`, `public/`: existing scaffolding; unused by this setup.

See [native Linux setup and operation](docs/native-linux/setup.md) and [licenses](docs/licenses.md).
