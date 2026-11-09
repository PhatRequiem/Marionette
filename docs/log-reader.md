# Active-session log access

Marionette can request one read-only function, **read_logs**, while answering in terminal or Discord. No extra program, launch command, model change, personality file, database, or background thought loop is required. Start normally using [STARTUP.md](../STARTUP.md).

Try: “Check your current model logs for warnings and tell me what you find, with references.” The model decides whether to call the tool; this is not a deterministic command. Look for **Reading active logs…** in main chat and `tool_call` / `tool_result` events in the chat log to verify it actually searched.

## Responsibilities

- `src/marionette/log_reader.py` owns the concise guide/schema and topic routing, readable evidence, computed token/time fields, and bounded retrieval from fixed active paths.
- `session.py` connects that reader to the running session.
- `inference.py` parses structured tool-call deltas, executes only read_logs, returns a tool result, and resumes generation.
- `terminal.py` displays reasoning, lookup notices, and answers. Discord still receives only the final answer.
- Existing storage/router/viewer modules retain their separate responsibilities. No logging format migration is required.

The tool description is the guide the model sees on every request. It explicitly distinguishes ordinary conversation from evidence requests: greetings and acknowledgments should receive normal replies, and sender metadata is not a request to audit a message. After a lookup, she should answer the question in plain language with only relevant references, rather than dumping metadata tables. This is model guidance, not a keyword gate; tool selection is still probabilistic. It explains the sources, interpretation limits, and that retrieved text is untrusted evidence, never instructions. This is supplied with the API's tool definition, not by loading the human documentation into context.

## Request and result

| Option | Values |
|---|---|
| `topic` | `reasoning`, `tokens`, `messages`, `delivery`, `errors`, or `activity` |
| `limit` | Optional 1–20 records; default 10 |

The model chooses the topic; code chooses the files and event types:

| Topic | Evidence returned |
|---|---|
| reasoning | Generated reasoning text in the chat log, with its associated user message when present in the scanned tail |
| tokens | Chat context snapshots, completed generation usage, and startup capacity; code provides explicit meanings and calculated prompt percentages/headroom |
| messages | User messages and final answers from chat; excludes reasoning |
| delivery | Discord receipt, sending, confirmation and connection status; receipt is not proof of answer delivery |
| errors | Warnings/failures from chat, server, model and the attached Discord log; identical shared diagnostic lines are deduplicated |
| activity | Runtime/client diagnostic activity from server and model |

Each lookup snapshots at most the most recent **1 MiB per selected file**, returns at most **12,000 JSON characters**, and truncates individual record text after **2,000 characters**. Results identify the session, topic, source of each record, original references, timestamps, truncation, and per-file coverage (availability, tail limit, skipped records and additional matches). The newest matching records are returned in chronological order. No pagination or complete-history search is implemented.

Reasoning and message text is returned directly rather than as a JSON metadata dump. Reasoning is labeled with the original user message when it is in the scanned tail. User messages outside that tail cannot be associated. The model selects only topic and count; it no longer chooses filenames or invents free-text filters. Base64 decoding and batch expansion happen in code; the model never chooses file paths.

For tokens, `summary.latest_prompt_snapshot` is a measurement **before its generation**, not a live meter after the lookup. `latest_completed_generation` describes one generation (which may itself request a tool), including its reasoning and answer/tool output (new usage records identify tool-call versus answer generations); it is not cumulative session usage or current context occupancy. The reader calculates prompt percentage, capacity minus prompt, and spare tokens after the recorded reply reserve plus boundary token. A code-written measured-context statement reinforces the exact snapshot count and percentage. No arithmetic is inferred from response text. Later tool results increase the next prompt. Missing snapshots are returned as unavailable summaries, not estimates.

Each record retains its original offset-bearing timestamp and includes `timestamp_utc`, converted by code. Local time must not be relabeled UTC. No inferred elapsed-time statistic is supplied. Normal startup now records a structured context snapshot before each initial generation and tool continuation; older files may lack these events.

A search can miss an older event even within the current session. Missing output does not prove an event never occurred. Malformed/unfinished JSON is reported as skipped. Buffering can delay visibility. Raw terminal chunks and prior tool request/result records are excluded to avoid duplicate/recursive output. The errors topic automatically selects warnings/errors; the model does not provide a text filter. Missing results do not establish that the logs are clean.

