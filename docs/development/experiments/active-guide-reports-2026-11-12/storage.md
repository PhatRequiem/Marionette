# storage: archived guide reports

Extracted from [the active guide](../../../active/current-operation/storage.md) on November 12, 2026. These are prior test reports and development notes, not current configuration or newly executed checks. Undated passages retain their original wording; the extraction date is not a test date. Some passages include operational context necessary to interpret the report.

## Verification of this change

On November 11, 2026, an isolated normal-launcher GPU check used synthetic profiles and a separate database. The unchanged Q4 model answered `2 + 2` with `4`; input, reasoning, and answer were stored separately, 7,806 diagnostic records and the terminal stream were saved, integrity checking passed, and the session/server ended cleanly. All 106 automated checks passed (93 core and 13 mocked Discord), including Ctrl+C shutdown with recorder draining. The then-existing message snapshot utility successfully read exports from the GPU session; that utility has since been removed. Mocked Discord integration verifies attachment, reconnection, metadata/delivery events, local reasoning, and answers-only delivery without a live Discord login. These checks establish recording and basic functionality, not long-session reliability, answer quality, or a performance improvement.

---

Synthetic tests verify same-version SQLite backup restoration and SQL export/import into a fresh SQLite file, including raw bytes, messages, IDs, and timestamps. **Migration to a different database engine is not implemented or verified.** Unexpected schema versions fail explicitly; there is no silent reset. No old-text import is implemented.

---

Synthetic checks verify schema-4 backfill, indexed lookup, raw-byte/ID preservation,
protected evidence after rolling eviction, shutdown saving, and reset deletion.
The storage suite separately checks same-version backup restore and SQL export/import;
these are SQLite tests, not cross-engine migration verification.
