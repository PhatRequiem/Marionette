# log-retention: archived guide reports

Extracted from [the active guide](../../../active/current-operation/log-retention.md) on November 12, 2026. These are prior test reports and development notes, not current configuration or newly executed checks. Undated passages retain their original wording; the extraction date is not a test date. Some passages include operational context necessary to interpret the report.

## Verification and future regression guardrails

`tests/core/test_ram_logs.py` checks the exact default sizes, no routine payload or
recent-context rows on disk before saving, whole-batch expiry, latest-20 errors,
shutdown save with original IDs, atomic rollback/retry, backup restoration, live
views, ID reservation collisions, oversized-event rejection, EOF/SIGTERM saving,
and the documented loss on recorder SIGKILL. Existing launcher checks exercise
normal exit, Ctrl+C, failed child processes, recorder draining, and conversation
persistence. Tests use isolated databases and synthetic profiles only.

This is not a five-year reliability claim or a live-model performance benchmark.
The no-payload-writes and shutdown tests must remain in place when storage evolves.

Verification of the RAM change: **118 core checks and 13 mocked Discord checks
passed**. A separate actual-size test retained exactly 25 × 20 MB batches in RAM,
confirmed zero diagnostic/event-window rows on disk before shutdown, then saved
the 500 MB buffer and protected error evidence with SQLite integrity intact.
The synthetic database was removed; the user's running session was not changed.
