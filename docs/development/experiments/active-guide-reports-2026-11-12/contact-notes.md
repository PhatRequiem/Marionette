# contact-notes: archived guide reports

Extracted from [the active guide](../../../active/current-operation/contact-notes.md) on November 12, 2026. These are prior test reports and development notes, not current configuration or newly executed checks. Undated passages retain their original wording; the extraction date is not a test date. Some passages include operational context necessary to interpret the report.

## Original whole-document verification — 2026-11-10 (historical)

The complete regression run passes 63 core and 11 mocked Discord checks. Seven character checks cover exact boundaries, rejected writes, identity/path restrictions, stale edits, disk failure, linked accounts, clear/rollover refresh, same-format restore, and the real Qwen-Agent loop over mocked HTTP responses. The loop test rejects oversized notes, accepts the model's corrected replacement, and retains only the final answer in conversation history.

A local GPU test used the existing Q4 model, normal 65,536 context and sampling settings, and isolated synthetic data. The model proactively saved a hobby and response preference, then answered the hobby question in a new conversation using the saved file. The server shut down afterward. This demonstrates functional persistence and tool use, not long-session reliability, universal recall, or profile accuracy. No real profiles or Discord messages were used.

## Entry-operation verification — 2026-11-10

Twelve character checks cover add/patch/remove, preservation of unrelated notes and the heading, missing/ambiguous/repeated matches, exact whole-entry precedence, duplicate adds, legacy tool-argument rejection, reserved separators, stale edits, write failure, the exact Unicode character boundary, legacy paragraph conversion (including a conversion that would overflow), and same-format backup restoration. Existing current-contact binding, clear/rollover, and mocked Qwen-Agent tool-loop checks remain passing. In total, 70 core and 12 mocked Discord checks pass.

A separate live Q4 test at the normal 65,536 context and 9 GiB RAM-cache setting used synthetic profiles in temporary storage. The model called `add` for a response preference, `patch` to change only that preference's wording, and `remove` for that entry. Disk content was checked after each call, and the runtime shut down cleanly. This verifies all three tool operations, not automatic fact accuracy or guaranteed proactive editing. Existing personal files were not rewritten during development; they will convert on their next successful edit after restart.

---

Synthetic checks cover reference delivery to model input, adding a linked fact and
an unlinked impression, patching/removing linked text, and resolving links after a
contact rename. These are functional checks, not a live model quality evaluation.
Restart main chat to load the prompt and metadata changes. Vault browsing and direct
file editing by the model remain disconnected.

---

Same-format restoration and reopening, plus legacy-paragraph conversion to entries, are tested with synthetic notes, including Unicode and exact-limit content. Cross-database migration is not applicable to this file store and is not claimed. Returning to historical `baseline-v3` does not load contact-note files; preserve them and follow the identity guide's separate registry rollback instructions.

---

Restart Marionette after this update so the running process uses the entry tool rather than the old whole-document tool. Launch commands and linked identity mappings are unchanged.
