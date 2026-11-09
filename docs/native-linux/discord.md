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
2. Generate/reset its **bot token**. Store it only in `data/discord/.env`, never in chat, screenshots, or Git. The format is shown in `.env.example`; use plain values without quotes. Set `DISCORD_ALLOWED_USER_ID` to your numeric user ID (enable Developer Mode in Discord to copy it). Existing local configuration is preserved by setup.
3. Invite the bot to a private server you control, using the application's installation/OAuth2 link with the `bot` scope and no administrator permissions. This gives you a shared server from which to open the bot's profile and send it a DM. If needed, allow DMs from that server in Discord's privacy settings.
4. No privileged Message Content, Server Members, or Presence intent is needed: this client subscribes only to direct messages. It never answers in the server.

The local configuration requires both `DISCORD_ALLOWED_USER_ID` and `DISCORD_BOT_TOKEN` and file permissions `600`. Missing or invalid configuration stops the Discord connection before login; the already running main chat is unaffected. To edit it:

```bash
nvim data/discord/.env
```

## Start and stop

Launch her normally. This opens terminal chat and its two existing log windows:

```bash
cd /home/phatkitty/Projects/Marionette
./scripts/native-linux/chat.sh
```

After she is ready, open one additional terminal and run:

```bash
/home/phatkitty/Projects/Marionette/scripts/native-linux/discord.sh
```

Discord runs in that same terminal and attaches to the running conversation; it does not open another window. You now have four terminals: main chat, two model/server logs, and Discord. Wait for **Discord ready**, then DM the bot from your allowed account. Keep the Discord terminal open while using the connection. Your computer must stay awake and connected.

**Ctrl+C in the Discord window disconnects Discord only.** Closing the main chat stops the model and disconnects Discord. You can reconnect Discord later without resetting the running conversation. Restarting the main chat starts a fresh conversation. Nothing is installed as a background service; automatic connection at startup is not implemented.

- Terminal and Discord share one conversation, context budget, and rollover preparation. Inputs take turns generating. Main chat displays the Discord label in cyan and numeric user ID in lavender, your text in neon green, a yellow reasoning heading with white reasoning text, and a light-pink answer heading with hot-pink answer text. Only final answers are sent back to Discord; local terminal messages are not forwarded there. The sender label is display/log metadata, not an added model instruction, and does not authorize other users.
- `/clear` from either input clears the shared model history, not saved logs or Discord messages.
- Only text is accepted. Attachments and stickers receive a short unsupported-input notice.
- Discord replies are sent once complete and split into chunks when needed. Mention notifications and link previews are suppressed. Markdown can span chunk boundaries.
- Messages missed while the bot is offline are not fetched or replayed. In-process duplicate message events are ignored.
- A failed generation does not commit a new turn. A completed generation stays in shared history even if Discord disconnects or delivery fails. Delivery can be partial; no automatic resend occurs. Check the Discord log before retrying.

The main chat owns the model and conversation. A Unix socket at `data/session/chat.sock` lets the optional Discord process submit text; it does not expose a new network port. Its directory is private to your OS account, and the socket is removed on normal shutdown. Locks prevent duplicate main sessions and duplicate Discord connections. The adapter contains no separate history or model-launch code. See [context policy](context.md).

## Local logs and verification

The three main session files stay unchanged: `-chat.txt` records the terminal, and `-server.txt`/`-model.txt` record model diagnostics, including reasoning and accepted Discord turns. The terminal transcript now also includes the labeled Discord exchanges and their reasoning. Remote requests are queued for the main terminal thread to render between local turns, then the local input prompt is shown again.

Each Discord connection saves one additional dated `-discord.txt` file under `data/conversations/`. Its terminal displays readable message blocks: lavender IDs, green incoming text, light-pink answer headings with hot-pink answer text, light-blue timestamps, turquoise success events, peach timings, orange warnings, and bright-red errors. Diagnostic labels are white with colored values, and spacing separates identity, delivery, timing, and other fields. Pending sends are orange, confirmed parts turquoise, and failed parts red. It contains no model reasoning. An answer record confirms generation; the following delivery entry confirms sending. Credentials are never passed to the model or logged.

The Discord log adds these diagnostics without additional Discord permissions:

- Connection, disconnect, ready, and resumed events, with time disconnected when known.
- Sender ID, DM channel ID, and incoming message ID on each turn; outgoing message IDs on successful sends. IDs are stored as strings to preserve precision.
- Discord's message creation time and local handler receipt time, recorded before waiting for the previous turn. `receipt_delay_ms` compares those clocks; it is not a precise network measurement and can be negative if clocks disagree.
- `adapter_queue_ms`: waiting behind another Discord turn. `main_queue_ms`: waiting for main chat to pick up the request. `processing_ms`: local handling, including token counting, any rollover wait, and generation. `local_response_ms`: the complete local request, including main queue and connection overhead. These overlap; do not add all of them together.
- `send_ms` for each part and the complete send, plus `total_ms` from local receipt through successful answer delivery. Discord library retries/rate-limit waits are included in send time.
- Chunk count, each successful part's ID, and the failed part/number of confirmed earlier parts on failure. A failed request may still have reached Discord; no automatic resend is added.
- Error class, HTTP status, and Discord error code when provided. Exception bodies, request headers, credentials, and raw network packets are not dumped.
- `heartbeat_ms` snapshots on ready/resume/disconnect and accepted incoming messages. This is Gateway heartbeat round-trip latency, not message delivery latency. Unavailable readings are `null`; there is no continuous heartbeat log spam.

Saved diagnostics use timestamped event names followed by JSON fields; saved transcripts remain timestamped JSON records. The live view formats these without changing the saved evidence; see [log colors and reading saved logs](logs.md). Restart main chat and reconnect Discord after code updates so both processes use the same local request format. Main chat and model logs still contain reasoning; the Discord log does not.

Credentials and logs are ignored by Git. Regenerate a token in Discord if it is ever exposed.

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