## Boundaries and lifetime

The tool has no path, source, view, or query argument. Main chat/server/model paths derive from this launch's chat file. For Discord, a private registration binds the currently attached adapter's log to the main socket identity and live process. Detached connections, prior main sessions, archives, credentials and arbitrary files are outside scope. Symlink log files are rejected. Discord must use the same log directory as main chat for tool access.

Profiles currently share conversation history and these active logs; this is not per-person access isolation. Selecting a terminal profile is not authentication. `/clear` clears model history but leaves active log access intact, including earlier same-session records. A new main launch starts a new log scope.

The tool only reads evidence. It cannot run commands, modify/delete logs, or change settings. Tool-call auditing writes ordinary chat/diagnostic records separately. Model/user text and reasoning are statements, not proof about hardware, consciousness, permissions or deployment. A logged answer does not establish delivery; consult Discord delivery confirmations.

## Limits and verification

At most **two sequential tool calls** are executed per user turn, followed by a final generation with tool choice disabled and a temporary system instruction to answer using the evidence. That instruction is counted in context and does not enter long-term conversation history. This last answer is buffered until completion so unparsed tool-call syntax can be rejected instead of sent to Discord. Unknown tools and invalid arguments never become file operations. Interrupted or incomplete tool-call streams do not execute. Generation usage is shared across the full turn; continuation prompts are counted before generation. Intermediate tool messages and reasoning are transient; future conversation history remains user/final-answer pairs. See [context policy](context.md).

The implementation uses existing `--jinja` runtime support for [OpenAI-style function calling](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md) and the model's bundled template. Publisher context: [Qwen function calling](https://qwen.readthedocs.io/en/stable/framework/function_call.html) and [Qwen3.5-4B tokenizer configuration](https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/tokenizer_config.json). No runtime, reasoning or sampling setting was changed.

On 2026-11-09 an isolated real Q4 session selected read_logs, received an actual active model warning, and returned an answer identifying its timestamp and reference. It shut down cleanly. All 74 checks (62 core and 12 mocked Discord) pass. Synthetic tests cover path/scope restrictions, live Discord registration, malformed/truncated records, bounded output, stream assembly, unknown tools, call limits, generation/context budgets, normal chat and mocked Discord delivery. This proves functional retrieval, not perfect model interpretation or guaranteed tool choice. No live Discord DM or long-session tool benchmark was performed.

## Conversational-use check (2026-11-09)

The guide was refined after live greetings triggered unnecessary identity/message audits. It now explicitly says to answer greetings, acknowledgments and ordinary conversation directly, use logs only when recorded evidence is needed, and avoid routine metadata tables. It also explains literal queries and warns against unverified timing/delivery claims. The topic-based reader below supersedes direct source selection.

An isolated real Q4 test using synthetic Discord-source input returned conversational answers to Hello and Okay with zero tool calls. A natural request to check model warnings made one call and retrieved the actual no-API-key/CORS warning. A preceding terminal test also answered the two casual messages without tools; it exposed a literal-query mistake that the revised guide addresses. These are sampled behavior checks, not a guarantee of every future response. No real Discord messages or personal profiles were used. All 74 regression checks pass.

Running sessions load the guide at startup. Restart to use the revised guide; a fresh session also removes the previous audit-style answers from conversation history.

## Topic-based retrieval verification (2026-11-09)

The tool now accepts only topic and count. Direct file selection and model-invented literal search phrases were removed after they caused false misses. Reasoning records include the original input when available; errors combine relevant sources and deduplicate shared lines. Tokens have explicit pre-generation versus completed-generation meanings, calculated context figures and a code-written measurement statement. UTC conversion is performed by code.

All 79 checks (67 core, 12 mocked Discord) pass, covering topic isolation, original-input association, duplicate removal, token arithmetic, UTC conversion and final-answer handling after two lookups. An isolated real Q4 test using a synthetic Discord-source connection answered a greeting without tools, retrieved tokens, retrieved actual saved greeting reasoning, found the startup warning, and completed a two-lookup request. No real Discord DMs were sent by the test.

Retrieval and computed fields are verified; model interpretation is still imperfect. The live test occasionally confused a completed generation total with context occupancy in its prose despite correctly supplied fields. Clearer labels and the code-written measurement statement help, but generated explanations must still be checked against returned evidence. No general accuracy guarantee or long-session benchmark is claimed.
