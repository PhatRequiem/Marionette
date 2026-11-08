# Chat in the terminal

## Start

Open a terminal and paste:

```bash
cd /home/phatkitty/Projects/Marionette
./scripts/native-linux/chat.sh
```

Wait for the `>` prompt, then type your message and press **Enter**.

## While chatting

Type these at the chat prompt:

| Command | What it does |
|---|---|
| `/clear` | Clears the current conversation so you can start fresh. |
| `/exit` | Closes the chat and returns you to the terminal. |

She runs locally and offline. Conversations are not saved between launches.

## If setup is missing

From the same project folder, run:

```bash
python scripts/native-linux/setup.py
./scripts/native-linux/chat.sh
```

Setup needs internet access to download missing files. You do not need to run it before every chat.

For installation details and advanced settings, see [Setup](setup.md).
