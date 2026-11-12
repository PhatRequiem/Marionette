# Conversation and diagnostic storage

Marionette stores conversations and shutdown-saved diagnostics in **`data/conversations/marionette.sqlite3`**. Python's standard-library `sqlite3` module provides local storage without a database service, account, or new pip dependency. `storage.py` is the small storage interface; `storage.sh` is the operator command. Character entries remain Markdown under `data/contact_notes/` with the 1,375-character limit. Identities remain JSON under `data/contacts/`.

## What is stored

Schema version 5 retains these primary tables (introduced in version 1):

| Table | Contents |
|---|---|
| `sessions` | Launch UUID, UTC start and clean end timestamps. An absent end can mean still running or interrupted. |
| `messages` | Session/correlation/conversation IDs, contact UUID, source and sender ID, UTC receipt timestamp, role, kind, content, and status. Kinds distinguish incoming text, reasoning, final answers, and command notices. |
| `events` | Global event number, session UUID, UTC receipt timestamp, stream, routing category, explicit message correlation ID when present, and original output bytes. |

Messages are recorded independently of the context window. User input is saved before processing; streamed reasoning is collected and saved on completion or interruption, while the terminal stream preserves output already displayed. Only a valid final answer is saved as an answer. A received input is not proof of successful generation or delivery. Discord delivery outcomes remain separate events. Tool requests/results, token usage, sampling, model loading, cache operations, and other technical details remain diagnostic events, not extra conversation messages.

Events preserve the terminal output (including display codes), Discord output (JSON records and connection events), and the diagnostic events retained when the RAM recorder shuts down. Live routine diagnostics are not immediately persisted; see [RAM retention](log-retention.md). Original bytes are BLOBs, including invalid UTF-8, control bytes, and partial final lines. They need no Base64 expansion. Server/model categories select views; shared/unknown/error events are stored once and appear in both. Exact terminal/runtime/Discord evidence still repeats some conversation content. This is not complete deduplication or compression, and no size reduction is promised.

Indexes support session-order reads, explicit message IDs, person/time lookup, and conversation lookup. No full-text search index is enabled yet. Source fields and UUIDs carry provenance; diagnostic IDs are reserved in blocks, so numeric ordering across streams is not receipt order; use timestamps and correlation IDs. Raw runtime lines are not assigned a message ID based on proximity.

## Behavior and lifecycle

The launch commands and four-terminal arrangement stay the same. Two diagnostic windows read the existing recorder’s RAM buffer through a private same-user socket, then fall back to saved rows after exit, using existing formatting/colors. The Discord connection attaches to the database/session identified by the running main chat. Closing a viewer does not stop recording. `script` still supplies the terminal recorder's PTY, but outputs to SQLite through a pipe rather than saving a text file. Main chat continues to display all interfaces while keeping model histories separate.

SQLite uses WAL mode, foreign keys, a 10-second lock timeout, and `synchronous=FULL`. Conversation/terminal/Discord writes use short transactions. Routine diagnostics use RAM; the surviving buffer and error windows are saved in one shutdown transaction. The database is created with mode 600; launchers use a private umask. Keep it on a local filesystem. WAL and SHM sidecars may exist while open; never delete them or copy only the live main file as a backup. Read viewers do not hold a long transaction. Storage failures are reported rather than silently falling back to unrecorded text output. Records not yet received/committed can be lost on forced termination. A failed write or interrupted session is not a successful saved conversation.

Normal shutdown drains main-chat recorders and saves retained RAM diagnostics before marking the session ended. Discord may append its final disconnect events afterward. A forced kill can leave no end timestamp; unsaved diagnostics can be lost if the recorder is killed. Stop both main chat and Discord before maintenance or a complete final-session export.

Saved data is **not automatically loaded into model context**. Restart still begins fresh conversation histories; `/clear` clears only the originating active history and preserves stored records. Contact notes remain automatically supplied. There is no new model log reader, memory search, or automatic resume. [Rolling diagnostic retention](log-retention.md) preserves conversations while expiring older diagnostics.

