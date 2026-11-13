# Marionette

Local terminal chat with Qwen3.5 4B using a small Python terminal client and llama.cpp’s `llama-server`. Runs in the foreground with a local HTTP server owned by the client, no persistent background service or required account. Each launch opens two live log terminals (connections/requests and model processing) and saves conversations in local SQLite. Diagnostics use a [500 MB RAM rolling buffer](docs/active/current-operation/log-retention.md), saved on shutdown. Saved conversations are not automatically reloaded as memory.

## Quick start

Follow [STARTUP.md](STARTUP.md) to launch her in the terminal and optionally connect Discord. It lists the steps in order and explains how to stop each part.

For quick experiments, the owner can send [`/resetmemory`](docs/active/current-operation/reset-memory.md) from terminal or Discord to reset personal memory and all chat histories without reloading the model.

For a new installation, see [local setup](docs/active/setup-and-maintenance/setup.md). Setup downloads and verifies the pinned runtime and model; subsequent terminal chat runs are offline.

Optional phone access: [Discord DM setup](docs/active/setup-and-maintenance/discord.md). Launch her first, then optionally attach Discord to the same running model in a fourth terminal. It accepts human one-to-one DMs, sends only final answers to Discord, and displays the full exchange (including reasoning) in main chat and local logs. Discord requires an account and internet access; the terminal mode remains offline.

## Status and architecture

The current base runs Qwen3.5-4B Q4_K_M on the RX 7900 XT with Vulkan, a 65,536-token context, and thinking enabled (white reasoning, pink answers). Qwen-Agent coordinates model/tool turns, including bounded [contact notes](docs/active/current-operation/contact-notes.md) that are supplied automatically and can be updated proactively. Successful exchanges retain tool calls and results in active context; trimming removes them with their user input and answer. Our client still owns exact context trimming and background cache preparation. See [tool coordination](docs/active/current-operation/qwen-agent.md). Her [editable soul](docs/active/current-operation/soul.md) starts blank and supplies system context only once filled; `query_logs` supplies scoped setup, current status and message diagnostics. The model’s loopback server stops when chat exits.

