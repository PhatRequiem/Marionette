# Standalone snapshot

One report interface combines optional `setup` and `message` sections. It remains
**disconnected from main chat, prompts, Qwen-Agent and Discord**. No live probes,
model requests, report files or memory writes are performed. Diagnostic RAM
retention and shutdown saving are unchanged.

## Commands

```bash
# Setup only, with unknown runtime facts
./scripts/native-linux/snapshot.sh
# Synthetic setup example, not live observations
./scripts/native-linux/snapshot.sh --evidence tests/fixtures/startup-observations.json
# One saved message
./scripts/native-linux/snapshot.sh --section message \
  --database data/conversations/marionette.sqlite3 --session SESSION_UUID \
  --message-id 'discord:INCOMING_MESSAGE_ID' --conversation-id 'discord:SENDER_ACCOUNT_ID'
# Combined: use the same message arguments and add setup evidence
./scripts/native-linux/snapshot.sh --section both --evidence /path/to/observations.json \
  --database data/conversations/marionette.sqlite3 --session SESSION_UUID \
  --message-id 'discord:INCOMING_MESSAGE_ID' --conversation-id 'discord:SENDER_ACCOUNT_ID'
```

Replace example paths and IDs with actual values. Text logs and `--discord-log`
remain supported as described in [message extraction](log-snapshots.md).
The existing `startup-snapshot.sh` and `log-snapshot.sh` commands delegate to this
interface, defaulting to `setup` and `message` respectively. Their arguments remain
supported; **their JSON output now uses the unified envelope**. Consumers must
read `setup` or `message` instead of the previous top-level report fields.

## Report and evidence

The schema-1 envelope contains `report_type: snapshot`, creation time,
`connected_to_model: false`, `setup`, `message`, and limitations. An unrequested
section is `null`. Requested setup without evidence has unverified facts.

Setup includes model/runtime, device, local inference, configured limits,
interfaces, available tools and separately labeled application-design descriptions.
See [setup evidence format](startup-snapshot.md). Each setup fact carries its
status plus source, observation time, synthetic flag and optional session.
Caller-supplied values are never promoted to verified observations.

Message evidence retains processing, actual request budgets and usage, tool calls,
cache preparation, delivery, errors and event references. Its old always-null
`model` and `connections` placeholders are removed from the unified report;
setup is the single location for that information. Setup currently reports
terminal availability and Discord connection status, not model-server health.
Available tools and tools actually called remain distinct.

For combined reports with populated setup values, evidence must include a
nonempty top-level `session` matching the selected database session UUID (or the
session filename stem in text mode). Missing or mismatched session evidence fails.
This is a caller assertion and consistency check, not independent authentication.
Observation timestamps remain visible: setup is an observation at that time,
not a claim about the configuration or connectivity at the message's time.
Current application-design descriptions likewise do not establish archived behavior.
Setup never fills or overwrites historical message fields. Missing historical
facts stay unavailable; different recorded budgets are preserved, not reconciled.

The combined report is bounded to 128 KiB. Existing input bounds and scope checks
remain in effect. Invalid input fails with no partial JSON. Both collectors stay
small and independent behind the common interface; no runtime evidence collector
has been added. Model connection, live RAM access and verified runtime collection
require separate implementation. A future model-facing adapter must bind permitted
sessions and conversations itself.

## Verification

```bash
python -m unittest discover -s tests/core -p 'test_*snapshot.py' -v
```

Synthetic tests cover evidence scope, preservation of observation time/status,
independent budgets, missing facts, compatibility command output, input rejection,
message extraction and read-only behavior. They do not establish live runtime
accuracy or model understanding.
