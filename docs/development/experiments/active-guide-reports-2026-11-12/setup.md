# setup: archived guide reports

Extracted from [the active guide](../../../active/setup-and-maintenance/setup.md) on November 12, 2026. These are prior test reports and development notes, not current configuration or newly executed checks. Undated passages retain their original wording; the extraction date is not a test date. Some passages include operational context necessary to interpret the report.

The client was checked with isolated real GPU sessions, including repeated context rollover, oversized-input recovery, synthetic word recall, fresh history after `/clear`, full debug logging, loopback-only listening, `/exit` with status zero, and disappearance of both the runtime process and listener. Check the current listener with `ss -lntp` while chatting; only `127.0.0.1:<temporary port>` should belong to this `llama-server` process.

---

For the current weight format and smoke-test result, see [4B return verification](../4b-return-2026-11-12.md). [BF16 measurements](../bf16-switch.md) and earlier Q4 experiments are historical.

---

Current tool-coordination setup and verification are documented in [Qwen-Agent coordination](../../../active/current-operation/qwen-agent.md). The runtime and sampling settings remain unchanged by the return to 4B; the manifest now selects the 4B model path.

---

Historical reports and the fixed `baseline-v3` tag still describe the previous checkout-local model paths. An old checkpoint's setup will use its old location; follow this guide for the current checkout. The retained BF16 file is not automatically downloaded by current setup. Back it up separately if wanted; moving models on the same disk is not a backup.
