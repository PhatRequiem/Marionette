# Reading the logs

See the [log glossary](log-glossary.md) for short definitions of IDs, fields and event types.

Conversations and logs are stored in `data/conversations/marionette.sqlite3`. Contact-note Markdown and identity JSON remain separate. See [storage](storage.md) for schema, provenance, exact-byte preservation, export, backup, and limitations.

The **server** view contains recognized connection, HTTP streaming, request queue, and response-delivery events. The **model** view contains recognized model loading, GPU, context, prompt, token, and timing events. Unknown entries, unprefixed continuations, and all warning/error records appear in both views but are stored only once. Classification remains tied to the pinned runtime.

`diagnostics.py` serializes client and runtime output; `ram_logs.py` retains original diagnostic lines in the existing recorder’s RAM and saves the surviving buffer through `storage.py` on shutdown. `log_router.py` classifies lines and formats them when displayed or exported. Terminal output and Discord connection output are separate streams in the same database. Structured messages record incoming text, reasoning, final answers, and command notices independently of the active context window.

Diagnostic views show `[event NUMBER]` and a UTC ISO receipt timestamp with microseconds. Event numbers are now database-wide, rather than restarting each launch. Gaps can represent events belonging to another view/stream/session, expired batches, or unused reserved IDs. Diagnostic IDs are reserved in blocks, so they do not establish numeric receipt order across streams. Shared events have the same number and timestamp in both views. Runtime elapsed timestamps remain in original bytes; receipt order does not prove execution order across threads.

Below each header, messages appear on `    | ` rows wrapped at 140 characters. Formatting preserves original content reversibly: controls become `\xHH`, literal backslashes are doubled, blank lines are marked, and a missing final newline is explicit. The database itself stores the exact unformatted bytes, so it need not reconstruct them from presentation. Original JSON values are not rounded or truncated.

The live windows use `log_view.py` and the shared palette in `style.py`:

| Meaning | Color |
|---|---|
| Discord/source labels | Bright cyan |
| User, channel, message IDs | Lavender |
| User message text | Neon green |
| Reasoning heading | Bright yellow |
| Reasoning and routine processing | White |
| Answer heading | Light pink (`#FF9ACB`) |
| Assistant answer text | Hot pink (`#FF4FA3`) |
| Timestamps and event headers | Light blue |
| Connection/delivery success | Turquoise |
| Queue, processing, delivery timings | Peach |
| Token counts and context usage | Violet |
| Warnings, disconnects, retries | Orange |
| Errors | Bright red |

The visible heading is **Reasoning**, matching the API’s `reasoning_content` field. **Answer** labels the final text from `content`; `assistant` is its message role, not another kind of output. The publisher’s “thinking mode” and the API’s `enable_thinking` option still describe the same enabled mode. Protocol names and original runtime diagnostics remain unchanged.

Diagnostic field labels are white; their values carry the colors above. IDs, delivery progress, timings, and other details are separated into spaced groups in the Discord view. Session start/end and history-clear headings are cyan. Delivery starts are orange, confirmed parts turquoise, and failed parts red; confirmed earlier parts stay turquoise even after a later failure. Rollover starts are orange, completion turquoise, and failure red, with spacing around those events. Timing values show milliseconds where recorded. These are presentation changes only.

Diagnostic colors follow recognizable fields and client records; unknown rows remain white. Source control bytes are escaped in diagnostic views. Discord JSON is expanded into readable blocks. Colors are enabled only for terminal output; redirects are plain text. These views do not alter stored evidence.

For saved-session viewing, text export, SQL export, and backup/restore commands, see [storage](storage.md). No text log or third raw-debug file is automatically created. RAM and saved diagnostic batches roll under the [retention policy](log-retention.md).

## Message IDs and section boundaries

Stored correlation IDs are read only from a leading `Client: [message …]` diagnostic header or a top-level Discord record field. Quoted message text, nested JSON fields, and terminal presentation bytes do not establish attribution. Malformed IDs remain unassigned while original bytes are preserved. This applies to new records; existing stored metadata is not rewritten.

New messages handled by main chat carry a log-only correlation ID. Terminal turns
use `local:<UUID>`; Discord uses `discord:<incoming-message-id>` through the
adapter, local socket, queue, model/tool processing, and delivery. The Discord
log keeps its original numeric `message_id` and adds `log_message_id` for matching
main diagnostics. Older callers without an ID receive a local UUID.

Both main diagnostic views show prominent boundaries, for example:

```text
Client: [message discord:123456] ========== MESSAGE START | processing ==========
Client: [message discord:123456] Conversation selected: discord:789.
Client: [message discord:123456] Message input: "Hello"
Client: [message discord:123456] Prompt budget: ...
Client: [message discord:123456] Reply completed: finish_reason=stop.
Client: [message discord:123456] ========== MESSAGE END | processing | completed ==========
```

These lines still receive the usual event numbers and receipt timestamps. Client
records inside processing, including tool events, usage, and failures, carry the
same ID. An end marker says `completed`, `failed`, or `interrupted`; failed input
does not enter conversation history. `/clear` also gets boundaries. Local `/help`,
`/exit`, and blank input do not create model-processing sections.

