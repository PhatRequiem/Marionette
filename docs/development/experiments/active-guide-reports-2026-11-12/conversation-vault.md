# conversation-vault: archived guide reports

Extracted from [the active guide](../../../active/setup-and-maintenance/conversation-vault.md) on November 12, 2026. These are prior test reports and development notes, not current configuration or newly executed checks. Undated passages retain their original wording; the extraction date is not a test date. Some passages include operational context necessary to interpret the report.

Synthetic launcher tests also verify shutdown exports the last saved messages and
Active documentation, and a failed export leaves the closed session and database
intact with a visible error.

---

Synthetic tests cover literal message preservation, IDs, contact separation,
repeat sync, annotations, stale-page deletion, symlink refusal, missing databases,
contact-local link resolution, migration from the flat layout,
and live reset deleting both generated conversations and annotations. Existing
SQLite backup/restore tests remain separate; this feature adds no restoration or
cross-database migration capability.
