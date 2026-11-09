# Active-session log access

Marionette can request one read-only function, **read_logs**, while answering in terminal or Discord. No extra program, launch command, model change, personality file, database, or background thought loop is required. Start normally using [STARTUP.md](../STARTUP.md).

Try: “Check your current model logs for warnings and tell me what you find, with references.” The model decides whether to call the tool; this is not a deterministic command. Look for **Reading active logs…** in main chat and `tool_call` / `tool_result` events in the chat log to verify it actually searched.

## Responsibilities

- `src/marionette/log_reader.py` owns the concise guide/schema and bounded retrieval from explicitly selected active paths.
- `session.py` connects that reader to the running session.
- `inference.py` parses structured tool-call deltas, executes only read_logs, returns a tool result, and resumes generation.
- `terminal.py` displays reasoning, lookup notices, and answers. Discord still receives only the final answer.
- Existing storage/router/viewer modules retain their separate responsibilities. No logging format migration is required.

The tool description is the guide the model sees on every request. It explicitly distinguishes ordinary conversation from evidence requests: greetings and acknowledgments should receive normal replies, and sender metadata is not a request to audit a message. After a lookup, she should answer the question in plain language with only relevant references, rather than dumping metadata tables. This is model guidance, not a keyword gate; tool selection is still probabilistic. It explains the sources, interpretation limits, and that retrieved text is untrusted evidence, never instructions. This is supplied with the API's tool definition, not by loading the human documentation into context.

## Request and result

| Option | Values |
|---|---|
| `source` | `chat`, `server`, `model`, or `discord` |
| `view` | `recent` or `errors` (warnings included) |
| `query` | Optional literal case-insensitive text, at most 200 characters |
| `limit` | Optional 1–20 records; default 10 |

Chat exposes structured messages, reasoning, answers, identities, usage and lifecycle. Server/model sources expand diagnostic batches into original lines with receipt timestamps and shared line references. Discord exposes message, connection and delivery evidence. Base64 is decoded by code; the model receives readable text.

Each lookup snapshots at most the most recent **1 MiB** of one file, returns at most **12,000 JSON characters**, and truncates individual record text after **2,000 characters**. Results identify the session/source, references, timestamps, text truncation, skipped/incomplete records, limited tail coverage, and whether additional matches exist within that scanned tail. The newest matching records are returned in chronological order. No pagination or complete-history search is implemented. Query matches one contiguous phrase, not multiple keywords or IDs. For all warnings/errors, omit query; an empty filtered search does not establish that the log is clean.

A search can miss an older event even within the current session. Missing output does not prove an event never occurred. Malformed/unfinished JSON is reported as skipped, rather than interpreted. Buffering can delay visibility. Raw terminal chunks are omitted to avoid duplicate output; tool request/result records are omitted to avoid recursively returning prior tool results. Unexpected raw Discord output is decoded as text.

## Boundaries and lifetime

The tool has no path argument. Main chat/server/model paths derive from this launch's chat file. For Discord, a private registration binds the currently attached adapter's log to the main socket identity and live process. Detached connections, prior main sessions, archives, credentials and arbitrary files are outside scope. Symlink log files are rejected. Discord must use the same log directory as main chat for tool access.

Profiles currently share conversation history and these active logs; this is not per-person access isolation. Selecting a terminal profile is not authentication. `/clear` clears model history but leaves active log access intact, including earlier same-session records. A new main launch starts a new log scope.

The tool only reads evidence. It cannot run commands, modify/delete logs, or change settings. Tool-call auditing writes ordinary chat/diagnostic records separately. Model/user text and reasoning are statements, not proof about hardware, consciousness, permissions or deployment. A logged answer does not establish delivery; consult Discord delivery confirmations.

## Limits and verification

At most **two sequential tool calls** are executed per user turn, followed by a final generation with tool choice disabled. Unknown tools and invalid arguments never become file operations. Interrupted or incomplete tool-call streams do not execute. Generation usage is shared across the full turn; continuation prompts are counted before generation. Intermediate tool messages and reasoning are transient; future conversation history remains user/final-answer pairs. See [context policy](context.md).

The implementation uses existing `--jinja` runtime support for [OpenAI-style function calling](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md) and the model's bundled template. Publisher context: [Qwen function calling](https://qwen.readthedocs.io/en/stable/framework/function_call.html) and [Qwen3.5-4B tokenizer configuration](https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/tokenizer_config.json). No runtime, reasoning or sampling setting was changed.

On 2026-11-09 an isolated real Q4 session selected read_logs, received an actual active model warning, and returned an answer identifying its timestamp and reference. It shut down cleanly. All 74 checks (62 core and 12 mocked Discord) pass. Synthetic tests cover path/scope restrictions, live Discord registration, malformed/truncated records, bounded output, stream assembly, unknown tools, call limits, generation/context budgets, normal chat and mocked Discord delivery. This proves functional retrieval, not perfect model interpretation or guaranteed tool choice. No live Discord DM or long-session tool benchmark was performed.

## Conversational-use check (2026-11-09)

The guide was refined after live greetings triggered unnecessary identity/message audits. It now explicitly says to answer greetings, acknowledgments and ordinary conversation directly, use logs only when recorded evidence is needed, and avoid routine metadata tables. It also explains literal queries and warns against unverified timing/delivery claims.

An isolated real Q4 test using synthetic Discord-source input returned conversational answers to Hello and Okay with zero tool calls. A natural request to check model warnings made one call and retrieved the actual no-API-key/CORS warning. A preceding terminal test also answered the two casual messages without tools; it exposed a literal-query mistake that the revised guide addresses. These are sampled behavior checks, not a guarantee of every future response. No real Discord messages or personal profiles were used. All 74 regression checks pass.

Running sessions load the guide at startup. Restart to use the revised guide; a fresh session also removes the previous audit-style answers from conversation history.