Schema 2 also adds diagnostic batches, policy/sequence state, retained failures, shared error evidence, and a bounded recent-context ring. The [retention guide](log-retention.md) describes the 20 MB batches, 500 MB diagnostic payload budget, last 20 failures with surrounding events, and shutdown saving. Existing schema-1 databases upgrade through schema 2 to schema 3 transactionally; schema 3 renames the contact UUID column without changing retention.

## View and export

From the checkout, list sessions and substitute the desired UUID below:

```bash
./scripts/native-linux/storage.sh sessions
./scripts/native-linux/storage.sh view SESSION_UUID model | python src/marionette/log_view.py diagnostic
./scripts/native-linux/storage.sh view SESSION_UUID server | python src/marionette/log_view.py diagnostic
./scripts/native-linux/storage.sh view SESSION_UUID discord | python src/marionette/log_view.py discord
```

Add `--follow` after the view name to follow a running session. `terminal` exports the exact displayed output bytes; those contain active terminal control codes. The diagnostic viewers escape original control bytes for safe reading.

Export related human-readable views under the same prefix:

```bash
umask 077
mkdir -p data/conversations/exports
./scripts/native-linux/storage.sh view SESSION_UUID server > data/conversations/exports/SESSION-server.txt
./scripts/native-linux/storage.sh view SESSION_UUID model > data/conversations/exports/SESSION-model.txt
./scripts/native-linux/storage.sh view SESSION_UUID discord > data/conversations/exports/SESSION-discord.txt
```

These are optional operator exports, not additional automatically saved logs. Model log access is not enabled.

For a portable complete export including structured messages, schema, indexes, provenance, and exact BLOB bytes:

```bash
umask 077
./scripts/native-linux/storage.sh export > data/conversations/export.sql
```

The SQL dump uses one read transaction for a consistent snapshot. It can be imported into an empty SQLite database with Python's `sqlite3.Connection.executescript`. Treat an SQL dump as executable database instructions: import only trusted exports. UUIDs and timestamps are preserved. JSON identity records and Markdown characters must be backed up separately when preserving a complete personal-data state.

## Backup and restore

Stop main chat and Discord for a complete session boundary. Use a new destination; this command refuses to overwrite an existing file:

```bash
./scripts/native-linux/storage.sh backup data/conversations/backup.sqlite3
```

This uses SQLite's backup API (including committed WAL data, but not unsaved RAM diagnostics) and checks database integrity. The command is also safe for a consistent database snapshot while writers run, although later events are naturally excluded. Move the backup to separate private storage for protection against disk loss.

Restore while both applications are stopped: move the current database and any matching WAL/SHM files aside together, copy the verified backup to `data/conversations/marionette.sqlite3`, and set permissions to 600. Do not combine sidecars from different database copies. Restoring this database restores the saved records, not automatic model history. Keep matching contact profiles/notes when restoring a complete personal state.

Synthetic tests verify same-version SQLite backup restoration and SQL export/import into a fresh SQLite file, including raw bytes, messages, IDs, and timestamps. **Migration to a different database engine is not implemented or verified.** Unexpected schema versions fail explicitly; there is no silent reset. No old-text import is implemented.

## Fresh personal-data start

