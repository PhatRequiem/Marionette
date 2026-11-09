# Reading the logs

New sessions save **JSONL**: one complete JSON object per line, in UTF-8. The log terminals decode these records into readable colored text; they do not display walls of JSON or Base64. Launch commands and window count are unchanged. Older text logs stay untouched and remain readable with the viewer.

This is storage and presentation only. Marionette cannot read these files, recall previous sessions, or use them as memory.

## Files and contents

All files remain private under `data/conversations/`:

| File ending | Contents |
|---|---|
| `-chat.jsonl` | Exact recorded terminal stream in Base64, plus structured profile, input, reasoning, answer, usage, command, and lifecycle events |
| `-server.jsonl` | Recognized connections, HTTP streaming, request queue, and response-delivery diagnostic lines |
| `-model.jsonl` | Recognized loading, GPU, context, prompt, token, and timing diagnostic lines |
| `-discord.jsonl` | One per optional Discord connection: incoming messages, answers, delivery, connection, and error metadata; no model reasoning |

Unknown diagnostic lines, unprefixed continuations, and all warnings/errors go to both server/model files. Each shared record is identical, including its UUID and sequence number. Classification is tied to the pinned runtime; unfamiliar formats fall back to both files. There is no additional raw debug file.

Main-chat input and response events carry source, sender ID, display name, person UUID, and a per-turn UUID. See [identities](identity.md). Reasoning and answer events are written when a stream completes or unwinds after an error; interrupted output is marked `complete: false`. Raw terminal output is saved as it arrives. Structured events are not written per token. A hard kill can prevent a final structured event from being written, even when earlier raw chunks were saved.

Discord retains its account/channel/message IDs and delivery metadata. Its connection has its own session ID; main chat/server/model share the main session ID. Main diagnostic identity records and chat events identify the resolved person. Discord message IDs are not currently forwarded into the main chat events.

## Record format, original bytes, and ordering

Every version 1 record has:

| Field | Meaning |
|---|---|
| `version` | Storage schema version, currently 1 |
| `session_id` | Timestamp and random suffix from the session filename |
| `event_id` | Unique UUID; shared diagnostic copies retain the same UUID |
| `timestamp` | Local ISO receipt/recording time with microseconds and UTC offset |
| `source` | Producer or input source, such as diagnostic, terminal, application, or discord |
| `event_type` | Such as diagnostic, terminal_output, message_received, reasoning, answer, or status |
| `data` | Structured fields; diagnostic records include routing destination |
| `sequence` | Present for raw records; receipt order within that capture stream |
| `raw_b64` | Present for raw records; original bytes encoded as Base64 |

Base64 preserves arbitrary bytes, including ANSI color codes, carriage returns, backspaces, invalid UTF-8, blank lines, and missing final newlines. It is reversible encoding, not encryption or compression. Ordinary message text uses normal JSON strings; it does not need Base64.

Diagnostic sequence numbers restart each main session and are assigned before routing. Gaps mean a line went only to the other file. Merge the diagnostic files by sequence and deduplicate their shared event IDs to recover the combined diagnostic stream. Terminal capture has a separate sequence; it must not be merged using diagnostic sequence numbers. Timestamps describe receipt, not exact execution order across threads. Structured and raw chat writes can interleave; turn IDs group structured messages reliably.

`diagnostics.py` synchronizes runtime/client diagnostic writes. `log_router.py` assigns diagnostic records and routes them. `log_store.py` handles the common envelope, Base64 capture, and locked append operations for the shared chat file. `log_view.py` renders the saved evidence.

Diagnostic views retain event numbers and timestamps, with wrapped continuation rows. Control bytes display as escaped text instead of executing in the terminal. JSON-looking runtime text is formatted without parsing away duplicate keys or changing values. The saved Base64 remains the authoritative original bytes.

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

Diagnostic colors follow recognizable fields and client records; unknown rows remain white. Message words such as “error” inside a normal reply do not change its color. Source control codes stay visible as escaped text. This is a display layer: saved server/model JSONL files retain original bytes and shared event numbers. Main chat retains its terminal stream, including color codes, inside Base64 records. No extra files or windows are created.

## Viewing and exporting

Run from the project directory, replacing the placeholders with actual paths:

```bash
python src/marionette/log_view.py diagnostic < PATH_TO_SERVER_OR_MODEL_LOG
python src/marionette/log_view.py discord < PATH_TO_DISCORD_LOG
python src/marionette/log_view.py chat < PATH_TO_CHAT_JSONL
```

The chat view displays structured events without repeating the raw terminal chunks. Colors require terminal output; redirection produces readable plain text. Legacy diagnostic and Discord text logs remain supported.

To recover the exact recorded terminal bytes into a separate file:

```bash
python src/marionette/log_store.py export-raw PATH_TO_CHAT_JSONL > recovered-terminal.txt
```

This concatenates decoded raw records in file order and skips structured records. It also works for an individual diagnostic file, containing only that file's routed lines. For Discord it exports only fallback raw output; normal Discord messages are already structured JSON events. Exporting raw bytes does not reproduce original playback timing. Inspect control codes with care rather than blindly printing an untrusted recovered stream.

## Storage and recovery

Base64 adds about one third to the raw payload size, plus JSON metadata. Small terminal chunks can have substantially more metadata than payload. Structured chat events also duplicate some text already present in the captured terminal stream; shared diagnostic events still appear in both diagnostic files. This deliberately retains both original evidence and searchable fields. Logs can be large; no automatic deletion or rotation is configured.

Files use owner-only permissions. Writers flush records as they arrive; normal launcher exit waits for the capture and routing processes. Closing a diagnostic viewer does not stop recording. This is not power-loss durability: there is no per-record disk synchronization, and a crash can leave a partial final JSON line. The viewer flags invalid records without changing the file. Raw export stops on malformed JSON rather than silently skipping evidence.

Stop the related sessions before backing up, then copy matching chat/server/model files and associated Discord connection files together. Restore without overwriting newer sessions. Keep older `.txt` and historical setup files if needed; they are not automatically converted. Same-version copy/restore and byte-exact raw reconstruction are tested with synthetic data. No cross-database migration is involved.

Completed sessions can be moved manually into `data/conversations/archive/`. An archive on the same disk is not a backup. Restoring or archiving logs does not restore model context or enable recall.

## Verification for this change

On 2026-11-09, 46 core checks and 12 mocked Discord checks passed. They cover byte-exact Base64 recovery (including invalid UTF-8 and control bytes), concurrent append integrity, copied-log restoration, shared diagnostic identities, unchanged diagnostic presentation, partial response records, and writer failure reporting.

An isolated Q4 GPU launch with a synthetic profile produced separate reasoning and answer events, answered a short arithmetic prompt, saved three valid JSONL files, and stopped its owned server. Real Discord login and long-session performance were not tested for this storage change. Model settings, rollover policy, and the fixed baseline-v3 recovery tag were not changed.
