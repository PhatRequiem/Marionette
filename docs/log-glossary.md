# Log glossary

Short definitions for current logs. Reference only: this glossary is
not supplied to the model and does not enable log access.

## Storage and records

| Term | Definition |
|---|---|
| SQLite | Database used for both live RAM diagnostics and saved records. |
| RAM recorder | Existing process holding live diagnostics in in-memory SQLite. |
| Saved logs | Conversations and other persisted output, plus diagnostics saved on orderly shutdown. |
| `sessions` | Application runs, identified by UUID and start/end times. |
| `messages` | Durable inputs, reasoning, answers and command notices. |
| `events` | Original output records with searchable metadata. |
| `error_evidence` | Protected records surrounding recognized failures. |
| `failures` | Recognized failures and their retained evidence windows. |
| `failure_events` | Links failures to before/error/after evidence records. |
| `diagnostic_batches` | Groups of raw diagnostics used for rolling eviction. |
| Retention | Rules deciding which records remain available. |
| Eviction | Removal of older diagnostic batches when the budget is exceeded. |
| Protected window | Retained context around an error: up to 20 events before and after. |
| Memory generation | Reset boundary preventing old writers from restoring erased records. |

## IDs, names and searchable fields

| Field | Definition |
|---|---|
| `session_id` | UUID identifying an application run. |
| Event `id` / `event_id` | Event number shared by live views and shutdown-saved evidence. |
| Message row `id` | Database row number; distinct from the incoming message ID. |
| `message_id` | Incoming-message correlation ID: `local:UUID` or `discord:ID`. |
| `conversation_id` | History key for a terminal profile or Discord sender. |
| `contact_uuid` | Permanent identity shared across a contact's linked accounts. |
| `sender_id` | Sender's account ID, or terminal profile UUID. |
| `display_name` | Contact name recorded in a sender-identity event. |
| `preferred_name` | Preferred contact name recorded at that time. |
| `channel_id` | Discord channel containing the exchange. |
| `outgoing_message_id` | Discord ID of one successfully sent reply chunk. |
| `request_number` | Model-request ordinal within a message, stored as text such as `01`. |
| `tool_number` | Tool-call ordinal within a message, stored as text such as `01`. |
| `tool_name` | Name recorded by an explicit tool-identity event. |
| `protocol_tool_call_id` | Original tool-call ID supplied by the tool protocol. |
| Failure `id` / `failure_id` | Identifier linking a retained failure to its evidence. |
| `event_type` | Recognized event label extracted from an explicit log envelope. |
| `recorded_at` | Recorder receipt timestamp; not necessarily the event's original occurrence time. |
| `stream` | Output source: diagnostic, terminal or Discord. |
| `category` | Diagnostic-view routing: server, model or both. |
| `source` | Message interface, not a file path. |
| `role` | Message participant role, such as user or assistant. |
| `kind` | Message content kind, such as input, reasoning or answer. |
| `status` | Outcome or evidence state; meaning depends on its record/section. |
| `raw` | Original event bytes, preserved without text conversion. |
| `batch_id` | Diagnostic batch containing an event. |
| `original_bytes` | Original size of a protected evidence record. |
| `truncated` | Whether retained evidence was shortened. |

Names are labels, not unique keys. Use contact UUIDs for identity and
`(session_id, message_id)` for message joins. Operation ordinals need that message
scope. Metadata is populated only where explicitly recorded; neighboring records
do not automatically inherit it.

## Recognized event types

These are the current searchable labels, not a list of every possible raw log line.

| Event type | Definition |
|---|---|
| `conversation_selected` | Conversation chosen for processing. |
| `sender_identity` | Sender's resolved identity recorded. |
| `message_input` | Incoming message text recorded. |
| `reasoning` | Model reasoning recorded. |
| `processing_start` / `processing_end` | Message processing boundary. |
| `message_failed` | Message processing raised an error. |
| `message_interrupted` | Message processing was interrupted. |
| `prompt_budget` | Prompt size, reply allowance and capacity recorded. |
| `model_request_start` / `model_request_end` | Individual model-request boundary. |
| `model_request_failed` | Individual model request raised an error. |
| `model_request_interrupted` | Individual model request was interrupted. |
| `model_usage` | Runtime-reported token counts. |
| `reply_completed` | Reply completion and finish reason recorded. |
| `tool_identity` | Tool name and protocol ID recorded. |
| `tool_call_start` / `tool_call_end` | Individual tool-call boundary. |
| `tool_call_failed` | Tool call raised an error. |
| `tool_call_interrupted` | Tool call was interrupted. |
| `contact_notes_supplied` | Current-contact notes supplied to processing. |
| `contact_notes_rejected` | Contact-note update rejected. |
| `soul_update_rejected` | Self-profile update rejected. |
| `cache_preparation_start` / `cache_preparation_end` | Between-turn cache preparation boundary. |
| `cache_preparation_failed` | Cache preparation failure recorded. |
| `discord_connected` | Discord transport connected; readiness is not yet established. |
| `discord_ready` | Discord ready to accept supported messages. |
| `discord_resumed` | Discord session resumed after disconnection. |
| `discord_disconnected` | Discord disconnection observed. |
| `discord_received` | Incoming Discord message received. |
| `discord_delivery_start` / `discord_delivery_end` | Discord turn/delivery boundary; inspect the recorded outcome. |
| `discord_local_response` | Response from the local chat connection completed. |
| `discord_send_start` / `discord_send_end` | Sending a group of Discord chunks began/finished. |
| `discord_chunk_sent` | One reply chunk successfully sent. |
| `discord_chunk_failed` | Sending one reply chunk failed. |
| `discord_delivered` | Final answer delivery recorded as complete. |
| `discord_turn_failed` | Discord turn failed; delivery may be partial. |

An `end` label marks a boundary, not guaranteed success. Read its outcome.

## Measurements and evidence

| Term / field | Definition |
|---|---|
| `capacity_tokens` | Total context capacity. |
| `prompt_tokens` | Tokens in a recorded model input. |
| `completion_tokens` | Generated tokens, potentially including reasoning and tool syntax. |
| `total_tokens` | Runtime-reported combined token count for one request. |
| `reply_allowance_tokens` | Generation budget inside the context capacity. |
| `removed_exchanges` | Complete exchanges removed during input-time context fitting. |
| `finish_reason` | Recorded reason generation stopped. |
| Provenance | Source references explaining where a reported fact came from. |
| `null` / unavailable | No usable value was obtained; does not mean false or zero. |
| Incomplete | Required boundaries or evidence are missing. |

Token counts belong to individual requests; do not sum prompt counts into context
usage. Missing errors do not prove success. Expired records cannot be reconstructed
from their IDs. Raw runtime lines are not assigned to a message by proximity alone.

For storage and query details, see [storage](storage.md). For budgets and durability,
see [retention](log-retention.md). The former snapshot utilities have been removed;
this glossary describes the logs and does not define a model-facing request interface.

For application/setup facts and their verification status, see the [setup datasheet](setup-datasheet.md).
