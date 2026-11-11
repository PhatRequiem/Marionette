# Rolling diagnostic retention

New writes use **20 MB logical batches** and a **500 MB combined diagnostic
payload budget** inside SQLite. MB means decimal bytes: 20,000,000 and
500,000,000. There are no rotated text files. Server and model windows remain
filtered views of the same stored diagnostic events; shared events count once.

`retention.py` implements the policy behind `Store.event`. It is not a model tool.
The log snapshot reader remains disconnected from her.

## What rolls out

Only `events` rows with `stream='diagnostic'` enter batches. A complete raw event
is assigned to the current batch, or a new batch if it would cross 20 MB. Event,
message, request, tool, and session IDs never reset when a batch changes. Event
IDs use a persistent sequence so deleting older rows cannot reuse an ID.

After each diagnostic insert, the oldest closed batches are deleted until the
retained raw diagnostic payload is at most 500 MB. Cleanup crosses session
boundaries. Whole-event preservation takes priority: an individual event larger
than 20 MB occupies its own oversized batch, and a single active event larger
than 500 MB can temporarily exceed the budget until a subsequent event closes
that batch. No event is split or silently truncated in the ordinary log.

Structured `messages`, session records, terminal transcripts, and the Discord
stream are preserved. The Discord stream contains both transcripts and transport
diagnostics and is outside this diagnostic-only cleanup policy. It can still
grow, as can conversation storage.

**500 MB is not a total SQLite file-size limit.** Database pages/indexes, WAL,
conversations, Discord/terminal output, retained errors, and the recent-context
buffer use additional space. Deleted pages are reused by SQLite; the main file
need not shrink. No live `VACUUM`, external part files, or compression is added.
Backup/export covers the whole database; see [storage](storage.md).

Live viewers continue by monotonically increasing event ID across cleanup. A
viewer which falls behind retention, or a later export, can only read events
still retained; it does not resurrect expired history. Event numbers keep their
original values and gaps are expected.

## Last 20 failures

The latest **20 distinct recognized failures**, across sessions and restarts,
are protected separately from the rolling events. Each has:

- Original event IDs, timestamps, session/message/request/tool IDs when present,
  and the detected component.
- Up to **20 preceding and 20 following diagnostic events** from the same session,
  in global receipt order. Discord connection events also participate; JSON
  conversation transcripts and terminal output do not.
- The original failure event and any explicitly related propagated error events.
- `before_count`, remaining following-event count, and collection state.

The error and preceding evidence are persisted in the **same transaction** as
the incoming event, before batch pruning. Following events are appended as they
arrive. Reopening a store in the same session can finish a pending window; a
forced process exit leaves a durable, visibly unfinished window. Clean session
end marks pending windows `incomplete` rather than claiming full evidence.

`collecting` means more following events are needed. `complete` means all 20
following events were collected; inspect `before_count` too, because a failure
near session start can have fewer than 20 preceding events. `incomplete` means
the session ended before the following window filled. No cross-session events
are appended to an old window.

Recognized failures are runtime severity `E` lines; tagged model-request,
tool-call, message, local Discord bridge, cache-preparation and client failure
records; and Discord chunk/turn failures. Warnings and error words inside input,
answers, or reasoning do not create failures. A tool returning an error as normal
text is not automatically classified as a failure: `returned` still describes
control flow, not domain success.

Parent/bridge errors join a related message's latest matching failure while its
window is collecting; model errors can join their failed child tool, and Discord
chunk/turn failures can join their message's delivery failure. Separate tool
executions remain separate failures. Untagged runtime errors cannot reliably be
linked to tagged client errors and remain distinct. Grouping does not extend the
20-following-event window indefinitely. Related errors inside that original
window are labeled `error` instead of `after`.

Overlapping windows share one copy of each protected event. Removing the 21st-oldest
failure removes only evidence no longer referenced by another retained failure.
The rolling copy may be deleted without affecting the protected copy.

To bound unusual evidence, each protected/recent-context event stores at most
**1 MB** of its original bytes, with `original_bytes` and `truncated` metadata.
This never changes the ordinary diagnostic event. Truncated evidence is clearly
marked by the inspector and excluded from structured snapshot field extraction.
The recent-context ring holds 20 events; retained windows hold at most 41 events
per failure before overlap sharing. These stores are outside the 500 MB budget.

## Inspect it

After restarting main chat so the schema is migrated:

```bash
./scripts/native-linux/storage.sh retention
./scripts/native-linux/storage.sh errors
./scripts/native-linux/storage.sh error FAILURE_ID
```

`retention` reports the persisted policy, retained raw diagnostic bytes, protected
evidence bytes, and recent-context bytes. `errors` lists failure IDs, correlation
fields, timestamps, and completeness information. `error` prints a selected
failure and its evidence with original event numbers, relation labels, truncation
metadata, and escaped diagnostic formatting. These are operator-only reads.

The [snapshot utility](log-snapshots.md) can read current and protected diagnostic
events directly using `--database` and `--session`. It deduplicates their shared
copies and continues to enforce conversation scope. If the original scope marker
expired, a matching stored message can establish that scope. Missing boundaries
still produce an incomplete snapshot; a retained window is not a complete
conversation or complete message trace. Raw untagged surrounding events are
available through `storage.sh error`, not inferred as belonging to a message by
the structured snapshot reader.

## Migration and recovery

Restart main chat and reconnect Discord to activate this policy. Do not run old
writers against the upgraded database. `Store` transactionally migrates schema 1
to schema 2 on opening. It preserves original IDs/content, assigns historical
diagnostics to batches, reconstructs retained failures/windows from existing
records, and initializes the persistent event sequence. Migration itself does
not prune; the next diagnostic write enforces the budget. Large existing stores
can take time to scan. A failed migration rolls back; there is no silent reset.

Schema 2 adds batch metadata, policy/sequence state, failure records, shared
error evidence, evidence membership, and a recent-context ring. Backup and SQL
export include all of these. The defaults are stored once in `retention_state`;
opening another connection does not reset them. There is no model-facing policy
control or new dependency.

Tests use separate synthetic databases and small budgets to exercise frequent
rotation, preserved transcripts, concurrent writers, viewer continuity, latest-20
retention, overlapping/grouped errors, partial windows, an abrupt process exit,
transaction rollback, schema-1 migration and rollback, same-version backup
restore, SQL round-trip, and snapshot lookup after original events expire.
A separate default-size check wrote synthetic 20 MB events and verified exactly
25 batches/500 MB remained, the old error survived in protected evidence, and
SQLite integrity passed. Cross-database-engine migration and multi-year operation
remain unverified. No personal database was modified during these checks.

Final verification: **107 core checks and 13 mocked Discord checks passed**.
A synthetic 10,000-event recording check retained every row and kept the recent
context ring at 20 entries. These are isolated functional checks, not a claim of
five-year reliability or live-model performance. Restart/reconnect is required
to activate the new writer and migrate the personal database.
