# Chat in the terminal

## Start

Open a terminal and paste:

```bash
cd /home/phatkitty/Projects/Marionette
./scripts/native-linux/chat.sh
```

A second terminal opens to show full debug output. In the chat terminal, wait for the `>` prompt, then type your message and press **Enter**.

## While chatting

Type these at the chat prompt:

| Command | What it does |
|---|---|
| `/clear` | Clears the current conversation so you can start fresh. |
| `/exit` | Closes the chat and returns you to the terminal. |

Each session saves two matching files in `data/conversations/`:

- `…-chat.txt`: your messages and her replies.
- `…-debug.txt`: full troubleshooting details, shown live in the second terminal.

Past logs stay there, but she starts fresh each launch. Logs remain local and are excluded from GitHub.

Closing the log window does not stop chat or recording. After `/exit`, press **Enter** in the log window to close it. `/clear` resets her context but does not erase the log.

## If setup is missing

From the same project folder, run:

```bash
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

Setup needs internet access to download missing files. You do not need to run it before every chat.

For installation details and advanced settings, see [Setup](setup.md).
