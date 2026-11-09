# Chat in the terminal

## Start

Open a terminal and paste:

```bash
cd /home/phatkitty/Projects/Marionette
./scripts/native-linux/chat.sh
```

A second terminal opens to show full debug output. In the chat terminal, wait for the `>` prompt, then type your message and press **Enter**.

## While chatting

- **Exit:** press **Ctrl+D** at an empty chat prompt.
- **Start fresh:** exit, then run the launch command again.

`/exit` and `/clear` are not commands in this runtime; typing them sends them as messages.

After loading, she receives a generated report of the observed setup with your first message. She still cannot open files or read logs herself.

Each session saves three matching files in `data/conversations/`:

- `…-chat.txt`: your messages and her replies.
- `…-debug.txt`: full troubleshooting details, shown live in the second terminal.
- `…-setup.json`: generated setup facts and the context supplied to her.

Past logs stay there, but she starts fresh each launch. Logs remain local and are excluded from GitHub.

Closing the log window does not stop chat or recording. After chat exits, press **Enter** in the log window to close it. Restarting chat does not erase past logs.

## If setup is missing

From the same project folder, run:

```bash
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

Setup needs internet access to download missing files. You do not need to run it before every chat.

For installation details and advanced settings, see [Setup](setup.md).
