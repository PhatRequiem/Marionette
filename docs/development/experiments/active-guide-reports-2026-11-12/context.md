# context: archived guide reports

Extracted from [the active guide](../../../active/current-operation/context.md) on November 12, 2026. These are prior test reports and development notes, not current configuration or newly executed checks. Undated passages retain their original wording; the extraction date is not a test date. Some passages include operational context necessary to interpret the report.

This setting takes effect on the next main-chat launch. The RAM cache is an optimization independent of the separate message histories. The reduced budget can retain fewer processed conversation states; switching may require rebuilding context more often. It does not reduce the context window or delete conversation history. Verify the startup diagnostic reports `prompt cache is enabled, size limit: 5120 MiB` after restarting. Background preparation and the existing token allowances are unchanged.

---

Verified on the pinned runtime and RX 7900 XT at 65,536 tokens; earlier checks used 1,024, 8,192, and 16,384 tokens. See [historical Q4 GPU preparation results](../idle-rollover.md). Q4_K_M is selected again for infrastructure testing; see [current loading and generation verification](../q4-return.md). This switch does not change rollover policy.

---

## Separate-conversation verification

See [the November 10 cache-switch experiment](../conversation-cache-2026-11-10.md): 66 core and 12 mocked Discord checks pass. A real GPU run retained three 60,000-token cached contexts with one active slot under the previous 9 GiB budget; cached returns took 0.80–1.22 seconds versus 25.5–26.3 seconds initially. Those results used the previous budget, not the current 5 GiB setting; they are synthetic cache timings, not promised full-response latency. Separate linked terminal/Discord histories were also checked with real generation.
