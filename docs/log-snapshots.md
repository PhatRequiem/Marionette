# On-demand message log snapshots

`src/marionette/log_snapshot.py` builds a fixed-field JSON report for one explicit
message ID from existing logs. It is an operator utility, **not registered as a
model tool**. Main chat, Qwen-Agent, and Discord do not import or call it. This
prepares the extraction code for testing before any model connection is approved.

## Run it

From the checkout, supply matching diagnostic files from one session, the full
message ID, and the conversation ID shown in that message's log section:

```bash
./scripts/native-linux/log-snapshot.sh \
  --message-id 'local:00000000-0000-4000-8000-000000000001' \
  --conversation-id 'terminal:PERSON_UUID' \
  data/conversations/SESSION-server.txt \
  data/conversations/SESSION-model.txt
```

Replace the example IDs and filenames with actual values. Either main diagnostic
file can be supplied alone; both provide cross-checking and source references.
For a Discord message, use `discord:INCOMING_MESSAGE_ID` and
`discord:SENDER_ACCOUNT_ID`. Add `--discord-log PATH` for its connection log;
repeat this option only for distinct relevant connection files.

The command prints JSON to standard output. `null` explicitly means unavailable.
A missing message, missing/mismatched conversation, conflicting event copies,
ambiguous repeated processing boundaries, malformed supported fields, or exceeded
limits produces a nonzero exit and no report. Logs predating message IDs cannot
be reliably selected and are not guessed from timestamps.

No snapshot file, database entry, in-process cache, model request, or conversation
history entry is created. Each call reads the supplied files anew and builds a
new result. A Python caller controls the lifetime of the returned dictionary;
ordinary memory reclamation is not secure erasure. Shell redirection or terminal
recording can save displayed output, so do not redirect it if you want no saved
snapshot.

## Fields and evidence

| Group | Contents |
|---|---|
| Scope | Capture time, session name, message ID, conversation ID, schema version |
| Processing | Recorded outcome, start/end receipt times, elapsed receipt milliseconds, finish reason |
| Context | Last recorded prompt budget: capacity, prompt tokens, remaining space before generation, reply allowance, headroom after allowance and one spare token, input-time exchanges removed |
| Model requests | One entry per recorded usage event, with prompt/completion/total tokens, reasoning count if provided, corresponding last budget, and source references |
| Timing | First-token time, first-answer time, generation speed; currently unavailable from explicitly tagged records |
| Model / connections | Reserved fields for model configuration and connection status; unavailable because session-wide raw events are not attributed to a message |
| Cache preparation | Recorded section status and relevant preparation details |
| Delivery | Discord delivery outcome and recorded queue/processing/response/total timings, when the matching Discord log is supplied |
| Errors / warnings | Recognized tagged failure, interruption, preparation, rejected-character-update, trimming, and generation-limit records |
| Evidence / limitations | Filenames and event numbers (or Discord line numbers), missing-boundary and partial-read notices, interpretation limits |

The report does not include user message text, final answer text, character notes,
or model reasoning. Diagnostic error text can still contain private information.
It is diagnostic evidence, not trusted instructions or an automatic root-cause
verdict. Empty error/warning lists mean no recognized matching records were found
in the supplied files, not that all possible faults have been ruled out.

The same main diagnostic event appears in both server/model logs. Matching copies
are merged, never counted twice; conflicting copies are rejected. Multiple model
calls in a tool loop stay separate: prompt counts are **not summed** into context
usage. Completion tokens can include tool syntax, so answer-token counts are not
inferred by subtracting reasoning tokens. Missing usage on a failed request stays
unavailable rather than becoming zero.

Processing elapsed time is a difference between log receipt timestamps. It is
not precise model-generation time and excludes waiting before the processing
start marker. Backward clock movement makes it unavailable. Discord timing
fields overlap and must not be added together. Context remaining describes space
before generation, not a live or post-response context reading.

## Boundaries and limits

Only records explicitly bearing the requested message ID are attributed. Raw
llama.cpp errors, timings, cache hits, and configuration remain excluded even
when they occur between message markers: receipt order alone cannot establish
ownership. See [message boundaries](logs.md#message-ids-and-section-boundaries).

Each file is read only to its length at opening. The utility does not follow or
wait on the writer. Incomplete final rows/events are ignored with a notice;
a missing processing boundary yields `incomplete`. A live multi-file read is not
atomic, and a complete-looking final record can still be part of an ongoing
write. Retry after the turn finishes when exact completion matters.

Limits are 512 MiB scanned per file, 4 MiB per event/row, 256 matching diagnostic
events, 256 matching Discord records, eight distinct Discord files, and 128 KiB
for serialized report content. Exceeding a limit fails explicitly instead of
silently reporting a partial successful snapshot. Error text is capped at 1,500
characters with a truncation flag; preparation detail text is capped at 1,500.
These bounds and the sequential scan are a simple initial implementation; there
is no persistent index.

The conversation argument is a consistency check for an operator, not an
authentication mechanism. A future model-facing tool must bind permitted files
and the caller's conversation itself, handle selection of previous messages, and
verify the tool payload's lifecycle. **That connection is not implemented here.**

## Verification

Run the focused checks without an inference engine or private profiles:

```bash
python -m unittest discover -s tests/core -p test_log_snapshot.py -v
```

Synthetic checks cover real application failure logging routed through the log
formatter, wrapped/escaped values, duplicate copies, distinct tool calls, source
references, conversation rejection, incomplete messages, Discord failure and
sender matching, read-on-demand freshness, limits, and the standalone command.
Tests confirm that snapshots do not write files or include conversation prose.

Read-only verification on the running session on November 10, 2026 examined
three completed messages from both live diagnostic files. Prompt and completion
counts matched their original usage records; single-file and paired-file reports
agreed, duplicate evidence merged correctly, and log contents were unchanged.
No live failures or Discord delivery were observed in those three messages;
those paths were checked with synthetic evidence. No private logs or snapshots
were copied into the repository, and no model call was made for this verification.
