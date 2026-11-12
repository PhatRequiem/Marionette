# Operator log queries

The handler accepts the [request form](log-request-form.md) and returns JSON facts,
evidence references and limitations. It is **not registered as a model tool**.
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
a future model adapter must bind it from authenticated caller context, not model
arguments. No connection to the model is authorized by this operator interface.

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

## Verification

`tests/core/test_log_query.py` covers valid/invalid forms, conversation scope,
previous-message anchoring, processing/delivery/error extraction, deduplication,
bounds, live RAM reads without disk event writes, startup-only parsing, and
isolated status probes. Discord status uses synthetic bot state, not credentials.
The handler was also exercised through forms against the saved multi-user archive
for processing, delivery, errors and previous-message retrieval, and against the
local startup sheet. A fresh synthetic main-chat instance returned current health,
registered tools and idle state. This verifies handler behavior, not the 4B model's
ability to choose a form. Model form selection remains to be tested when separately
connected.
