# Discord DMs

An optional Discord bot runs on this computer and accepts one-to-one DMs from human users who can reach the bot. Server channels, group DMs, and bots are ignored before their content reaches the model or transcript. Only final model answers are sent to Discord; reasoning stays in local diagnostic logs. Short status/error notices may also be sent.

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

`DISCORD_ALLOWED_USER_ID` retains its legacy name for compatibility: it now identifies the owner account for identity linking, not an access allowlist. The local configuration still requires both `DISCORD_ALLOWED_USER_ID` and `DISCORD_BOT_TOKEN` and file permissions `600`. Missing or invalid configuration stops the Discord connection before login; the already running main chat is unaffected. To edit it:

```bash
nvim data/discord/.env
```

## Start and stop

Follow [STARTUP.md](../../../STARTUP.md): launch main chat first, then optionally run the Discord connection in a fourth terminal. Wait for **Discord ready**, then DM the bot. Keep the Discord terminal open while using the connection. Your computer must stay awake and connected.

**Ctrl+C in the Discord window disconnects Discord only.** Closing the main chat stops the model and disconnects Discord. You can reconnect Discord later without resetting the running conversation. Restarting the main chat starts a fresh conversation. Nothing is installed as a background service; automatic connection at startup is not implemented.

- Each Discord sender and the terminal have separate histories, with the same per-conversation context budget and rollover preparation. Inputs take turns generating. Main chat displays the Discord label in cyan and numeric user ID in lavender, your text in neon green, a yellow reasoning heading with white reasoning text, and a light-pink answer heading with hot-pink answer text. Only final answers are sent back to Discord; local terminal messages are not forwarded there. The client includes source, sender ID, display name, and contact UUID in each model input; your configured Discord account maps to Phat independently of the selected terminal profile. See [identity mapping](../current-operation/contacts.md). New Discord senders receive their own saved UUID, a name initialized from their Discord display name, and contact notes; identities are never merged by name. Only that conversation’s messages and the current contact’s contact notes are supplied to the model. Linked terminal/Discord accounts share contact notes but not history.
- `/resetmemory` is owner-only and resets all local memory and histories while staying connected. See [reset behavior and limits](../current-operation/reset-memory.md).
- `/clear` clears only the sender’s originating conversation, not saved contact notes, logs, or Discord messages. Every DM sender may clear their own conversation.
- Only text is accepted. Attachments and stickers receive a short unsupported-input notice.
- Discord replies are sent once complete and split into chunks when needed. Mention notifications and link previews are suppressed. Markdown can span chunk boundaries.
- After a temporary disconnect, a successful Discord Gateway resume replays missed events. This differs from stopping the bot or reconnecting without a resumable session: the application does not fetch missed message history in those cases, so you may need to resend. In-process duplicate/older message events are ignored per DM channel, so activity in another channel does not discard a valid message. See [Discord's resume behavior](https://github.com/discord/discord-api-docs/blob/main/developers/events/gateway.mdx#resuming).
- A failed generation does not commit a new turn. A completed generation stays in that conversation’s history even if Discord disconnects or delivery fails. Delivery can be partial; no automatic resend occurs. Check the Discord log before retrying.

The main chat owns the model and conversation histories. A Unix socket at `data/session/chat.sock` lets the optional Discord process submit text and sender identity; it does not expose a new network port. Its directory is private to your OS account, and the socket is removed on normal shutdown. Locks prevent duplicate main sessions and duplicate Discord connections. The adapter contains no history storage or model-launch code. See [context policy](../current-operation/context.md).

## Local logs and maintenance checks

Main chat and Discord now share the main launch's SQLite session. Terminal output and Discord connection events are stored streams; server/model diagnostics use the existing recorder’s RAM and are saved at shutdown; structured conversation messages are recorded by main chat. The operator terminal still displays labeled Discord exchanges and reasoning. Remote requests are queued for the main terminal thread and the input prompt returns afterward.

The Discord launcher reads `data/session/log-session.json` to use the same database even with a custom main-chat log directory. Disconnecting/reconnecting adds events to that session without creating text files. Its terminal displays readable message blocks: lavender IDs, green incoming text, light-pink answer headings with hot-pink answer text, light-blue timestamps, turquoise success events, peach timings, orange warnings, and bright-red errors. Diagnostic labels are white with colored values, and spacing separates identity, delivery, timing, and other fields. Pending sends are orange, confirmed parts turquoise, and failed parts red. It contains no model reasoning. An answer record confirms generation; the following delivery entry confirms sending. Credentials are never passed to the model or logged.

The Discord log adds these diagnostics without additional Discord permissions:

- Connection, disconnect, ready, and resumed events, with time disconnected when known.
- Sender ID, DM channel ID, and incoming message ID on each turn; outgoing message IDs on successful sends. IDs are stored as strings to preserve precision. `log_message_id` links the same message to main processing diagnostics, with explicit start/end markers for delivery; see [message log boundaries](../current-operation/logs.md#message-ids-and-section-boundaries).
- Discord's message creation time and local handler receipt time, recorded before waiting for the previous turn. `receipt_delay_ms` compares those clocks; it is not a precise network measurement and can be negative if clocks disagree.
- `adapter_queue_ms`: waiting behind another Discord turn. `main_queue_ms`: waiting for main chat to pick up the request. `processing_ms`: local handling, including token counting, any rollover wait, and generation. `local_response_ms`: the complete local request, including main queue and connection overhead. These overlap; do not add all of them together.
- `send_ms` for each part and the complete send, plus `total_ms` from local receipt through successful answer delivery. Discord library retries/rate-limit waits are included in send time.
- Chunk count, each successful part's ID, and the failed part/number of confirmed earlier parts on failure. A failed request may still have reached Discord; no automatic resend is added.
- Error class, HTTP status, and Discord error code when provided. Exception bodies, request headers, credentials, and raw network packets are not dumped.
- `heartbeat_ms` snapshots on ready/resume/disconnect and accepted incoming messages. This is Gateway heartbeat round-trip latency, not message delivery latency. Unavailable readings are `null`; there is no continuous heartbeat log spam.

Discord event payloads preserve timestamped names and JSON fields/records as original bytes in SQLite; server/model events use their own stream. The live view formats these without changing the saved evidence; see [log colors and reading saved logs](../current-operation/logs.md). Restart main chat and reconnect Discord after code updates so both processes use the same local request format. Main chat and model logs still contain reasoning; the Discord log does not.

Credentials and logs are ignored by Git. Regenerate a token in Discord if it is ever exposed.

Run the core and optional transport checks separately:

```bash
runtime/agent/bin/python -m unittest discover -s tests/core -v
runtime/discord/bin/python -m unittest discover -s tests/discord -v
```

Tests use synthetic messages and mock delivery, not Discord accounts. Live Discord login and phone delivery require your bot token and a manual DM check; passing local tests does not establish that Discord configuration is complete.

To update the optional dependency lock deliberately:

```bash
uv pip compile --python python --generate-hashes scripts/native-linux/discord-requirements.in -o scripts/native-linux/discord-requirements.txt
./scripts/native-linux/setup-discord.sh
```

Review changed packages and licenses and rerun both test suites when updating.

Conversation commands are checked by [command permissions](../current-operation/contacts.md#command-permissions): `/clear` targets only the resolved sender’s originating conversation.

The [operator query handler](../current-operation/log-queries.md) can request fresh Discord status
from a same-user private socket in the existing bot process. The response is
`online`, `connecting`, or `offline`; an unreachable probe means `unknown`.
Restart the adapter after updating code to enable this endpoint. It neither
updates the startup datasheet nor exposes a model tool.

Discord display names are carried as separate sender metadata over the local socket, never parsed from message text. Saved names are retained after initial capture; legacy generated numeric labels are filled on the next DM. Numeric Discord IDs and permanent contact UUIDs still identify senders and route conversations. Name capture occurs when a message arrives. See [name preservation and fallback rules](../current-operation/contacts.md).

## Admin shutdown

The saved owner can send `/shutdown` in a DM or main terminal. Code resolves the
sender account to the saved owner UUID, using the same authorization as memory
reset; Discord server roles, display names and message claims do not grant access.
Non-owners receive `Access Denied`. No inference is performed for either outcome.
The command waits for current work through the existing sequential turn handling,
then main chat returns through normal model/recorder cleanup. Saved conversations,
soul, notes and the vault are preserved. Discord attempts to deliver the shutdown
acknowledgement before disconnecting; network failures can prevent delivery.
This stops Marionette, not the computer. `/exit` remains a local terminal exit.
Restart main chat and Discord after code updates so both use the installed command implementation.
