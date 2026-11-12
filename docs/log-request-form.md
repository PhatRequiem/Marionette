# Log request form

Version 1. Agreed request format only: **no query handler or model connection yet**.
The [JSON Schema](log-request-form.schema.json) defines valid forms. Short field
and evidence definitions are in the [log glossary](log-glossary.md).

## Fields

| Field | Meaning |
|---|---|
| `lookup` | What information to retrieve. |
| `target` | What to inspect. |
| `message_id` | Existing message ID; include only when `target` is `message_id`. |

## Choices

| `lookup` | Allowed `target` | Intended result |
|---|---|---|
| `setup` | `startup` | Latest recorded startup information from the setup datasheet. |
| `status` | `current` | Current server health, Discord connection, available tools and processing state. |
| `processing` | `previous_message` or `message_id` | Message outcome, token usage, model requests, tool calls and available timings. |
| `delivery` | `previous_message` or `message_id` | Reply delivery outcome, including partial delivery. |
| `errors` | `previous_message` or `message_id` | Recognized failures associated with the message. |

`previous_message` means the previous user message in the caller's conversation,
before the user message that triggered this lookup. Tool calls and the lookup
itself do not move that reference point. With no previous message, return unavailable.

## Examples

Startup information:

```json
{"lookup": "setup", "target": "startup"}
```

Current status:

```json
{"lookup": "status", "target": "current"}
```

Previous message processing:

```json
{"lookup": "processing", "target": "previous_message"}
```

Previous reply delivery:

```json
{"lookup": "delivery", "target": "previous_message"}
```

Errors for a specific message (synthetic example ID):

```json
{"lookup": "errors", "target": "message_id", "message_id": "discord:123456789"}
```

## Handler rules for the next step

- The application supplies conversation, access scope and session context. The form accepts no SQL, file paths, contact IDs, session IDs or extra filters.
- Validate the form before reading data. Invalid combinations or extra fields are errors, not silently ignored instructions.
- Resolve message targets only within permitted scope. Reject ambiguous matches across sessions rather than guessing; ID syntax alone does not prove existence or permission.
- Setup is a dated startup record. Current status requires fresh observations; missing observations return unknown. Do not substitute the startup sheet for current status.
- Return a bounded set of relevant facts with observation times and evidence references. Mark missing or incomplete evidence explicitly. Do not claim records expired unless that is established.
- No matching errors does not prove success. Missing delivery records do not prove delivery failure. Unsupported checks return unavailable rather than inferred results.

Date ranges, multi-message searches, field selection and vault search are outside
this first form. A schema-valid request does not yet execute anything. Retrieval,
result formatting, current-status probes and access enforcement remain to be
implemented and tested. Native tool-schema compatibility must be checked before
this contract is registered with the model.
