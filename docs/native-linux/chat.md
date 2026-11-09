# Chat in the terminal

## Start

Open a terminal and paste:

```bash
cd /home/phatkitty/Projects/Marionette
./scripts/native-linux/chat.sh
```

Two log terminals open: **Connections and requests** and **Model processing**. In the chat terminal, wait for the `>` prompt, then type your message and press **Enter**.

## While chatting

- **Exit:** type `/exit`, or press **Ctrl+D** at an empty chat prompt.
- **Start fresh:** type `/clear`, or exit and launch again.

The embedded server is local to this computer and stops when the chat process exits. Its temporary address appears in the connections-and-requests log and setup snapshot.

After loading, she receives a generated report of the observed setup with your first message, and again with the first message after `/clear`. She still cannot open files or read logs herself.

Each session saves four matching files in `data/conversations/`:

- `…-chat.txt`: your messages and her replies.
- `…-server.txt`: connections and requests, shown in its own terminal.
- `…-model.txt`: model processing, shown in its own terminal.
- `…-setup.json`: generated setup facts and the context supplied to her.

Past logs stay there, but she starts fresh each launch. Logs remain local and are excluded from GitHub.

Unknown entries, warnings, and errors appear in both diagnostic files with the same event number. Original timestamps are retained. There is no new raw debug file; older logs remain untouched.

Closing either log window does not stop chat or recording. After chat exits, press **Enter** in each log window to close it. Restarting chat does not erase past logs.

## If setup is missing

From the same project folder, run:

```bash
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

Setup needs internet access to download missing files. You do not need to run it before every chat.

For installation details and advanced settings, see [Setup](setup.md).
