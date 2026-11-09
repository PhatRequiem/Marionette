# Current baseline

Reviewed November 9, 2026. This is the current supported base; the [original direct-inference baseline](experiments/baseline-v1.md) is historical.

## Boundaries

- One local llama.cpp b12211 server, owned by the terminal client; no persistent service.
- Qwen3.5-4B BF16, Vulkan0, 65,536-token context, 32,768-token combined reasoning/answer allowance. Publisher sampling settings remain explicit in the launcher; see [setup](setup.md).
- One shared conversation, optional owner-only Discord DMs, sequential generation. Reasoning stays local; only final answers are delivered to Discord.
- Oldest complete exchanges removed as needed, with cache preparation after replies. No personality file, setup report, tools, summaries, or persistent model memory.
- Three files per chat session, plus one file per optional Discord connection. See [logs](logs.md) for formats, colors, and recovery.

## Maintenance checks

Run from the checkout:

```bash
python -m unittest discover -s tests/native-linux -v
runtime/discord/bin/python -m unittest discover -s tests/discord -v
bash -n scripts/native-linux/*.sh
```

All 42 checks passed in this review (30 core, 12 Discord), along with shell syntax and documentation-link checks. The code cleanup used synthetic tests; the subsequent [BF16 switch](experiments/bf16-switch.md) also passed an isolated real GPU chat. No live Discord messages were sent for either check.

The tests use temporary data, a synthetic local server, and mocked Discord delivery. They cover budgets, rollover and cache boundaries, failed turns, shared history, process cleanup, owner filtering, delivery, and log preservation/presentation. They do not establish live GPU throughput or Discord connectivity. Earlier GPU measurements remain in [the rollover experiment](experiments/idle-rollover.md).

The cleanup removes repeated per-chunk terminal color changes and the Discord result handoff's polling delay (previously up to 100 ms). Token counting, model settings, retained context, and full diagnostic logging are unchanged. Exact counting still requires local requests, debug logging writes every event, and a message sent before preparation finishes can still wait. These are deliberate baseline tradeoffs, not claims of fully optimized inference.

Restart main chat and reconnect Discord after code updates. Updating files does not change an already running session.
