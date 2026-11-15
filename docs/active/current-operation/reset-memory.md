# Reset memory from chat

Send **`/resetmemory`** in the main terminal, desktop puppet input, or a one-to-one Discord DM. Only the saved owner contact may run it. Discord authorization resolves the sending account against the saved owner mapping; typing an owner name in a message does not grant access. The desktop is a private same-OS-user interface that resolves the saved owner server-side. The local terminal profile selector remains identification, not a secure login.

This is an application command, processed before model inference. It does not depend on the model agreeing to erase memory. `/clear` still clears only the originating conversation history and preserves saved memory and logs. There is no confirmation prompt for `/resetmemory`. Non-owners receive: “Access Denied”

## What it resets

- All terminal and Discord model histories, pending preparation, soul name and personal description, and previous soul revisions.
- All contact notes, including the owner's, and all other contact profiles. Only the owner's existing UUID, Discord account ID links, and owner status survive from the old profile. Its display name becomes the neutral label `Owner` because the schema requires a name. Preferred name, timezone and creation time become null; the save sets a fresh update timestamp. Other account links and extra fields are removed. Terminal access stays enabled for owner operation.
- Saved conversation messages, old sessions, logs, protected error windows, and the recorder's RAM buffer.
- Personal content in the [conversation vault](../setup-and-maintenance/conversation-vault.md), including generated pages, annotations and mirrored documentation. Every existing folder and the complete `.obsidian/` settings, installed plugins and connection credentials are preserved. Source documentation can be mirrored again.
- Local memory backups, exports, and revision copies in the documented memory directories, including legacy directories. No new backup is made.

The soul UUID, owner UUID and authorization mapping, tools, and existing directory tree are preserved. Reset removes memory files, leaving empty directories in place, including backup and legacy folders. Tool registrations stay present; adapters holding old soul or contact notes are rebound to cleared memory. Configuration, credentials, model weights, installed environments, and source documentation are preserved. Discord-hosted messages and external backups are not deleted. Existing terminal scrollback is not erased. This is a logical reset, not secure erasure of SQLite free pages, WAL bytes, or GPU/RAM allocations.

## Live behavior and safety

The main turn lock waits for pending preparation and serializes the reset with generation. Messages from the old reset generation are discarded rather than replayed into fresh memory. Queued terminal lines, partial input, and unread interactive keystrokes are discarded at the reset boundaries; type the next message after the success response. Discord remains connected and the model process remains loaded. Transport duplicate-message watermarks remain active so replayed Discord events do not restore old conversations. The application prepares an empty conversation prefix with its tools and application guidance still registered; no old messages are submitted to the next generation.

The live database and its WAL/SHM files stay open. A transaction deletes old payloads and advances a private reset generation. The current session ID and monotonically allocated event IDs remain valid so launchers and live viewers continue working; its start timestamp is refreshed. Reset completion and subsequent activity create new log records, so the running database is not expected to stay empty.

The desktop client clears its current draft and reply bubble when it observes a reset or session change, and rechecks the session/generation before displaying a received answer. Pending desktop inputs from the old generation are rejected by the same queue boundary. Its UI text is RAM-only and is not a second memory store.

Ordered markers in the diagnostic and terminal streams drain buffered old bytes and acknowledge the boundary. Stale terminal/Discord writers cannot save payloads until crossing the new boundary. Discord input/answer payload logging occurs under the same turn lock; delayed connection handlers log transport metadata only. The diagnostic recorder discards its old RAM and protected errors; even an interrupted reset cannot save the old generation at shutdown. Discord synchronizes its stream on reset completion or the next fresh message. The ordinary 500 MB / 20 MB RAM retention and latest-20 error-window policy is unchanged.

The command refuses symlinked memory paths and logs outside the active data directory. Such alternate configurations require an operator reset. The cleared owner registry and blank soul are written atomically while keeping both permanent IDs. A reset is not an atomic transaction across all JSON/Markdown files and SQLite; a filesystem failure can leave a partial reset.

Reset refuses configured alternate Scarecrow vault locations before changing personal data, even when the connector is disabled. An operator must review and clear those memory copies separately; reset never deletes arbitrary configured folders.

## Completion and failure recovery

Before changing saved memory, reset writes `memory-reset-incomplete.json` in the active data directory. This contains only reset status, never a memory backup. It remains until the empty prefix is prepared, both recorders acknowledge the new boundary, and verification confirms the owner profile, soul UUID, tool registrations, folders, and cleared memory files/database records. The current live session is retained as described above.

A failure leaves chat blocked and the marker in place. Normal startup and vault export refuse an incomplete reset; restarting alone is not recovery. Stop main chat and Discord cleanly, let recorders drain, and follow the [stopped maintenance reset](../../../AGENTS.md#operator-instruction-reset-memory) while holding its locks. Verify the full reset scope, including cleared owner details and unchanged IDs, Discord links and owner status, before removing the marker. Leave the application stopped unless a restart was requested. An interruption after a successful wipe can conservatively leave the marker behind and require the same verification.

Synthetic regression tests cover both command sources with real recorder subprocesses, cleared owner details with UUID/Discord/owner authorization retained after reloading the registry, folder and tool preservation, erased backups, a delayed Discord handler crossing reset, queued/partial terminal input, and startup/export refusal after a preparation failure. They do not establish power-loss durability or model answer quality. No real profiles are used by those tests.
