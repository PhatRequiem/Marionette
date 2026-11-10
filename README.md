# Marionette

Local terminal chat with Qwen3.5 4B using a small Python terminal client and llama.cpp’s `llama-server`. Runs in the foreground with a local HTTP server owned by the client, no persistent background service, account, or personality file. Each launch opens two live log terminals (connections/requests and model processing) and saves dated chat and diagnostic text files locally. Previous logs are not loaded as memory.

## Quick start

Follow [STARTUP.md](STARTUP.md) to launch her in the terminal and optionally connect Discord. It lists the steps in order and explains how to stop each part.

For a new installation, see [local setup](docs/setup.md). Setup downloads and verifies the pinned runtime and model; subsequent terminal chat runs are offline.

Optional phone access: [Discord DM setup](docs/discord.md). Launch her first, then optionally attach Discord to the same conversation in a fourth terminal. It allows only your configured user ID, sends only final answers to Discord, and displays the full exchange (including reasoning) in main chat and local logs. Discord requires an account and internet access; the terminal mode remains offline.

## Status and architecture

The current base runs Qwen3.5-4B Q4_K_M on the RX 7900 XT with Vulkan, a 65,536-token context, and thinking enabled (white reasoning, pink answers). Qwen-Agent streams model reasoning and answers through our client; the client still owns conversation history and rollover. See [Qwen-Agent integration](docs/qwen-agent.md). It supplies no setup report or personality instructions. Its loopback server stops when chat exits.

Q4 is selected for faster infrastructure testing; BF16 is retained locally in `data/models/archive/`. See [Q4 return verification](docs/experiments/q4-return.md).

The **last saved stable baseline** is **`baseline-v3` (2026-11-09)**: a deliberately saved, simple working foundation to return to if later development becomes cluttered or unreliable. It records the program at that checkpoint, not the current setup. Later changes are not automatically included; a new baseline requires a deliberate decision and a new tag. Recovery steps are in [the baseline guide](docs/baseline.md).

See [context policy and verified behavior](docs/context.md) for allowances, trimming, cache preparation, and limitations. See the [last saved stable baseline and its verification](docs/baseline.md) and [log guide](docs/logs.md). Historical experiments live under `docs/experiments/`.

Terminal profiles and linked Discord accounts now use permanent person UUIDs; see [identities](docs/identity.md). Profiles, owner command permissions, the module organization, and Q4 are included in `baseline-v3`; the previous V2 guide is [archived](docs/archive/baseline-v2-2026-11-09.md). Conversation history is still shared.

## Reviewing the code

Start with these files, in order:

| File | Responsibility |
|---|---|
| [chat.sh](scripts/native-linux/chat.sh) | Launch options, private session files, recorder, and two log windows |
| [session.py](src/marionette/session.py) | Component startup, server lifetime, readiness, and shutdown |
| [terminal.py](src/marionette/terminal.py) | Profile selector, typed input, colors, and display of terminal/Discord exchanges |
| [conversation.py](src/marionette/conversation.py) | Shared history, sequential turns, identity resolution, and permission checks |
| [context.py](src/marionette/context.py) | Exact history fitting and between-turn rollover preparation |
| [inference.py](src/marionette/inference.py) | Qwen-Agent response adapter, exact token counting, and local cache requests |
| [identity.py](src/marionette/identity.py) | Saved profiles, linked accounts, and sender metadata |
| [commands.py](src/marionette/commands.py) | Command recognition and shared-history actions |
| [permissions.py](src/marionette/permissions.py) | Command authorization for resolved identities; shared history clear is owner-only |
| [connection.py](src/marionette/connection.py) | Private local connection to the shared conversation |
| [discord.sh](scripts/native-linux/discord.sh) | Attach Discord to the running chat and display its connection log |
| [discord_bot.py](src/marionette/discord_bot.py) | Optional owner-only DM transport, sequential delivery, and local transcript |
| [style.py](src/marionette/style.py) and [log_view.py](src/marionette/log_view.py) | Shared colors and human-readable log views |
| [diagnostics.py](src/marionette/diagnostics.py) | Shared synchronized writer for client and runtime diagnostics |
| [log_router.py](src/marionette/log_router.py) | Diagnostic classification, timestamps, shared event numbers, and readable formatting |
| [view-log.sh](scripts/native-linux/view-log.sh) | Follow a saved log until the chat ends |
| [setup.py](scripts/native-linux/setup.py) and [downloads.json](scripts/native-linux/downloads.json) | Install and verify the pinned runtime and model |
| [setup-agent.sh](scripts/native-linux/setup-agent.sh) | Install the pinned Qwen-Agent environment used by main chat |
| [setup-discord.sh](scripts/native-linux/setup-discord.sh) | Install pinned Discord dependencies and create the local credential template if missing |
| [tests/core](tests/core) | Core regression checks using synthetic data; no personal conversations or model downloads |
| [tests/discord](tests/discord) | Optional Discord transport checks using mocked delivery |

