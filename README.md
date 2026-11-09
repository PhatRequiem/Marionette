# Marionette

Local terminal chat with Qwen3.5 4B using a small Python terminal client and llama.cpp’s `llama-server`. Runs in the foreground with a local HTTP server owned by the client, no persistent background service, account, or personality file. Each launch opens two live log terminals (connections/requests and model processing) and saves dated chat and diagnostic text files and a generated setup snapshot locally. Previous logs are not loaded as memory.

## Quick start

From this checkout on x86_64 Linux:

```bash
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

Setup downloads and verifies the pinned runtime and model. Subsequent chat runs are offline. See the short [terminal chat guide](docs/native-linux/chat.md) for everyday launch and exit commands.

## Status and architecture

Verified on an AMD Radeon RX 7900 XT with Vulkan: model download checksums, repeat setup, and a generated offline response. The client starts the Q4_K_M model with an 8,192-token context and reasoning disabled. It counts the formatted prompt before each reply, reserves 512 tokens for the response, and removes the oldest complete exchanges when needed. The generated setup report stays in every request as a system message. The server listens on `127.0.0.1` at a temporary port and stops when the client exits.

Baseline 1 is preserved at Git tag `baseline-v1`. The current version uses automatic context rollover and [generated startup context](docs/native-linux/startup-context.md). See [baseline scope, checks, and limitations](docs/native-linux/baseline.md) before adding features.

## Folder map

- `scripts/native-linux/`: setup, terminal client, logging, launch, and pinned download manifest.
- `docs/native-linux/`: setup requirements, operation, and decisions.
- `docs/licenses.md`: active dependency versions and licenses.
- `runtime/llama.cpp/`: downloaded runtime and bundled licenses; ignored by Git.
- `data/conversations/`: dated chat transcripts, server/model diagnostic logs, and setup snapshots; ignored by Git.
- `data/models/`: local model weights; ignored by Git.
- `data/downloads/`: verified runtime archive; ignored by Git.
- `visual design/`: existing visual references, independent of terminal chat.
- `scripts/visual-design/`: optional, local Blender character-render experiment.
- `docs/visual-design/experiments/`: visual experiment methods and limitations.
- `data/visual-design/`: generated Blender scenes and renders; ignored by Git.
- `tests/native-linux/`: isolated setup and logging regression checks.
- `src/`, `public/`: existing scaffolding; unused by this setup.

See [native Linux setup and operation](docs/native-linux/setup.md) and [licenses](docs/licenses.md).

The optional [porcelain marionette render experiment](docs/visual-design/experiments/porcelain-marionette.md) interprets the character sheet as editable Blender geometry.
