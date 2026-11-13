# Start Marionette

Follow these steps in order. Launch the main chat first, then choose any optional connections you want to use.

If this checkout needs its Qwen-Agent dependencies installed, run `./scripts/native-linux/setup-agent.sh` once first. Full installation is covered in [setup](docs/active/setup-and-maintenance/setup.md).

## 1. Launch her — required

Open a terminal and run:

```bash
cd /home/phatkitty/Projects/Marionette
./scripts/native-linux/chat.sh
```

This starts her and opens two log windows: **Connections and requests** and **Model processing**. Choose **Phat** (or **Add new profile**) when prompted, then wait for **Ready** and the `>` prompt. ContactProfiles persist between launches; see [identities](docs/active/current-operation/contacts.md). You can now chat in this terminal.

The log-query tool is connected.

## 2. Connect Discord — optional

Skip this step if you only want terminal chat. After she is ready, open another terminal and run:

```bash
cd /home/phatkitty/Projects/Marionette
./scripts/native-linux/discord.sh
```

Wait for **Discord ready**, then DM her. This terminal shows the Discord logs. Only her final answers go to Discord; reasoning stays local. Each Discord DM has its own conversation, separate from typed terminal messages. The main terminal still displays all messages, reasoning, and answers.

## Stop or start fresh

- **Disconnect Discord only:** press Ctrl+C in its terminal. Main chat stays running.
- **Admin shutdown:** send `/shutdown` as the saved owner in terminal or Discord. Stops the local model and main chat, disconnects Discord, and follows normal recorder shutdown saving. Saved memory is kept. Other contacts receive `Access Denied`.
- **Stop her:** type `/exit` in main chat, or press Ctrl+C. This also disconnects Discord. Press Enter in each diagnostic log window afterward to close it.
- **Reset all memory (owner only):** type `/resetmemory` in terminal or Discord. Clears all chat histories, soul, contact notes, and local logs while preserving both IDs and your owner/account mapping. The model stays loaded. See [reset details](docs/active/current-operation/reset-memory.md).
- **Clear the conversation:** type `/clear` in that conversation. Each person can clear their own DM; terminal `/clear` affects only terminal history. Saved SQLite records remain. Every new main-chat launch also starts fresh model history; contact notes persist.

## First-time setup

If the model or runtime is missing, follow [local setup](docs/active/setup-and-maintenance/setup.md). Before the first Discord connection, follow [Discord setup](docs/active/setup-and-maintenance/discord.md). These are one-time steps, not required on every launch.

Future launchable features should be added below the required main-chat step, in dependency order, with their command and a clear required/optional label. Keep technical configuration in the component guides.

Conversations and diagnostics are saved in `data/conversations/marionette.sqlite3`. See [viewing and backups](docs/active/current-operation/storage.md); no extra startup step is required.
