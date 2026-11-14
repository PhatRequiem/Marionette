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

Follow [STARTUP.md](../../../STARTUP.md): launch main chat first and use
`/startdiscord` from the owner's terminal profile. Wait for **Discord ready** in
Connections and requests before sending a DM. `/stopdiscord` disconnects without
stopping the model; `/startdiscord` reconnects. These are application commands,
not model tools, and are available only in terminal chat to the saved owner.

Background mode starts the existing bot and durable Discord recorder without a
fifth terminal. It shares the connection lock with `discord.sh`, preventing
simultaneous background/foreground connections. Startup acknowledgement means
starting, not confirmed online. A failed connection is visible in connection logs;
no automatic restart is added. Stop waits for owned processes and recorder draining.
On main-chat exit, the bot gets time to deliver a shutdown acknowledgement before
cleanup; a stuck owned bot is stopped. Your computer must remain awake and online.

The original `./scripts/native-linux/discord.sh` foreground command remains
supported. Ctrl+C in that terminal disconnects Discord only. `/stopdiscord` can
also request that foreground bot to close through its existing same-OS-user local
status/control socket; this reports a disconnect request, not confirmed completion.
The model's status probe remains read-only. Stopping can interrupt an active delivery;
check connection logs before retrying a message.

- Each Discord sender and the terminal have separate histories, with the same per-conversation context budget and rollover preparation. Inputs take turns generating. Main chat displays the Discord label in cyan and numeric user ID in lavender, your text in neon green and a light-pink answer heading with hot-pink answer text. Only final answers are sent back to Discord; local terminal messages are not forwarded there. The client includes source, sender ID, display name, and contact UUID in each model input; your configured Discord account maps to Phat independently of the selected terminal profile. See [identity mapping](../current-operation/contacts.md). New Discord senders receive their own saved UUID, a name initialized from their Discord display name, and contact notes; identities are never merged by name. Only that conversation’s messages and the current contact’s contact notes are supplied to the model. Linked terminal/Discord accounts share contact notes but not history.
- `/resetmemory` is owner-only and resets all local memory and histories while staying connected. See [reset behavior and limits](../current-operation/reset-memory.md).
- `/clear` clears only the sender’s originating conversation, not saved contact notes, logs, or Discord messages. Every DM sender may clear their own conversation.
- Only text is accepted. Attachments and stickers receive a short unsupported-input notice.
- Discord replies are sent once complete and split into chunks when needed. Mention notifications and link previews are suppressed. Markdown can span chunk boundaries.
- After a temporary disconnect, a successful Discord Gateway resume replays missed events. This differs from stopping the bot or reconnecting without a resumable session: the application does not fetch missed message history in those cases, so you may need to resend. In-process duplicate/older message events are ignored per DM channel, so activity in another channel does not discard a valid message. See [Discord's resume behavior](https://github.com/discord/discord-api-docs/blob/main/developers/events/gateway.mdx#resuming).
- A failed generation does not commit a new turn. A completed generation stays in that conversation’s history even if Discord disconnects or delivery fails. Delivery can be partial; no automatic resend occurs. Check the Discord log before retrying.

The main chat owns the model and conversation histories. A Unix socket at `data/session/chat.sock` lets the optional Discord process submit text and sender identity; it does not expose a new network port. Its directory is private to your OS account, and the socket is removed on normal shutdown. Locks prevent duplicate main sessions and duplicate Discord connections. The adapter contains no history storage or model-launch code. See [context policy](../current-operation/context.md).

## Local logs and maintenance checks

Main chat and Discord now share the main launch's SQLite session. Terminal output and Discord connection events are stored streams; server/model diagnostics use the existing recorder’s RAM and are saved at shutdown; structured conversation messages are recorded by main chat. The operator chat terminal displays labeled Discord messages and replies; the separate Reasoning terminal streams their reasoning. Remote requests are queued for the main terminal thread and the input prompt returns afterward.

The Discord launcher reads `data/session/log-session.json` to use the same database even with a custom main-chat log directory. Disconnecting/reconnecting adds events to that session without creating text files. The optional foreground terminal displays readable message blocks: lavender IDs, green incoming text, light-pink answer headings with hot-pink answer text, light-blue timestamps, turquoise success events, peach timings, orange warnings, and bright-red errors. Diagnostic labels are white with colored values, and spacing separates identity, delivery, timing, and other fields. Pending sends are orange, confirmed parts turquoise, and failed parts red. It contains no model reasoning. An answer record confirms generation; the following delivery entry confirms sending. Credentials are never passed to the model or logged.

The Discord log adds these diagnostics without additional Discord permissions:

- Connection, disconnect, ready, and resumed events, with time disconnected when known.
- Sender ID, DM channel ID, and incoming message ID on each turn; outgoing message IDs on successful sends. IDs are stored as strings to preserve precision. `log_message_id` links the same message to main processing diagnostics, with explicit start/end markers for delivery; see [message log boundaries](../current-operation/logs.md#message-ids-and-section-boundaries).
- Discord's message creation time and local handler receipt time, recorded before waiting for the previous turn. `receipt_delay_ms` compares those clocks; it is not a precise network measurement and can be negative if clocks disagree.
- `adapter_queue_ms`: waiting behind another Discord turn. `main_queue_ms`: waiting for main chat to pick up the request. `processing_ms`: local handling, including token counting, any rollover wait, and generation. `local_response_ms`: the complete local request, including main queue and connection overhead. These overlap; do not add all of them together.
- `send_ms` for each part and the complete send, plus `total_ms` from local receipt through successful answer delivery. Discord library retries/rate-limit waits are included in send time.
- Chunk count, each successful part's ID, and the failed part/number of confirmed earlier parts on failure. A failed request may still have reached Discord; no automatic resend is added.
- Error class, HTTP status, and Discord error code when provided. Exception bodies, request headers, credentials, and raw network packets are not dumped.
- `heartbeat_ms` snapshots on ready/resume/disconnect and accepted incoming messages. This is Gateway heartbeat round-trip latency, not message delivery latency. Unavailable readings are `null`; there is no continuous heartbeat log spam.

Discord event payloads preserve timestamped names and JSON fields/records as original bytes in SQLite; server/model events use their own stream. The live view formats these without changing the saved evidence; see [log colors and reading saved logs](../current-operation/logs.md). Restart main chat and reconnect Discord after code updates so both processes use the same local request format. The separate Reasoning terminal and local diagnostic records contain reasoning; main chat and the Discord log do not display it.

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
Restart the adapter after updating code to enable this endpoint. Adapter startup and
orderly exit notify main chat to refresh the setup datasheet and its existing Obsidian
copy. Owned background-process exit also triggers refresh. The sheet records process
presence, not Discord network health; transient reconnects do not rewrite it. The
status endpoint does not expose a model tool.

Discord display names are carried as separate sender metadata over the local socket, never parsed from message text. Saved names are retained after initial capture; legacy generated numeric labels are filled on the next DM. Numeric Discord IDs and permanent contact UUIDs still identify senders and route conversations. Name capture occurs when a message arrives. See [name preservation and fallback rules](../current-operation/contacts.md).

## DM access control

The saved owner can use `/ddm on`, `/ddm off`, or `/ddm` (show current setting)
in terminal or a Discord DM. `/help` lists these commands. Off silently ignores
non-owner DMs; the configured owner account remains admitted. This controls
Marionette's processing and replies, not whether Discord lets someone send a DM.

The setting is stored atomically with mode 600 in `data/discord/access.json`
(`allow_other_dms`, a JSON boolean), under `MARIONETTE_DATA_DIR` when overridden.
It survives application/Discord restarts and memory reset. A missing file preserves
the existing open-access default; an unreadable or invalid file blocks non-owners.
The owner can repair the setting with `/ddm on` or `/ddm off`. No credential edits
or bot restart are needed after a command. Setup snapshots and their existing
Obsidian copies refresh after the command.

The adapter checks before reading/logging message content and again after its
queue wait. Main chat checks the saved owner mapping before registering contacts
or processing a queued DM. Already admitted/in-progress work can finish; turning
off does not erase earlier records or recall replies. Re-enabling does not fetch
messages ignored while off. Owner authorization uses the saved UUID/account
mapping, never a display name or Discord server role. The admission policy is
shared by both foreground and background Discord launches.

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

Connections and requests merges Discord connection/delivery events with the model
server view using separate stream cursors. Reserved diagnostic event-ID blocks
are not global arrival order, so the combined view does not promise strict global
chronology. Discord transcript rows remain in their original stream and main chat;
they are not duplicated into this connection view. Existing Discord disk durability
and diagnostic RAM retention are unchanged.
