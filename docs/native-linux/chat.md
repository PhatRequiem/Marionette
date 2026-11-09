# Chat in the terminal

## Start her

```bash
cd /home/phatkitty/Projects/Marionette
./scripts/native-linux/chat.sh
```

Two log windows open: **Connections and requests** and **Model processing**. Wait for `>` in the main terminal, then type and press Enter. Your input is neon green, her reasoning white, and her answers pink. Headings, IDs, status, and timing values use the shared [log colors](logs.md).

## Optionally connect Discord

After [one-time Discord setup](discord.md), open a fourth terminal:

```bash
cd /home/phatkitty/Projects/Marionette
./scripts/native-linux/discord.sh
```

This terminal is the Discord log window. Your DMs appear in main chat with your numeric sender ID, followed by her reasoning and answer. Only her answer is sent to Discord. Both inputs share the same conversation. Ctrl+C in the Discord terminal disconnects it while main chat stays running.

## While chatting

- `/clear` starts a fresh conversation.
- `/exit`, Ctrl+C, or Ctrl+D at an empty prompt closes main chat and its local server.
- Closing a log window does not stop chat or recording. After chat exits, press Enter in each diagnostic window to close it.

The context limit is 65,536 tokens; reasoning and answers share a 32,768-token allowance. Older exchanges are removed as needed, with preparation after replies. See [context policy](context.md) for timing and limits.

Dated transcripts and diagnostics stay in `data/conversations/`; [the log guide](logs.md) explains each file. Each launch starts fresh. She cannot read files or logs herself, and no setup report or personality file is supplied.

## If setup is missing

```bash
python scripts/native-linux/setup.py
```

Run this from the project folder, then launch normally. Setup needs internet access for missing downloads; ordinary terminal chat runs offline. See [setup](setup.md) for requirements and advanced settings.
