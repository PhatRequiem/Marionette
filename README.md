# Marionette

Local terminal chat with Qwen3.5 4B using a small Python terminal client and llama.cpp’s `llama-server`. Runs in the foreground with a local HTTP server owned by the client, no persistent background service, account, or personality file. Each launch opens two live log terminals (connections/requests and model processing) and saves dated chat and diagnostic text files locally. Previous logs are not loaded as memory.

## Quick start

From this checkout on x86_64 Linux:

```bash
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

Setup downloads and verifies the pinned runtime and model. Subsequent chat runs are offline. See the short [terminal chat guide](docs/native-linux/chat.md) for everyday launch and exit commands.

## Status and architecture

The current base runs Qwen3.5-4B Q4_K_M on the RX 7900 XT with Vulkan, a 65,536-token context, and thinking enabled (white reasoning, pink answers). The client streams replies and prepares context rollover between turns. It supplies no setup report or personality instructions. Its loopback server stops when chat exits.

See [context policy and verified behavior](docs/native-linux/context.md) for allowances, trimming, cache preparation, and limitations. The older direct-inference checkpoint is documented separately at [Baseline 1](docs/native-linux/baseline.md) and Git tag `baseline-v1`.

## Reviewing the code

Start with these files, in order:

| File | Responsibility |
|---|---|
| [chat.sh](scripts/native-linux/chat.sh) | Launch options, private session files, recorder, and two log windows |
| [session.py](src/marionette/session.py) | Server lifetime, terminal input, streaming replies, token budgets, and rollover preparation |
| [log_router.py](src/marionette/log_router.py) | Diagnostic classification, timestamps, shared event numbers, and readable formatting |
| [view-log.sh](scripts/native-linux/view-log.sh) | Follow a saved log until the chat ends |
| [setup.py](scripts/native-linux/setup.py) and [downloads.json](scripts/native-linux/downloads.json) | Install and verify the pinned runtime and model |
| [tests/native-linux](tests/native-linux) | Synthetic regression checks; no personal conversations or model downloads |

In `session.py`, `run()` owns the server, `chat()` handles turns, `fit_history()` checks actual requests, and `Preparation` prepares shortened history between turns. `API` handles loopback requests. For diagnostic flow and test commands, see [operation and verification](docs/native-linux/setup.md).

## Folder map

- `src/marionette/`: application code—terminal chat, rollover, and diagnostic log processing.
- `scripts/native-linux/`: installation, chat launcher, log-window launcher, and pinned download manifest.
- `docs/native-linux/`: setup requirements, operation, and decisions.
- `docs/licenses.md`: active dependency versions and licenses.
- `runtime/llama.cpp/`: downloaded runtime and bundled licenses; ignored by Git.
- `data/conversations/`: dated chat transcripts and server/model diagnostic logs; ignored by Git.
- `data/models/`: local model weights; ignored by Git.
- `data/downloads/`: verified runtime archive; ignored by Git.
- `visual design/`: local visual references, independent of terminal chat; currently untracked.
- `tests/native-linux/`: isolated setup, chat, rollover, logging, and lifecycle checks.

See [native Linux setup and operation](docs/native-linux/setup.md) and [licenses](docs/licenses.md).
