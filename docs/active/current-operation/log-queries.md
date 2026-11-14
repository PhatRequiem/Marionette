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

- `setup` reads only the marked, dated setup section: startup evidence plus the latest observed application configuration. It is not current health. See [refresh triggers](../setup-and-maintenance/setup-datasheet.md#refresh-triggers).
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
combines saved evidence with available recorder RAM evidence. Streaming reasoning display chunks are excluded before evidence limits. Protected copies
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
- `processing_boundary_elapsed_ms` measures application processing boundary elapsed time, not pure inference time. Budgets are allowances, not usage.
- Delivery reports `receipt_to_delivery_ms` only for a recorded successful answer-send event, or `receipt_to_failure_ms` for a recorded failure. Queue, processing and local round-trip intervals overlap. No send-only duration is inferred. Chunk counts describe retained send records.
- Setup explicitly labels `llama.cpp runtime version`, including when reading an older startup sheet. Reasoning format does not identify a model family; GPU offload counts do not measure utilization.
- Message results identify their ID as the incoming user message anchoring the exchange, not the outgoing reply. Current tool lists describe bindings at the probe instant; empty recognized-error results do not prove an error-free run.

## Model guidance

The tool is rebound after each conversation switch and before prompt counting. Its description includes short definitions and valid request examples; the full glossary and datasheet are not injected into every prompt. Only current-session messages are accessible. A current-status query usually observes processing as busy because it runs during the answering turn.

Enabled [log-query instructions](../../../prompts/log-queries.md) are composed separately from the editable soul. They guide evidence lookup for setup/status questions without forcing a tool call or guaranteeing compliance. Other registered tools receive their own concise guidance; see [prompt composition](../../../prompts/prompt-guide.md). Restart chat to load prompt edits.

## Current reliability limits

Successful retrieval and delivery do not guarantee accurate model interpretation. Unit conversion, unsupported claims, and response length require review. The short follow-up instruction in `prompts/log-results.md` applies only after a fresh log result in the current turn, not when answering solely from retained context.

Answer quality and long-session reliability are not established by functional tool checks. Before relying on interpretations for automated actions, evaluate tool selection, arguments, factual interpretation, and error recovery separately, including messages that need no tool.

### Tool and connection evidence

Processing reports include one tool entry per request/tool ordinal, with protocol call ID, action, explicit outcome and evidence references. Missing outcomes remain unknown; completed processing does not imply every tool succeeded. Failed tool-result summaries are recognized by error lookups and retention.

Message-owned Obsidian HTTP UUIDs anchor joins to otherwise untagged Scarecrow server events in the same session, including protected evidence. Reports use `http_request_id` to distinguish these UUIDs from model-request ordinals. Joins use exact IDs, never timestamp proximity; unrelated messages and global lifecycle events are excluded. If the client anchor or server events have expired, the corresponding evidence cannot be reconstructed. Existing query byte/event limits still apply.

Current status includes a separate `obsidian` result from an authenticated Scarecrow `/v1/status` probe, with its own observation timestamp. It reports ready, unavailable, disabled, not_configured or unknown. This is independent of the tools list. Unavailable is not proof that the Obsidian application is closed.
