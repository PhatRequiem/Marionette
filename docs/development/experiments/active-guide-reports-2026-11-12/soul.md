# soul: archived guide reports

Extracted from [the active guide](../../../active/current-operation/soul.md) on November 12, 2026. These are prior test reports and development notes, not current configuration or newly executed checks. Undated passages retain their original wording; the extraction date is not a test date. Some passages include operational context necessary to interpret the report.

The [original starting description](../../history/marionette-starting-sheet.md) is a historical reference from the earlier assigned-identity experiment. It is preserved for comparison and is no longer loaded by the application. Its consciousness statement was a user-supplied premise, not a verified finding.

---

## Verification

Tests cover blank initialization without a system message, name-only and description-only edits, clearing both fields, exact Unicode limits, stale edits, failed writes, immutable UUIDs, revision preservation, same-version restoration, schema migration, and the real Qwen-Agent loop over mocked HTTP. Cross-conversation refresh, clear, rollover, and separation from contact notes remain covered. These tests establish functional behavior, not consciousness, spontaneous self-editing, or long-session reliability.

Verification on 2026-11-11: 124 core and 13 mocked Discord checks passed. A live Q4 GPU test used isolated synthetic storage, started without custom system context, set both a name and description through the real tool, preserved the UUID and blank starting revision, recalled the saved description in a separate Discord-routed conversation, and reopened the saved data. No live Discord messages or test content in real profiles were used. The edit was explicitly requested in the test; spontaneous tool use is not established.

Contact/soul rename verification: 127 core and 13 mocked Discord tests pass, including legacy path migration, SQLite contact-column migration, and renamed tool calls through the Qwen-Agent loop. These checks do not establish that proactive soul updates or trait attribution are reliable. See [path migration](../../../active/current-operation/contacts.md#contactsoul-path-migration).

---

Same-version backup restoration and schema-1-to-2 migration are covered with synthetic data. Cross-database migration is not implemented or claimed. Back up contact profiles and conversations separately using their guides. A persistent UUID does not establish continuity of consciousness.

---

This removes application-authored self-description; it does not disable native chat-template/tool formatting or Qwen's learned identity. Changing the description may invalidate cached prefixes. Startup preparation does not guarantee cache reuse. Model weights, sampling, reasoning, launch commands, dependencies, and diagnostic RAM policy are unchanged. Restart an existing chat to use this code.
