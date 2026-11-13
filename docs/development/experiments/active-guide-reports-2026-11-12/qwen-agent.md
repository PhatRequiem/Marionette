# qwen-agent: archived guide reports

Extracted from [the active guide](../../../active/current-operation/qwen-agent.md) on November 12, 2026. These are prior test reports and development notes, not current configuration or newly executed checks. Undated passages retain their original wording; the extraction date is not a test date. Some passages include operational context necessary to interpret the report.

## Coordination verification — 2026-11-10 (before contact notes)

52 core and 11 mocked Discord checks pass. The suites cover normal streaming, reasoning separation, unchanged background preparation, command permissions, identities, launcher lifecycle, and shared-library paths. A synthetic tool test drives the real Qwen-Agent loop through HTTP-boundary mocks, verifies tool-result delivery to a second model request, and confirms only the final answer is retained. Unknown tools, incomplete/truncated calls, and oversized follow-up prompts are rejected. Synthetic tools exist only in tests, not in the live launcher.

Full setup verified and reused the existing shared runtime/model and all 68 locked Python packages. A normal 65,536-context GPU session displayed reasoning, answered `2 plus 2 equals 4.`, recorded 124 prompt/841 completion tokens, and shut down cleanly. A separate 8,192-context run exposed only the synthetic test tool: the real Qwen model called it with `coordination-test`, received its result, and gave a final answer. The server stopped cleanly. No personal histories, live Discord DMs, or production tools were used. Background preparation is covered by regression tests; forced GPU rollover was not rerun for this change. This is functional verification, not a claim of improved model quality or long-session reliability. Baseline V3 remains a fixed historical recovery checkpoint.

For current contact-notes tool verification, see [contact notes](../../../active/current-operation/contact-notes.md).

---

Current regression checks cover tool-result replay on the next user turn, preserved
call IDs across multiple calls, sender isolation, input-time and background trimming
of whole exchanges, and native-template preparation with retained evidence. Earlier
verification paragraphs above describe the former final-answer-only policy.
