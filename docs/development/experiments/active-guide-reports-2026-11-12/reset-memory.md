# reset-memory: archived guide reports

Extracted from [the active guide](../../../active/current-operation/reset-memory.md) on November 12, 2026. These are prior test reports and development notes, not current configuration or newly executed checks. Undated passages retain their original wording; the extraction date is not a test date. Some passages include operational context necessary to interpret the report.

## Verification

Synthetic checks cover owner commands from terminal and Discord, non-owner rejection, arbitrary stream-marker chunk boundaries, stale disk writers, old RAM suppression on interrupted reset, ID/account preservation, blank soul, local-copy deletion, and normal shutdown after reset. A launcher test runs a conversation, resets, continues chatting using the same server process, and verifies that old conversation text does not return after recorder shutdown. Existing RAM tests still verify no routine diagnostic payload writes and orderly shutdown saving.

These tests establish application behavior, not answer quality or long-session reliability. Mocked Discord tests do not establish live Discord delivery. No private conversation is used as test data.

A real Q4 GPU smoke test in temporary synthetic storage generated before and after `/resetmemory` with one model load, retained only the post-reset conversation, and shut down with SQLite integrity intact. The personal instance was left stopped and no live Discord message was sent. This establishes loading and short functional generation, not broader quality, performance, or long-session reliability.

Verification: 134 core regression checks and 14 mocked Discord checks passed, plus the isolated live GPU reset test.
