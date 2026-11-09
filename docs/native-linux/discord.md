# Discord DMs

An optional Discord bot runs on this computer and talks only to the configured owner's numeric user ID in one-to-one DMs. Server channels, group DMs, other users, and bots are ignored before their content reaches the model or transcript. Only final model answers are sent to Discord; reasoning stays in local diagnostic logs. Short status/error notices may also be sent.

The model stays local. Discord is an external, proprietary service requiring an account, a bot application, and internet access. Your messages and final answers pass through Discord. Terminal chat remains available offline without Discord dependencies.

## One-time setup

The runtime/model must already be installed with `python scripts/native-linux/setup.py`. Install the optional Python dependencies:

```bash
cd /home/phatkitty/Projects/Marionette
./scripts/native-linux/setup-discord.sh
```

This uses [uv](https://docs.astral.sh/uv/getting-started/installation/) (already installed on the current computer), an isolated environment in `runtime/discord/`, and the pinned, hash-checked `discord-requirements.txt`. It does not alter system Python. Network access is needed for dependency installation.

1. Open the [Discord developer portal](https://discord.com/developers/applications), create an application, and open its **Bot** settings. Keep the bot private (Public Bot off).
2. Generate/reset its **bot token**. Store it only in `data/discord/.env`, never in chat, screenshots, or Git. The format is shown in `.env.example`; use plain values without quotes. The owner ID has already been filled in locally for this checkout.
3. Invite the bot to a private server you control, using the application's installation/OAuth2 link with the `bot` scope and no administrator permissions. This gives you a shared server from which to open the bot's profile and send it a DM. If needed, allow DMs from that server in Discord's privacy settings.
4. No privileged Message Content, Server Members, or Presence intent is needed: this client subscribes only to direct messages. It never answers in the server.

The local configuration requires both `DISCORD_ALLOWED_USER_ID` and `DISCORD_BOT_TOKEN` and file permissions `600`. Missing or invalid configuration stops launch before loading the model. To edit it:

```bash
nano data/discord/.env
```

## Start and stop

Stop any existing terminal chat first. Then:

```bash
cd /home/phatkitty/Projects/Marionette
./scripts/native-linux/discord.sh
```

Wait for **Discord ready**, then DM the bot from your allowed account. Your computer must stay awake and connected. This is a foreground process, not an installed background service. **Ctrl+C** in its terminal stops the bot and its owned local model server. A lock prevents two updated launchers from running simultaneously.

- `/clear` in the DM clears the model's conversation history, not saved local logs or Discord messages.
- Only text is accepted. Attachments and stickers receive a short unsupported-input notice.
- Messages are handled sequentially. New DMs wait while the current reply is being generated or sent.
- Replies are sent once complete and split into chunks when needed. Mention notifications and link previews are suppressed. Markdown can span chunk boundaries.
- Reconnection keeps in-memory history while the process remains alive; restarting starts fresh. Messages missed while the bot is offline are not fetched or replayed. In-process duplicate message events are ignored.
- A failed generation does not commit a new turn. A failed send may leave part of an answer on Discord; it is logged and is not automatically resent. Only fully delivered answers are committed to history.

The model uses the same sampling, context limits, token counting, and rollover preparation as terminal chat. See [context policy](context.md).

## Local logs and verification

Three dated files with `discord_` in their names are saved under `data/conversations/`. Discord mode does not open separate desktop windows:

- `-chat.txt`: timestamped JSON records of accepted user text, final answers, and clear notices, plus launch/status text. An answer record describes generation; check diagnostics to confirm delivery.
- `-server.txt` and `-model.txt`: the same numbered, readable diagnostics as terminal mode, including locally recorded reasoning. Unknown/shared events appear in both.

Credentials and logs are ignored by Git. Regenerate a token in Discord if it is ever exposed. No credentials are passed to the model or placed in the server launch command.

Run the core and optional transport checks separately:

```bash
python -m unittest discover -s tests/native-linux -v
runtime/discord/bin/python -m unittest discover -s tests/discord -v
```

Tests use synthetic messages and mock delivery, not Discord accounts. Live Discord login and phone delivery require your bot token and a manual DM check; passing local tests does not establish that Discord configuration is complete.

To update the optional dependency lock deliberately:

```bash
uv pip compile --python python --generate-hashes scripts/native-linux/discord-requirements.in -o scripts/native-linux/discord-requirements.txt
./scripts/native-linux/setup-discord.sh
```

Review changed packages and licenses and rerun both test suites when updating.