Between-turn cache preparation has its own start/end section with the triggering
message's ID. Its end says `finished`; any preparation failure or shutdown is
recorded inside that section, and existing history-preservation behavior remains
unchanged. Preparation finishes before the next processing section starts.
Discord has separate delivery boundaries and an outcome, since successful model
processing does not guarantee successful delivery. Search the full correlation
ID across the session views to follow a message.

Raw llama.cpp lines retain their original bytes and runtime task identifiers;
they are not individually stamped with the application message ID. They appear
among these boundaries in receipt order, which does not prove exact attribution
for delayed runtime output or unrelated connection events. Session-wide events
remain outside message scopes. A crash or forced process kill can leave a start
without an end; that is incomplete evidence, not a successful turn.

These IDs are not supplied to the model or saved in conversation history.
Operators can inspect saved logs with the [storage commands](storage.md). No model log-reading tool is enabled. Legacy text exports remain readable.
Restart main chat and reconnect Discord to use the updated logging together.

Verification uses synthetic messages: unique terminal IDs, success/failure
boundaries, preparation separation, correlation through the real local socket
and queue, shared-file routing, viewer colors, and mocked Discord delivery.

## Model requests and tool calls within a message

Each message numbers its generation requests `01`, `02`, … and tool executions
`01`, `02`, … separately. The full message ID remains on every related client
record. Request and tool numbers restart for each message; use the message ID
plus the child number as the complete reference, for example
`discord:1234/request-02` and `discord:1234/tool-01`.

The saved event header repeats these labels and marks section boundaries, so
searching for `discord:1234` finds its records in either diagnostic view. A
simplified view (omitting event numbers and timestamps) looks like:

```text
[message discord:1234] [MESSAGE START]
[message discord:1234] [request 01] [MODEL REQUEST START]
[message discord:1234] [request 01] ... prompt budget, usage, finish reason ...
[message discord:1234] [request 01] [MODEL REQUEST END]
[message discord:1234] [request 01] [tool 01] [TOOL CALL START]
[message discord:1234] [request 01] [tool 01] ... tool name and protocol call ID ...
[message discord:1234] [request 01] [tool 01] [TOOL CALL END]
[message discord:1234] [request 02] [MODEL REQUEST START]
[message discord:1234] [request 02] ... final generation ...
[message discord:1234] [request 02] [MODEL REQUEST END]
[message discord:1234] [MESSAGE END]
```

The reversible event body has explicit start/end banners too. Model request ends
say `completed`, `failed`, or `interrupted`; a separate finish reason distinguishes
`stop`, `length`, and `tool_calls`. A request number identifies an attempted model
call, including one rejected during its budget check before HTTP transmission.
Template/token-count requests and cache preparation are not generation requests.

Tool records retain the request number that produced the call, plus a per-message
tool number. `Tool call identity` records its name and the original protocol ID;
protocol IDs are not replaced or inserted into prompts. Two calls to the same
tool still get different numbers. Unknown tools and raised tool failures get
closing failure banners. A normal tool return ends with `returned`, not a claim
that the requested operation succeeded: the framework can return an error as text,
and tools can return their own structured error results.

Raw runtime records remain unchanged and are not assigned inferred child IDs.
No model log-reading tool is registered. Restart main chat to get the new request
and tool labels; reconnect Discord after restarting. Existing saved logs remain
readable and are not rewritten.

Verification uses the real pinned Qwen-Agent loop with synthetic streamed HTTP
responses: multi-call turns, repeated calls to the same tool, unchanged protocol
IDs in tool results, failed/truncated streams, rejected tools, budget rejection,
raised/returned tool errors, scope cleanup, and lossless log routing. These checks do not assert live-model tool-selection quality.

## Log storage and recovery

Keep the SQLite database when updating or reinstalling. Follow [backup and restore](storage.md#backup-and-restore) rather than copying a live main file without its WAL. Saved records do not restore model context. Synthetic checks cover same-version database restoration and SQL export/import; migration to another database engine is not verified.

Optional exported text views can be archived manually. They are not loaded as memory and do not replace a complete database backup.

Contact notes add `Contact notes supplied`, `Contact notes updated`, and `Contact notes update rejected` client events to the existing diagnostic stream. Successful writes include the contact UUID, entry action (`add`, `patch`, or `remove`), and character count; tool/runtime diagnostics can include the Markdown itself. No separate log file is created. See [contact-note storage and verification](contact-notes.md).

`Conversation selected: terminal:<uuid>` or `discord:<account-id>` identifies each serialized turn in diagnostics; clear events also include that key. The main terminal labels both input sources and shows all conversations, although their model histories are separate. Cache save/restore, entry sizes, and evictions remain in runtime diagnostics.

## Rolling retention and protected errors

Diagnostics now use [20 MB logical batches and a 500 MB rolling budget](log-retention.md) in the existing recorder’s RAM, saved to SQLite on shutdown. The latest 20 recognized diagnostic failures retain 20 preceding/following events separately. Conversations and terminal/Discord transcripts remain preserved. See that guide for completeness flags, read commands, migration, and physical disk-size limits.

## Search metadata

Recorded envelopes now provide indexed event types, operation ordinals and explicit
Discord identity/delivery fields in SQLite. See [search fields and their limits](storage.md#searchable-diagnostic-metadata-schema-5). This does not enable model access.
