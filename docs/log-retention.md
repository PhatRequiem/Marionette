# Rolling diagnostics in RAM

**Policy:** routine diagnostics live in the **existing recorder process's RAM**,
with a **500 MB raw-event rolling budget in 20 MB batches**. No new helper or
watchdog process is added. Conversations remain durable in SQLite. Model log access remains disabled.

MB means decimal bytes: 500,000,000 and 20,000,000. `ram_logs.py` owns the live
buffer and shutdown save; `retention.py` supplies batch/error-window rules.
SQLite `:memory:` is used as a RAM data structure containing raw BLOB events and
indexes; its database and temporary storage are in memory, with no database/WAL
file. This does **not** mean per-event writes to the on-disk SQLite database.

The [project rules](../AGENTS.md#diagnostic-ram-policy) and regression tests make
this an explicit architectural policy. Changing it requires a deliberate decision.

## Rolling buffer

The existing diagnostic capture command feeds the RAM buffer instead of the
on-disk event writer. A complete event starts a new batch if it would cross
20 MB. Oldest closed batches roll out when the retained raw payload exceeds
500 MB. Server and model windows are views of the same events; shared records
count once.

An individual event larger than 20 MB can occupy a larger batch without being
split, provided it fits within 500 MB. An event larger than the entire RAM budget
is rejected with an error, and the recorder attempts to save its existing buffer
on exit. Payload limits are not a strict process-RSS limit: SQLite indexes/free
pages, Python objects, temporary copies, and protected error evidence need
additional RAM. Old batches are discarded, not periodically written to disk.

Structured conversation messages, terminal transcripts, and the Discord stream
continue using the on-disk database. Those are outside the routine diagnostic
RAM buffer and can still generate disk writes. This change reduces diagnostic
writes; it does not promise zero SSD activity or a measured endurance gain.

## Live views and IDs

The two diagnostic windows query a private local socket served by a thread in
the **existing recorder process**. No additional process is launched. Linux
abstract Unix sockets avoid stale socket files; the server checks `SO_PEERCRED`
and accepts only the same OS user. Queries are read-only operator views, not a
model tool. Closing a viewer does not stop recording.

The recorder reserves event-ID blocks of 65,536 using a small SQLite metadata
transaction, then allocates IDs in RAM. Routine diagnostic payloads are not
persisted by those reservations. This preserves unique IDs while the existing
terminal/Discord writers use the same database. Unused reserved IDs create gaps.
IDs preserve order **within the diagnostic stream**; they no longer imply global
receipt order across diagnostic, terminal, and Discord streams. Use timestamps
and correlation IDs when comparing streams.

Views follow the live RAM buffer and fall back to saved SQLite rows once the
recorder exits. IDs and receipt timestamps do not change when saved. A viewer
that falls behind can miss rolled-out events. Saved-log commands see current
RAM diagnostics only after shutdown saving.

## Latest 20 errors with context

The RAM buffer retains the latest **20 recognized diagnostic failures**, with
up to **20 diagnostic events before and 20 after** each, independently of batch
rollover. Related parent/request/tool failures are grouped when their explicit
IDs establish the relationship. Separate executions and untagged runtime errors
remain separate; words such as “failed” inside conversation prose do not trigger
an error record. See `retention.failure_identity` for recognized event types.

Overlapping windows share evidence. Each protected event retains up to 1 MB, with
`original_bytes` and `truncated` metadata when limited; the ordinary rolling event
is not truncated. A failure near startup may have fewer than 20 preceding events.
`collecting` means more following events are needed; `complete` means 20 following
events arrived. Shutdown marks unfinished windows `incomplete`.

These **new diagnostic error windows are also in RAM until shutdown**. The
existing saved failures remain on disk while the session runs; Discord transport
failures still use that durable path. On shutdown, new RAM windows are merged
with saved failures, retaining the latest 20 by receipt timestamp and deleting
unreferenced evidence. A diagnostic window contains diagnostic events; it does
not infer interleaving with the separately captured Discord stream.

## Shutdown saving and limits

On producer EOF, normal application shutdown, Python exception unwinding, or
orderly recorder SIGTERM, the recorder attempts one atomic SQLite transaction:

1. Save the surviving diagnostic batches with original IDs, bytes, and timestamps.
2. Merge protected error windows, including evidence whose ordinary batch expired.
3. Enforce the existing 500 MB saved-diagnostic payload budget across shutdowns.

Ctrl+C continues to be handled by the producer; the recorder ignores it and drains
through EOF before saving. The launcher waits for recording to finish before
marking the session ended. A failed save rolls back and reports failure; it does
not claim success or silently fall back to per-event disk writes. Save time can
increase with the buffer size. Conversation persistence remains independent.

**SIGKILL or OOM killing the recorder, an OS crash, and power loss can lose all
unsaved RAM diagnostics and new error windows.** There is no crash-monitor helper,
periodic checkpoint, or guarantee that every abnormal termination executes cleanup.
If only the producer exits and the existing pipe closes, EOF can still save the
buffer. A descendant retaining the pipe can delay EOF. These limits are intentional
and must stay visible when future versions change shutdown behavior.

The saved 500 MB payload budget does not cap the entire database file. Conversation
records, terminal/Discord output, protected evidence, indexes, and WAL need extra
space. SQLite reuses deleted pages; the file need not shrink. No live `VACUUM`,
compression, or rotated text files are added. Saved data continues using schema 2;
there is no new on-disk schema migration for this RAM change.

## Operator commands

Restart main chat and reconnect Discord to use the new recorder. Existing saved
records are preserved under their existing rolling retention policy.

```bash
./scripts/native-linux/storage.sh retention
./scripts/native-linux/storage.sh errors
./scripts/native-linux/storage.sh error FAILURE_ID
```

`retention` reports saved sizes plus `live_ram` policy, size, session, and failure
count when the recorder is available. `errors` and `error` inspect **saved** failures;
new RAM failures appear there after shutdown saving. The live diagnostic windows
show errors as they occur. Log inspection remains operator-only.

Use [SQLite backup/export](storage.md) for already saved evidence and conversations.
A backup while running does not include the unsaved RAM buffer. Stop cleanly first
for a complete snapshot of retained diagnostics. Restoring a backup restores saved
rows, not a running RAM buffer or model history.

## Verification and future regression guardrails

`tests/core/test_ram_logs.py` checks the exact default sizes, no routine payload or
recent-context rows on disk before saving, whole-batch expiry, latest-20 errors,
shutdown save with original IDs, atomic rollback/retry, backup restoration, live
views, ID reservation collisions, oversized-event rejection, EOF/SIGTERM saving,
and the documented loss on recorder SIGKILL. Existing launcher checks exercise
normal exit, Ctrl+C, failed child processes, recorder draining, and conversation
persistence. Tests use isolated databases and synthetic profiles only.

This is not a five-year reliability claim or a live-model performance benchmark.
The no-payload-writes and shutdown tests must remain in place when storage evolves.

Verification of the RAM change: **118 core checks and 13 mocked Discord checks
passed**. A separate actual-size test retained exactly 25 × 20 MB batches in RAM,
confirmed zero diagnostic/event-window rows on disk before shutdown, then saved
the 500 MB buffer and protected error evidence with SQLite integrity intact.
The synthetic database was removed; the user's running session was not changed.

## Explicit live memory reset

The owner-authorized [`/resetmemory`](reset-memory.md) command deliberately discards both saved logs and the recorder's RAM/error windows. It uses private generation markers and acknowledgments in existing capture processes; no helper process or periodic payload writes are added. Schema 4 adds reset-generation metadata. Event allocation remains monotonic and the active session ID is preserved for live viewers. Old-epoch writers and shutdown buffers cannot reinsert erased payloads. Ordinary rolling budgets, protected-error limits, and shutdown-save behavior remain unchanged. Tests include interrupted-boundary suppression, stale writer rejection, and a full launcher reset followed by shutdown.

Schema 5 adds searchable metadata columns and indexes to both retained events and
protected evidence. They follow their parent rows through eviction, shutdown saving
and reset; routine diagnostic metadata stays in the same in-memory recorder. The
500,000,000-byte budget still counts raw payload bytes, not SQLite/index overhead.
No additional payload writes, helper process or durability guarantee is introduced.
See [search metadata](storage.md#searchable-diagnostic-metadata-schema-5).
