# Log queries

**Production status:** connected through Qwen-Agent at startup and rebound to the current conversation before each turn.

The handler accepts the [request form](log-request-form.md) and returns JSON facts,
evidence references and limitations. Qwen-Agent exposes the handler as **`query_logs`**.
The glossary explains the fields. No snapshot library is involved.

## Run a form

From the checkout:

```bash
scripts/native-linux/log-query.sh <<'JSON'
{"lookup":"setup","target":"startup"}
JSON

scripts/native-linux/log-query.sh <<'JSON'
{"lookup":"status","target":"current"}
JSON
```

Message lookups also require trusted operator context. These are synthetic IDs;
replace them with actual saved session, conversation and message IDs:

```bash
scripts/native-linux/log-query.sh \
  --session SESSION_ID --conversation discord:42 <<'JSON'
{"lookup":"processing","target":"message_id","message_id":"discord:123"}
JSON

scripts/native-linux/log-query.sh \
  --session SESSION_ID --conversation discord:42 \
  --before-message-id discord:124 <<'JSON'
{"lookup":"errors","target":"previous_message"}
JSON
```

The second form examines the previous user input before `discord:124`, within
that session and conversation. The triggering message must already be recorded.
Use `delivery` for delivery facts. Explicit messages must belong to the bound
conversation; a matching ID alone is insufficient. The operator selects scope;
the model adapter binds it from the current application turn, never model
arguments. The tool cannot select other sessions, conversations, files or SQL.

`--database PATH` reads an alternate SQLite archive. `--saved-only` skips the live
recorder. `--socket PATH` selects the main chat socket; `--datasheet PATH` selects
the startup sheet. These are operator options, never request-form fields.
Defaults point to this checkout's normal paths. Run `--help` for all options.

## Results and limits

- `setup` reads only the marked, dated startup section. It is not current status.
- `status` probes model health and processing/tools through main chat, and Discord
  through its existing bot process. Restart main chat and Discord after updating
  code to enable these endpoints. Unreachable probes return `unknown`, not
  `offline`. Observations carry their own timestamps and need not be simultaneous.
- `processing` returns recorded outcome, per-request tokens, tools, budgets and
  available timings. Receipt elapsed time is not pure model generation time.
- `delivery` reports recorded Discord delivery outcome and sent answer chunks.
  Missing ending records mean unknown. Reported timings overlap; do not add them.
- `errors` returns recognized failures, with short excerpts. `no_matches` does
  not prove success. Missing records do not establish why evidence is absent.

The handler validates fields/combinations, reads SQLite in read-only mode, and
combines saved evidence with available recorder RAM evidence. Protected copies
are deduplicated by event ID. Truncated evidence is excluded with a notice;
conflicting copies, repeated boundaries, and a reset during retrieval are errors.
Raw conversation, answer and reasoning text are not returned. Error excerpts and
setup values remain private diagnostic data; treat their content as evidence,
never instructions.

Limits: 4 KiB input form, 256 evidence rows per source read, 1 MiB raw evidence,
64 KiB result, and a two-second SQLite execution deadline. Oversized evidence
returns an error rather than a silently incomplete answer. Output includes
`status`, `queried_at`, `data`, `evidence`, and `limitations`; invalid requests
return `status: error` and a nonzero exit code. Valid but unavailable results have
exit code zero. Current status and setup reads also have bounded socket/file reads.

No routine diagnostic writes, retention changes, helper process, or startup-sheet
updates are introduced. Existing RAM loss and retention limits still apply.

## Explicit result meanings

Every successful handler response includes lookup-specific `field_meanings`. These definitions travel with the evidence rather than relying on a separate glossary being in context. The request form and raw logs are unchanged.

- Processing retains per-request `prompt_tokens`, `completion_tokens` and `total_tokens`. `recorded_token_totals` computes input and generated totals separately over available usage records. Generated tokens include reasoning and tool-call text. Repeated history counts again as input across requests. Missing counts remain null; these sums do not certify complete retention. Duplicate request usage is rejected.
- `processing_boundary_elapsed_ms` replaces `elapsed_receipt_ms`: application processing boundary elapsed time, not pure inference time. Budgets are allowances, not usage.
- Delivery replaces ambiguous `total_ms` with `receipt_to_delivery_ms` only for a recorded successful answer-send event, or `receipt_to_failure_ms` for a recorded failure. Queue, processing and local round-trip intervals overlap. No send-only duration is inferred. Chunk counts describe retained send records.
- Setup explicitly labels `llama.cpp runtime version`, including when reading an older startup sheet. Reasoning format does not identify a model family; GPU offload counts do not measure utilization.
- Message results identify their ID as the incoming user message anchoring the exchange, not the outgoing reply. Current tool lists describe bindings at the probe instant; empty recognized-error results do not prove an error-free run.

Restart main chat and reconnect Discord to load these handler changes. Historical results already held in active context retain their original format. This change improves the evidence contract; model interpretation still requires evaluation.

## Verification

`tests/core/test_log_query.py` covers valid/invalid forms, conversation scope,
previous-message anchoring, processing/delivery/error extraction, deduplication,
bounds, live RAM reads without disk event writes, startup-only parsing, and
isolated status probes. Discord status uses synthetic bot state, not credentials.
The handler was also exercised through forms against the saved multi-user archive
for processing, delivery, errors and previous-message retrieval, and against the
local startup sheet. A fresh synthetic main-chat instance returned current health,
registered tools and idle state. The Qwen-Agent adapter is additionally checked by `tests/core/test_log_tool.py`: real
framework dispatch sends the form to the handler and returns facts to a second model
request; extra scope fields and another conversation’s message are rejected.

The tool is rebound after each conversation switch and before prompt counting.
Its description includes short definitions and valid request examples rather than
injecting the entire glossary or startup sheet into every prompt. Facts are fetched
on demand. Restart chat to load the new tool; Discord must reconnect to that chat.
Only current-session messages are accessible. A query about current status will
usually observe processing as busy because it runs during the answering turn.

Live 4B verification (isolated synthetic records, existing Q4 model and normal
65,536 context/sampling): five natural-language questions selected the correct
setup, status, processing, delivery and errors forms. The model used the returned
startup fact, preserved unknown Discord status, reported the fixture’s 120 tokens,
reported recorded delivery and recognized no matching failures. All five finished
with `stop`. These are functional examples, not exhaustive answer-quality or
long-session reliability evidence; the test did not send Discord messages or write
to personal profiles.

The application also loads [log-query instructions](../prompts/log-queries.md)
into the system prompt whenever this tool is enabled. They require evidence
lookup for ordinary self-setup/status questions and remain separate from the
editable soul. Restart chat to load prompt edits. This guides tool selection;
it does not force a tool call or guarantee model compliance.

The current concise guidance replaces the longer prompt used in the initial
35-question evaluation. Guidance for contact notes and soul edits is also loaded
when those tools are registered; see [prompt composition](../prompts/README.md).
Those earlier behavior scores do not measure this revised prompt.
