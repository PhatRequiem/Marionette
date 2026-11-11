# Reading the logs

`-server.txt` contains recognized connection, HTTP streaming, request queue, and response-delivery events. `-model.txt` contains recognized model loading, GPU, context, prompt, token, and timing events, including inference performed by server components. Unknown entries and all warning/error records go to both. Unprefixed continuation lines are also shared so they cannot be silently misclassified. Classification is tied to the pinned runtime; unfamiliar formats fall back to both files.

Main-chat diagnostics also record **Sender identity** for each input: source, sender ID, display name, and person UUID. These shared records connect terminal and Discord messages to the saved [profile mapping](identity.md). The Discord connection log continues to use Discord account/channel/message IDs; the main diagnostics contain the resolved person identity.

`diagnostics.py` serializes client messages and raw runtime output into the same diagnostic stream before routing. Moving code between modules does not create new log files or change the saved format.

Every received line gets `[event 00000001]` followed by an ISO timestamp with microseconds and UTC offset, then a readable message block retaining the runtime's elapsed timestamp. The added timestamp is receipt time, not the time the runtime generated the event. Identical shared entries carry identical numbers and timestamps. Numbers restart each session; gaps within one file mean events routed only to the other file. Compare the two files by event number to recover their combined receipt order. This is line order, not a claim of exact execution order across runtime threads.

Messages appear below their event header on `    | ` continuation rows, wrapped at 140 characters. JSON punctuation outside strings starts a new row; values are not parsed, rounded, truncated, or deduplicated. Blank input lines are explicitly marked `[blank line]`. Control bytes are displayed as `\xHH` (for example `\x1b` for Escape and `\x08` for backspace), and literal backslashes are doubled. This retains the codes without allowing them to alter the terminal display. To recover an original message, concatenate its continuation rows without their prefixes or added line breaks, decode those escapes, and restore its final newline unless the header says `[no final newline]`. Shared events use identical formatting in both files. Existing session files are not rewritten; the new format applies on the next launch.

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

Diagnostic colors follow recognizable fields and client records; unknown rows remain white. Message words such as “error” inside a normal reply do not change its color. Source control codes stay visible as escaped text. This is a display layer: saved server/model files retain their complete reversible format and shared event numbers. Main chat keeps its normal terminal transcript, including its color codes. No extra files or windows are created.

To read an existing saved file with the same presentation, run from the project directory (replace `PATH_TO_LOG` with its path):

```bash
python src/marionette/log_view.py diagnostic < PATH_TO_LOG
python src/marionette/log_view.py discord < PATH_TO_DISCORD_LOG
```

The Discord view expands JSON message text into readable blocks and shows every metadata field separately. Saved Discord records remain structured and uncolored for tracing and future tools. Colors are enabled only when output goes to a terminal; redirected output is readable plain text. Existing saved files are never rewritten.

There is no third raw debug file or filtered temporary log. The launcher waits for the router to finish writing before exiting. Older `-debug.txt` files remain untouched. Export all three matching chat files and any associated Discord connection files together; nothing automatically deletes or rotates them.


## Message IDs and section boundaries

New messages handled by main chat carry a log-only correlation ID. Terminal turns
use `local:<UUID>`; Discord uses `discord:<incoming-message-id>` through the
adapter, local socket, queue, model/tool processing, and delivery. The Discord
log keeps its original numeric `message_id` and adds `log_message_id` for matching
main diagnostics. Older callers without an ID receive a local UUID.

Both main diagnostic files show prominent boundaries, for example:

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
ID across the matching session files to follow a message.

Raw llama.cpp lines retain their original bytes and runtime task identifiers;
they are not individually stamped with the application message ID. They appear
among these boundaries in receipt order, which does not prove exact attribution
for delayed runtime output or unrelated connection events. Session-wide events
remain outside message scopes. A crash or forced process kill can leave a start
without an end; that is incomplete evidence, not a successful turn.

No snapshot/retrieval tool or new log file is added, and these IDs are not supplied
to the model or saved in conversation history. Existing logs are not rewritten.
Restart main chat and reconnect Discord to use the updated logging together.

Verification uses synthetic messages: unique terminal IDs, success/failure
boundaries, preparation separation, correlation through the real local socket
and queue, shared-file routing, viewer colors, and mocked Discord delivery.

## Log storage and recovery

Keep the existing `data/conversations/` folder when updating or reinstalling. To restore logs, copy the backed-up `.txt` files (and any historical `-setup.json` files) for each session into that directory without overwriting newer files. Restoring files does not restore model context. A byte-for-byte copy and restore of a synthetic transcript is checked separately from inference; no cross-database migration is applicable.

Completed sessions may be moved manually into `data/conversations/archive/`. Stop the relevant chat and Discord connection first, then keep all matching chat/server/model files and associated Discord files together. Archived files remain readable through the same log viewer; they are not automatically loaded as memory.

Character profiles add `Character supplied`, `Character updated`, and `Character update rejected` client events to the existing diagnostic stream. Successful writes include the person UUID, entry action (`add`, `patch`, or `remove`), and character count; tool/runtime diagnostics can include the Markdown itself. No new log file is created. See [character storage and verification](characters.md).

`Conversation selected: terminal:<uuid>` or `discord:<account-id>` identifies each serialized turn in diagnostics; clear events also include that key. The main terminal labels both input sources and shows all conversations, although their model histories are separate. Cache save/restore, entry sizes, and evictions remain in runtime diagnostics.