Log-tool execution works, but answers can still misinterpret units or add unsupported details; see [current reliability limits](docs/active/current-operation/log-queries.md#current-reliability-limits).

An optional [read-only Obsidian connection](docs/active/setup-and-maintenance/obsidian-connection.md) lets her search and browse the local mirror through Cyanheads. It includes all contact collections and Active documentation; direct vault writes are disabled.

Chat runs in response to terminal or Discord input; there is no autonomous thinking cycle or temporary scratchpad system.

The selected 4B Q4_K_M weights live in `~/AI Infrastructure/AI Local Models/Qwen/Qwen3.5/4B/Instruct/`. The 9B Q4 and 4B BF16 files remain available. See [shared model storage](docs/active/setup-and-maintenance/setup.md#shared-model-storage) and [4B return verification](docs/development/experiments/4b-return-2026-11-12.md).

The **last saved stable baseline** is **`baseline-v4` (2026-11-11)**: a deliberately saved, simple working foundation to return to if later development becomes cluttered or unreliable. It records the program at that checkpoint, not the current setup. Later changes are not automatically included; a new baseline requires a deliberate decision and a new tag. Recovery steps are in [the baseline guide](docs/development/history/baseline.md).

See [context policy and limitations](docs/active/current-operation/context.md) for allowances, trimming, cache preparation, and limitations. See the [last saved stable baseline and its verification](docs/development/history/baseline.md) and [log guide](docs/active/current-operation/logs.md), with a [short log glossary](docs/active/current-operation/log-glossary.md) and the [request form](docs/active/current-operation/log-request-form.md) and [operator query handler](docs/active/current-operation/log-queries.md). See [SQLite storage, export, and recovery](docs/active/current-operation/storage.md) and the [local Obsidian conversation mirror](docs/active/setup-and-maintenance/conversation-vault.md). Historical experiments live under `docs/development/experiments/`.

Terminal profiles and linked accounts use permanent contact UUIDs. The schema-2 registry also stores preferred names, timezones, and creation/update timestamps; see [identities and migration](docs/active/current-operation/contacts.md). The earlier foundation is captured in `baseline-v4`; the previous [V3 guide](docs/development/history/baseline-v3-2026-11-09.md) is archived and its tag stays unchanged. Each Discord DM and the terminal have separate histories. Linked accounts share the contact’s notes, not their message history. The main terminal displays all activity.

## Documentation

Start with the [documentation map](docs/documentation-map.md). [Current operation](docs/active/current-operation/current-operation.md) explains implemented behavior; [Setup and maintenance](docs/active/setup-and-maintenance/setup-and-maintenance.md) covers installation and upkeep. These Active guides are mirrored into Obsidian.

[Development](docs/development/development-index.md) contains test reports, historical checkpoints and discussion-only ideas. It stays outside the vault. Keep dated results there; keep current limitations and supported procedures in Active.

## Reviewing the code

Start with these files, in order:

| File | Responsibility |
|---|---|
| [chat.sh](scripts/native-linux/chat.sh) | Launch options, private session files, recorder, and two log windows |
| [setup_datasheet.py](src/marionette/setup_datasheet.py) | Refresh the marked [setup datasheet](docs/active/setup-and-maintenance/setup-datasheet.md) section from startup observations |
| [session.py](src/marionette/session.py) | Component startup, server lifetime, readiness, and shutdown |
| [terminal.py](src/marionette/terminal.py) | Profile selector, typed input, colors, and display of terminal/Discord exchanges |
| [conversation.py](src/marionette/conversation.py) | Separate histories, sequential turns, identity resolution, and permission checks |
| [context.py](src/marionette/context.py) | Exact history fitting and between-turn rollover preparation |
| [inference.py](src/marionette/inference.py) | Local HTTP, exact budgets, cache preparation, and Qwen-Agent response adapter |
| [coordination.py](src/marionette/coordination.py) | Qwen-Agent tool loop with explicit tool registration |
| [contact_notes.py](src/marionette/contact_notes.py) | Bounded Markdown contact notes and current-contact add/patch/remove tool |
| [soul.py](src/marionette/soul.py) | Permanent self UUID, revisioned soul, and self-editing tool |
| [memory_reset.py](src/marionette/memory_reset.py) and [reset_boundary.py](src/marionette/reset_boundary.py) | Owner-only live memory reset and recorder boundaries |
| [data_migration.py](src/marionette/data_migration.py) | Preserving legacy contact and soul paths during startup |
| [contacts.py](src/marionette/contacts.py) | Saved profiles, linked accounts, and sender metadata |
| [commands.py](src/marionette/commands.py) | Command recognition and conversation-scoped actions |
| [permissions.py](src/marionette/permissions.py) | Restrict clearing to the sender’s own conversation |
| [connection.py](src/marionette/connection.py) | Private local connection to the conversation manager |
| [discord.sh](scripts/native-linux/discord.sh) | Attach Discord to the running chat and display its connection log |
| [discord_bot.py](src/marionette/discord_bot.py) | Optional human one-to-one DM transport, sequential delivery, and local transcript |
| [style.py](src/marionette/style.py) and [log_view.py](src/marionette/log_view.py) | Shared colors and human-readable log views |
| [log_metadata.py](src/marionette/log_metadata.py) | Extract explicit searchable event metadata; [fields and indexes](docs/active/current-operation/storage.md#searchable-diagnostic-metadata-schema-5) |
| [storage.py](src/marionette/storage.py) and [storage.sh](scripts/native-linux/storage.sh) | SQLite messages/events, live views, portable export, and verified backups |
| [diagnostics.py](src/marionette/diagnostics.py) | Shared synchronized writer for client and runtime diagnostics |
| [vault_tool.py](src/marionette/vault_tool.py) | Read-only browsing, search, tags, sections and UI navigation over local Cyanheads MCP |
| [setup-obsidian.py](scripts/native-linux/setup-obsidian.py) | Install the locked connector and checksum-verified Obsidian API plugin |
| [log_tool.py](src/marionette/log_tool.py) | Qwen-Agent log adapter scoped to the current session and conversation |
| [log_query.py](src/marionette/log_query.py) | Validate request forms and return bounded, scoped log facts |
| [operator_status.py](src/marionette/operator_status.py) | Read-only Discord status probe in the existing bot process |
| [ram_logs.py](src/marionette/ram_logs.py) | Existing-recorder RAM buffer, live views, and shutdown saving |
| [retention.py](src/marionette/retention.py) | [Rolling diagnostic batches and protected error windows](docs/active/current-operation/log-retention.md) |
| [log_router.py](src/marionette/log_router.py) | Diagnostic classification and reversible human-readable formatting |
| [view-log.sh](scripts/native-linux/view-log.sh) | Follow a saved log until the chat ends |
| [setup.py](scripts/native-linux/setup.py) and [downloads.json](scripts/native-linux/downloads.json) | Install and verify the pinned runtime and model |
| [setup-agent.sh](scripts/native-linux/setup-agent.sh) | Install pinned Qwen-Agent dependencies for main chat |
| [setup-discord.sh](scripts/native-linux/setup-discord.sh) | Install pinned Discord dependencies and create the local credential template if missing |
| [tests/core](tests/core) | Core regression checks using synthetic data; no personal conversations or model downloads |
| [tests/discord](tests/discord) | Optional Discord transport checks using mocked delivery |

`session.py` connects the components. `terminal.py` renders streamed text through a per-reply callback; inference and conversation code do not import terminal UI code. Future interfaces can supply their own callback while reusing identity, permissions, and conversation handling. The current Discord connection still queues work for the main terminal thread, preserving sequential generation across separate conversations. For diagnostic flow and test commands, see [operation and maintenance checks](docs/active/setup-and-maintenance/setup.md).

## Folder map

- `prompts/`: versioned feature instructions, explicitly bound to the system prompt separately from the soul.
- `STARTUP.md`: step-by-step launch and stop guide, with optional features clearly marked.
- `src/marionette/`: application code—terminal chat, optional Discord DMs, rollover, and diagnostic log processing.
- `scripts/native-linux/`: installation, terminal/Discord launchers, log-window launcher, and pinned dependency manifests.
- `docs/`: [documentation map](docs/documentation-map.md).
- `docs/active/current-operation/`: current behavior and feature guides; mirrored into Obsidian.
- `docs/active/setup-and-maintenance/`: installation, configuration, maintenance and licenses; mirrored into Obsidian.
- `docs/development/`: [development index](docs/development/development-index.md); excluded from Obsidian.
- `docs/development/experiments/`: [test reports and investigations](docs/development/experiments/experiment-index.md), including reports extracted from Active guides.
- `docs/development/history/`: [saved baselines and retired documentation](docs/development/history/history-index.md).
- `docs/development/ideas/`: [discussion-only ideas](docs/development/ideas/ideas-guide.md), separate from approved work and current behavior.
- `docs/active/setup-and-maintenance/licenses.md`: active dependency versions and licenses.
- `~/AI Infrastructure/AI Apps/Inference Engines/Language Models/llama.cpp/`: shared versioned inference runtime and bundled licenses; outside Git. See [runtime storage](docs/active/setup-and-maintenance/setup.md#shared-inference-runtime).
- `data/conversations/`: SQLite conversation/event database, optional private exports and backups; ignored by Git.
- `data/conversations/obsidian-vault/`: private Markdown conversation mirror, refreshed on orderly shutdown or manually for Obsidian; cleared by memory reset.
- `data/contacts/`: private, portable JSON profile registry; ignored by Git.
- `data/contact_notes/`: private Markdown contact notes, one file per contact UUID; ignored by Git.
- `data/soul/`: private self identity and soul revision history; ignored by Git.
- `data/session/`: private socket and current logging-session descriptor; ignored by Git.
- `data/discord/`: private bot credentials and connection/setup locks; ignored by Git.
- `runtime/obsidian-mcp/`: pinned optional Cyanheads Node environment; ignored by Git.
- `data/obsidian/`: private local vault connection settings and credential; ignored by Git.
- `scripts/native-linux/obsidian/`: connector npm lockfile and plugin download checksums.
- `runtime/agent/`: project-specific, hash-locked Qwen-Agent environment; ignored by Git.
- `runtime/discord/`: isolated optional Discord Python environment; ignored by Git.
- `tests/discord/`: optional Discord transport tests—human one-to-one DM filtering, delivery, attachment to main chat, and reasoning isolation.
- `~/AI Infrastructure/AI Local Models/`: shared local model library outside the checkout; [setup and launch](docs/active/setup-and-maintenance/setup.md#shared-model-storage) use `Qwen/Qwen3.5/4B/Instruct/`.
- `data/downloads/`: verified runtime archive; ignored by Git.
- `visual design/`: local visual references, independent of terminal chat; currently untracked.
- `tests/core/`: core application tests—setup, chat, shared connection, rollover, logging, and lifecycle.

See [native Linux setup and operation](docs/active/setup-and-maintenance/setup.md), the [latest-startup datasheet](docs/active/setup-and-maintenance/setup-datasheet.md), and [licenses](docs/active/setup-and-maintenance/licenses.md).

## Archives

Keep inactive material separate from current files:

| Folder | Contents |
|---|---|
| `data/conversations/archive/` | Optional manually retained private exports or backups |
| `docs/development/history/` | Historical baselines and retired guides; active guides live under `docs/active/` |
| `visual design/archive/` | Superseded visual references |

Archiving documents and private exports is manual. Routine diagnostic events expire automatically under the [rolling retention policy](docs/active/current-operation/log-retention.md). For the current SQLite database, use the [backup procedure](docs/active/current-operation/storage.md#backup-and-restore); do not move a live database or separate its WAL/SHM sidecars. Archives under `data/` remain private and ignored by Git. Visual references, including their archive, remain local and untracked. These local folders can be created when needed on a new checkout. Unused model variants such as BF16 stay alongside Q4 in the shared model library; the download manifest selects Q4 for Marionette.

Use Git history for retired source, scripts, and tests; do not keep duplicate old code in the active tree. Experiment reports stay under `docs/development/experiments/`. Runtime versions already have versioned directories; keep the manifest-selected runtime in place. Archives on the same disk are not backups.
