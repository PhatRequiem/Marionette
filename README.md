# Marionette

Local terminal chat with Qwen3.5 4B using a small Python terminal client and llama.cpp’s `llama-server`. Runs in the foreground with a local HTTP server owned by the client, no persistent background service, account, or personality file. Each launch opens two live log terminals (connections/requests and model processing) and saves dated chat and diagnostic text files locally. Previous logs are not loaded as memory.

## Quick start

Follow [STARTUP.md](STARTUP.md) to launch her in the terminal and optionally connect Discord. It lists the steps in order and explains how to stop each part.

For a new installation, see [local setup](docs/setup.md). Setup downloads and verifies the pinned runtime and model; subsequent terminal chat runs are offline.

Optional phone access: [Discord DM setup](docs/discord.md). Launch her first, then optionally attach Discord to the same conversation in a fourth terminal. It allows only your configured user ID, sends only final answers to Discord, and displays the full exchange (including reasoning) in main chat and local logs. Discord requires an account and internet access; the terminal mode remains offline.

## Status and architecture

The current base runs Qwen3.5-4B BF16 on the RX 7900 XT with Vulkan, a 65,536-token context, and thinking enabled (white reasoning, pink answers). The client streams replies and prepares context rollover between turns. It supplies no setup report or personality instructions. Its loopback server stops when chat exits.

See [context policy and verified behavior](docs/context.md) for allowances, trimming, cache preparation, and limitations. See the [current baseline and verification](docs/baseline.md) and [log guide](docs/logs.md). Historical experiments live under `docs/experiments/`.

## Reviewing the code

Start with these files, in order:

| File | Responsibility |
|---|---|
| [chat.sh](scripts/native-linux/chat.sh) | Launch options, private session files, recorder, and two log windows |
| [session.py](src/marionette/session.py) | Server lifetime, terminal input, streaming replies, token budgets, and rollover preparation |
| [connection.py](src/marionette/connection.py) | Private local connection to the shared conversation |
| [discord.sh](scripts/native-linux/discord.sh) | Attach Discord to the running chat and display its connection log |
| [discord_bot.py](src/marionette/discord_bot.py) | Optional owner-only DM transport, sequential delivery, and local transcript |
| [style.py](src/marionette/style.py) and [log_view.py](src/marionette/log_view.py) | Shared colors and human-readable log views |
| [log_router.py](src/marionette/log_router.py) | Diagnostic classification, timestamps, shared event numbers, and readable formatting |
| [view-log.sh](scripts/native-linux/view-log.sh) | Follow a saved log until the chat ends |
| [setup.py](scripts/native-linux/setup.py) and [downloads.json](scripts/native-linux/downloads.json) | Install and verify the pinned runtime and model |
| [setup-discord.sh](scripts/native-linux/setup-discord.sh) | Install pinned Discord dependencies and create the local credential template if missing |
| [tests/core](tests/core) | Core regression checks using synthetic data; no personal conversations or model downloads |
| [tests/discord](tests/discord) | Optional Discord transport checks using mocked delivery |

In `session.py`, `run()` owns the server, `Conversation` owns shared history and serializes turns, `terminal()` handles input and `chat()` connects optional transports, `fit_history()` checks actual requests, and `Preparation` prepares shortened history between turns. `API` handles loopback requests. For diagnostic flow and test commands, see [operation and verification](docs/setup.md).

## Folder map

- `STARTUP.md`: step-by-step launch and stop guide, with optional features clearly marked.
- `src/marionette/`: application code—terminal chat, optional Discord DMs, rollover, and diagnostic log processing.
- `scripts/native-linux/`: installation, terminal/Discord launchers, log-window launcher, and pinned dependency manifests.
- `docs/`: setup requirements, operation, and decisions.
- `docs/licenses.md`: active dependency versions and licenses.
- `runtime/llama.cpp/`: downloaded runtime and bundled licenses; ignored by Git.
- `data/conversations/`: dated chat transcripts, server/model diagnostics, and optional Discord logs; ignored by Git.
- `data/session/`: private socket for optional connections to the running chat; ignored by Git.
- `data/discord/`: private bot credentials and connection/setup locks; ignored by Git.
- `runtime/discord/`: isolated optional Discord Python environment; ignored by Git.
- `tests/discord/`: optional Discord transport tests—owner filtering, delivery, attachment to main chat, and reasoning isolation.
- `data/models/`: local model weights; ignored by Git.
- `data/downloads/`: verified runtime archive; ignored by Git.
- `visual design/`: local visual references, independent of terminal chat; currently untracked.
- `tests/core/`: core application tests—setup, chat, shared connection, rollover, logging, and lifecycle.

See [native Linux setup and operation](docs/setup.md) and [licenses](docs/licenses.md).