Ask the development agent to **reset memory** using the [operator instruction](../AGENTS.md#operator-instruction-reset-memory). This clears local conversations, logs, souls, other profiles, self-description revisions, and project-local copies of those memories. Both permanent UUIDs and Phat's name, linked Discord account, and owner status remain. The self name and sheet start blank. The application stays installed and stopped; ordinary restart does not perform this wipe.

This is not a model tool or runtime slash command. Discord-hosted messages and backups outside the project are outside its scope. Local deletion is not a secure disk-erasure guarantee. See the operator instruction for the complete preservation and shutdown requirements.

SQLite is [public domain](https://sqlite.org/copyright.html). Design references: [WAL](https://sqlite.org/wal.html) and [Python SQLite interface/backup](https://docs.python.org/3/library/sqlite3.html). Installed versions are recorded in [licenses](licenses.md).

## Verification of this change

On November 11, 2026, an isolated normal-launcher GPU check used synthetic profiles and a separate database. The unchanged Q4 model answered `2 + 2` with `4`; input, reasoning, and answer were stored separately, 7,806 diagnostic records and the terminal stream were saved, integrity checking passed, and the session/server ended cleanly. All 106 automated checks passed (93 core and 13 mocked Discord), including Ctrl+C shutdown with recorder draining. The then-existing message snapshot utility successfully read exports from the GPU session; that utility has since been removed. Mocked Discord integration verifies attachment, reconnection, metadata/delivery events, local reasoning, and answers-only delivery without a live Discord login. These checks establish recording and basic functionality, not long-session reliability, answer quality, or a performance improvement.

## Contact UUID schema migration

Writable opens upgrade conversation databases to schema 3 transactionally: `messages.person_uuid` becomes `messages.contact_uuid`, with the corresponding index renamed. Existing messages, IDs, and raw diagnostic payloads are preserved. Read-only inspection still accepts schemas 1 and 2. Retention behavior and RAM budgets are unchanged. Synthetic tests verify the column migration and reopen; this is SQLite schema migration, not cross-database migration.

Schema 4 adds one private `memory_epoch` metadata row for coordinated live resets. It migrates transactionally from schema 3 without rewriting existing messages. Read-only inspection accepts schemas 1–5. See [live reset](reset-memory.md) for deletion boundaries and retained active session metadata.


## Searchable diagnostic metadata (schema 5)

Writable opens migrate schemas 1–4 transactionally to schema 5, including the
recorder's in-memory SQLite store. Original payload bytes and IDs are preserved.
Migration scans existing events and protected evidence once to backfill recognized
metadata; large retained databases can therefore take longer to open the first time.
Read-only tools accept older versions without upgrading them. Do not run an older
writer against a schema-5 database.

Both `events` and `error_evidence` have nullable text columns:

| Column | Meaning |
|---|---|
| `event_type` | Recognized envelope type, e.g. `model_usage`, `tool_identity`, `processing_end`, `discord_chunk_sent`, `discord_delivery_end` |
| `request_number`, `tool_number` | Original per-message ordinals, e.g. `01`; use session + message ID to scope them |
| `tool_name`, `protocol_tool_call_id` | Name and original protocol ID from the explicit tool-identity record |
| `contact_uuid`, `display_name`, `preferred_name` | Identity as recorded in the sender-identity event; names are labels, not unique keys |
| `conversation_id` | Explicit conversation-selection marker or Discord sender envelope |
| `sender_id`, `channel_id`, `outgoing_message_id` | Explicit identity/delivery envelope values where present |

`log_metadata.py` defines the recognized types. Unknown/raw runtime events retain
null metadata, rather than gaining guessed message ownership. Conversation prose
and JSON transcript content are never scanned for embedded metadata. Truncated
protected evidence is left unclassified. Metadata is not copied from neighboring
records, so most diagnostic events obtain conversation/contact scope through a join
on `(session_id, message_id)` to `messages`, not their own `conversation_id` column.

Indexes cover session/type/time, session/message/request/tool, session/tool name,
message correlation and sender/time, alongside the existing contact/time indexes.
For example, read recorded model usage for one session:

```sql
SELECT id, message_id, recorded_at, raw
FROM events
WHERE session_id = :session AND event_type = 'model_usage'
ORDER BY recorded_at, id;
```

Protected evidence can be searched with the same metadata fields, using
`event_id` instead of `id`. Deduplicate by event ID when combining both sources.
A missing record can mean expired evidence, not proof that the event never happened.
Names remain in the contact registry and searchable retained sender-identity diagnostics;
resolve names to permanent contact UUIDs and handle ambiguity before searching.
Historical names are not guaranteed after diagnostic expiry. No full-text index,
natural-language lookup, live model access, or new setup evidence collector is added.
A future model-facing lookup interface would require separate implementation; the
former snapshot utilities have been removed. The [operator handler](log-queries.md)
now accepts bounded request forms without connecting retrieval to the model.

Synthetic checks verify schema-4 backfill, indexed lookup, raw-byte/ID preservation,
protected evidence after rolling eviction, shutdown saving, and reset deletion.
The storage suite separately checks same-version backup restore and SQL export/import;
these are SQLite tests, not cross-engine migration verification.
