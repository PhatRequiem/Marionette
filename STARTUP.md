# Start Marionette

Follow these steps in order. Launch the main chat first, then choose any optional connections you want to use.

If this checkout needs its Qwen-Agent dependencies installed, run `./scripts/native-linux/setup-agent.sh` once first. Full installation is covered in [setup](docs/setup.md).

## 1. Launch her — required

Open a terminal and run:

```bash
cd /home/phatkitty/Projects/Marionette
./scripts/native-linux/chat.sh
```

This starts her and opens two log windows: **Connections and requests** and **Model processing**. Choose **Phat** (or **Add new profile**) when prompted, then wait for **Ready** and the `>` prompt. Profiles persist between launches; see [identities](docs/identity.md). You can now chat in this terminal.

## 2. Connect Discord — optional

Skip this step if you only want terminal chat. After she is ready, open another terminal and run:

```bash
cd /home/phatkitty/Projects/Marionette
./scripts/native-linux/discord.sh
```

Wait for **Discord ready**, then DM her. This terminal shows the Discord logs. Only her final answers go to Discord; reasoning stays local. Each Discord DM has its own conversation, separate from typed terminal messages. The main terminal still displays all messages, reasoning, and answers.

## Stop or start fresh

- **Disconnect Discord only:** press Ctrl+C in its terminal. Main chat stays running.
- **Stop her:** type `/exit` in main chat, or press Ctrl+C. This also disconnects Discord. Press Enter in each diagnostic log window afterward to close it.
- **Clear the conversation:** type `/clear` in that conversation. Each person can clear their own DM; terminal `/clear` affects only terminal history. Saved logs remain. Every new main-chat launch also starts fresh.

## First-time setup

If the model or runtime is missing, follow [local setup](docs/setup.md). Before the first Discord connection, follow [Discord setup](docs/discord.md). These are one-time steps, not required on every launch.

Future launchable features should be added below the required main-chat step, in dependency order, with their command and a clear required/optional label. Keep technical configuration in the component guides.
