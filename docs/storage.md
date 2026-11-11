# Conversation and diagnostic storage

Marionette stores new sessions in **`data/conversations/marionette.sqlite3`**. Python's standard-library `sqlite3` module provides local storage without a database service, account, or new pip dependency. `storage.py` is the small storage interface; `storage.sh` is the operator command. Character entries remain Markdown under `data/characters/` with the 1,375-character limit. Identities remain JSON under `data/identities/`.

## What is stored

Schema version 1 has three tables:

| Table | Contents |
|---|---|
| `sessions` | Launch UUID, UTC start and clean end timestamps. An absent end can mean still running or interrupted. |
| `messages` | Session/correlation/conversation IDs, person UUID, source and sender ID, UTC receipt timestamp, role, kind, content, and status. Kinds distinguish incoming text, reasoning, final answers, and command notices. |
| `events` | Global event number, session UUID, UTC receipt timestamp, stream, routing category, explicit message correlation ID when present, and original output bytes. |

Messages are recorded independently of the context window. User input is saved before processing; streamed reasoning is collected and saved on completion or interruption, while the terminal stream preserves output already displayed. Only a valid final answer is saved as an answer. A received input is not proof of successful generation or delivery. Discord delivery outcomes remain separate events. Tool requests/results, token usage, sampling, model loading, cache operations, and other technical details remain diagnostic events, not extra conversation messages.

Events preserve the terminal output (including display codes), Discord output (JSON records and connection events), and every diagnostic line. Original bytes are BLOBs, including invalid UTF-8, control bytes, and partial final lines. They need no Base64 expansion. Server/model categories select views; shared/unknown/error events are stored once and appear in both. Exact terminal/runtime/Discord evidence still repeats some conversation content. This is not complete deduplication or compression, and no size reduction is promised.

Indexes support session-order reads, explicit message IDs, person/time lookup, and conversation lookup. No full-text search index is enabled yet. Source fields and UUIDs carry provenance; receipt ordering is not exact runtime execution ordering. Raw runtime lines are not assigned a message ID based on proximity.

## Behavior and lifecycle

The launch commands and four-terminal arrangement stay the same. Two diagnostic windows read committed rows and apply existing formatting/colors. The Discord connection attaches to the database/session identified by the running main chat. Closing a viewer does not stop recording. `script` still supplies the terminal recorder's PTY, but outputs to SQLite through a pipe rather than saving a text file. Main chat continues to display all interfaces while keeping model histories separate.

SQLite uses WAL mode, foreign keys, a 10-second lock timeout, and `synchronous=FULL`. Each write is a short transaction. The database is created with mode 600; launchers use a private umask. Keep it on a local filesystem. WAL and SHM sidecars may exist while open; never delete them or copy only the live main file as a backup. Read viewers do not hold a long transaction. Storage failures are reported rather than silently falling back to unrecorded text output. Records not yet received/committed can be lost on forced termination. A failed write or interrupted session is not a successful saved conversation.

Normal shutdown drains main-chat recorders before marking the session ended. Discord may append its final disconnect events afterward. A forced kill can leave no end timestamp; live diagnostic windows also watch the main launcher's PID. Stop both main chat and Discord before maintenance or a complete final-session export.

Saved data is **not automatically loaded into model context**. Restart still begins fresh conversation histories; `/clear` clears only the originating active history and preserves stored records. Character notes remain automatically supplied. There is no new model log reader, memory search, automatic resume, or retention cap.

## View and export

From the checkout, list sessions and substitute the desired UUID below:

```bash
./scripts/native-linux/storage.sh sessions
./scripts/native-linux/storage.sh view SESSION_UUID model | python src/marionette/log_view.py diagnostic
./scripts/native-linux/storage.sh view SESSION_UUID server | python src/marionette/log_view.py diagnostic
./scripts/native-linux/storage.sh view SESSION_UUID discord | python src/marionette/log_view.py discord
```

Add `--follow` after the view name to follow a running session. `terminal` exports the exact displayed output bytes; those contain active terminal control codes. The diagnostic viewers escape original control bytes for safe reading.

Text exports preserve compatibility with the existing [message snapshot utility](log-snapshots.md). Export related views under the same prefix:

```bash
umask 077
mkdir -p data/conversations/exports
./scripts/native-linux/storage.sh view SESSION_UUID server > data/conversations/exports/SESSION-server.txt
./scripts/native-linux/storage.sh view SESSION_UUID model > data/conversations/exports/SESSION-model.txt
./scripts/native-linux/storage.sh view SESSION_UUID discord > data/conversations/exports/SESSION-discord.txt
```

These are optional operator exports, not additional automatically saved logs. The snapshot utility still reads these text exports; it is not connected to the model.

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

This uses SQLite's backup API (including committed WAL data) and checks database integrity. The command is also safe for a consistent database snapshot while writers run, although later events are naturally excluded. Move the backup to separate private storage for protection against disk loss.

Restore while both applications are stopped: move the current database and any matching WAL/SHM files aside together, copy the verified backup to `data/conversations/marionette.sqlite3`, and set permissions to 600. Do not combine sidecars from different database copies. Restoring this database restores the saved records, not automatic model history. Keep matching identities/characters when restoring a complete personal state.

Synthetic tests verify same-version SQLite backup restoration and SQL export/import into a fresh SQLite file, including raw bytes, messages, IDs, and timestamps. **Migration to a different database engine is not implemented or verified.** Unexpected schema versions fail explicitly; there is no silent reset. No old-text import is implemented.

## Fresh personal-data start

The authorized November 11, 2026 reset removes previous local conversation/log files (including their archives), other identities, character notes, and stale session state. It preserves the owner UUID, Phat name and Discord link, credentials, application/configuration, models, runtimes, documentation, and historical development reports. Phat's Markdown restarts as `# Phat`; the database starts with no sessions/messages/events. This is a one-time reset, not automatic behavior on launch. File deletion is not a secure disk-erasure guarantee and does not delete Discord's hosted message history or backups elsewhere.

SQLite is [public domain](https://sqlite.org/copyright.html). Design references: [WAL](https://sqlite.org/wal.html) and [Python SQLite interface/backup](https://docs.python.org/3/library/sqlite3.html). Installed versions are recorded in [licenses](licenses.md).

## Verification of this change

On November 11, 2026, an isolated normal-launcher GPU check used synthetic profiles and a separate database. The unchanged Q4 model answered `2 + 2` with `4`; input, reasoning, and answer were stored separately, 7,806 diagnostic records and the terminal stream were saved, integrity checking passed, and the session/server ended cleanly. All 106 automated checks passed (93 core and 13 mocked Discord), including Ctrl+C shutdown with recorder draining. The existing message snapshot utility successfully read exports from the GPU session. Mocked Discord integration verifies attachment, reconnection, metadata/delivery events, local reasoning, and answers-only delivery without a live Discord login. These checks establish recording and basic functionality, not long-session reliability, answer quality, or a performance improvement.