`session.py` connects the components. `terminal.py` renders streamed text through a per-reply callback; inference and conversation code do not import terminal UI code. Future interfaces can supply their own callback while reusing identity, permissions, and conversation handling. The current Discord connection still queues work for the main terminal thread, preserving one shared conversation and sequential generation. For diagnostic flow and test commands, see [operation and verification](docs/setup.md).

## Folder map

- `STARTUP.md`: step-by-step launch and stop guide, with optional features clearly marked.
- `src/marionette/`: application code—terminal chat, optional Discord DMs, rollover, and diagnostic log processing.
- `scripts/native-linux/`: installation, terminal/Discord launchers, log-window launcher, and pinned dependency manifests.
- `docs/`: setup requirements, operation, and decisions.
- `docs/ideas/`: [discussion-only ideas](docs/ideas/README.md), separate from approved work and current behavior.
- `docs/licenses.md`: active dependency versions and licenses.
- `runtime/llama.cpp/`: downloaded runtime and bundled licenses; ignored by Git.
- `data/conversations/`: dated chat transcripts, server/model diagnostics, and optional Discord logs; ignored by Git.
- `data/identities/`: private, portable JSON profile registry; ignored by Git.
- `data/session/`: private socket for optional connections to the running chat; ignored by Git.
- `data/discord/`: private bot credentials and connection/setup locks; ignored by Git.
- `runtime/agent/`: isolated, hash-locked Qwen-Agent dependencies for main chat; ignored by Git.
- `runtime/discord/`: isolated optional Discord Python environment; ignored by Git.
- `tests/discord/`: optional Discord transport tests—owner filtering, delivery, attachment to main chat, and reasoning isolation.
- `data/models/`: local model weights; ignored by Git.
- `data/downloads/`: verified runtime archive; ignored by Git.
- `visual design/`: local visual references, independent of terminal chat; currently untracked.
- `tests/core/`: core application tests—setup, chat, shared connection, rollover, logging, and lifecycle.

See [native Linux setup and operation](docs/setup.md) and [licenses](docs/licenses.md).

## Archives

Keep inactive material separate from current files:

| Folder | Contents |
|---|---|
| `data/models/archive/` | Unused model weights, including the full-precision BF16 model |
| `data/conversations/archive/` | Completed sessions moved out of the current log listing |
| `docs/archive/` | Retired guides; current guides remain directly under `docs/` |
| `visual design/archive/` | Superseded visual references |

Archiving is manual; nothing is automatically moved or deleted. Move all related session files together only after chat and Discord have stopped. Archives under `data/` remain private and ignored by Git. Visual references, including their archive, remain local and untracked. These local folders can be created when needed on a new checkout.

Use Git history for retired source, scripts, and tests; do not keep duplicate old code in the active tree. Experiment reports stay under `docs/experiments/`. Runtime versions already have versioned directories; keep the manifest-selected runtime in place. Archives on the same disk are not backups.
