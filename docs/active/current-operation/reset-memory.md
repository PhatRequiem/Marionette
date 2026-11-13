# Reset memory from chat

Send **`/resetmemory`** in the main terminal or a one-to-one Discord DM. Only the saved owner contact may run it. Discord authorization resolves the sending account against the saved owner mapping; typing an owner name in a message does not grant access. The local terminal profile selector remains identification, not a secure login.

This is an application command, processed before model inference. It does not depend on the model agreeing to erase memory. `/clear` still clears only the originating conversation history and preserves saved memory and logs. There is no confirmation prompt for `/resetmemory`. Non-owners receive: “Access Denied”

## What it resets

- All terminal and Discord model histories, pending preparation, soul name and personal description, and previous soul revisions.
- All contact notes and all contacts except Phat. Phat retains the same contact UUID, name, linked Discord accounts, and owner status; other personal fields are cleared.
- Saved conversation messages, old sessions, logs, protected error windows, and the recorder's RAM buffer.
- The entire [conversation vault](../setup-and-maintenance/conversation-vault.md), including generated pages, annotations and Obsidian settings.
- Local memory backups, exports, and revision copies in the documented memory directories, including legacy directories. No new backup is made.

The soul UUID is preserved. Configuration, credentials, model weights, installed environments, and documentation are preserved. Discord-hosted messages and external backups are not deleted. Existing terminal scrollback is not erased. This is a logical reset, not secure erasure of SQLite free pages, WAL bytes, or GPU/RAM allocations.

## Live behavior and safety

The main turn lock waits for pending preparation and serializes the reset with generation. New messages from the old reset generation are discarded rather than replayed into fresh memory. Discord remains connected and the model process remains loaded. Transport duplicate-message watermarks remain active so replayed Discord events do not restore old conversations. The application prepares an empty conversation prefix; no old messages are submitted to the next generation.

The live database and its WAL/SHM files stay open. A transaction deletes old payloads and advances a private reset generation. The current session ID and monotonically allocated event IDs remain valid so launchers and live viewers continue working; its start timestamp is refreshed. Reset completion and subsequent activity create new log records, so the running database is not expected to stay empty.

Ordered markers in the diagnostic and terminal streams drain buffered old bytes and acknowledge the boundary. Stale terminal/Discord writers cannot save payloads until crossing the new boundary. The diagnostic recorder discards its old RAM and protected errors; even an interrupted reset cannot save the old generation at shutdown. Discord synchronizes its stream on reset completion or the next fresh message. The ordinary 500 MB / 20 MB RAM retention and latest-20 error-window policy is unchanged.

The command refuses symlinked memory paths and logs outside the active data directory. Such alternate configurations require an operator reset. A failure after reset begins blocks further turns instead of claiming success; inspect the error and restart before continuing. Neither IDs nor current identity files are deliberately deleted before their blank replacements are written atomically. A reset is not an atomic transaction across all JSON/Markdown files and SQLite; a filesystem failure can leave a partial reset.

## Verification

Synthetic checks cover owner commands from terminal and Discord, non-owner rejection, arbitrary stream-marker chunk boundaries, stale disk writers, old RAM suppression on interrupted reset, ID/account preservation, blank soul, local-copy deletion, and normal shutdown after reset. A launcher test runs a conversation, resets, continues chatting using the same server process, and verifies that old conversation text does not return after recorder shutdown. Existing RAM tests still verify no routine diagnostic payload writes and orderly shutdown saving.

These tests establish application behavior, not answer quality or long-session reliability. Mocked Discord tests do not establish live Discord delivery. No private conversation is used as test data.

A real Q4 GPU smoke test in temporary synthetic storage generated before and after `/resetmemory` with one model load, retained only the post-reset conversation, and shut down with SQLite integrity intact. The personal instance was left stopped and no live Discord message was sent. This establishes loading and short functional generation, not broader quality, performance, or long-session reliability.

Verification: 134 core regression checks and 14 mocked Discord checks passed, plus the isolated live GPU reset test.
