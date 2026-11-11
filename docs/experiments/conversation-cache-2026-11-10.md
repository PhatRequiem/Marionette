# Separate conversations and RAM cache — 2026-11-10

This is a functional experiment, not a replacement for the fixed baseline or a long-session reliability claim. Current behavior is documented in [context](../context.md).

## Configuration and method

Existing llama.cpp b12211, Qwen3.5-4B Q4_K_M, RX 7900 XT Vulkan0; model, precision, reasoning, sampling, and 65,536-token context unchanged. One inference slot; explicit `--cache-ram 9216` (9 GiB). No new dependency or download. Test data, profiles, and server logs were isolated under a temporary directory; no live Discord connection or personal profile was used.

For the cache measurement, create four synthetic token prompts with distinct initial tokens and repeated padding, each exactly 60,000 tokens. Submit A, B, C, D, A, B, C, D to native `/completion`, with `cache_prompt: true` and `n_predict: 1`. Measure elapsed HTTP time and inspect server cache/processing diagnostics. This directly exercises the runtime's near-full context; it does not represent a normal Marionette turn, which reserves 32,768 tokens for generation. The single predicted token is not an answer-quality test.

## Observed results

| Context | Initial request | Cached return |
|---|---:|---:|
| A | 25.493 s | 1.220 s |
| B | 26.101 s | 0.803 s |
| C | 26.306 s | 1.014 s |
| D | 26.306 s | 0.800 s |

Initial requests processed 60,000 prompt tokens. All four returns reported 59,996 reused tokens and four processed tokens. Runtime full-restore diagnostic markers confirmed actual RAM restores, rather than inference based only on elapsed time.

Each saved context used 2,027.125 MiB including checkpoints. Three cached contexts occupied 6,081.376 MiB (about 5.94 GiB), while the fourth was active. The outgoing-save/incoming-restore operation took 738.80–1,160.60 ms. All four returns retained three saved contexts without eviction. This verifies the intended three-cached/one-active pattern for these inputs; the budget is still bytes, not a guaranteed count. Different checkpoint histories, prompt lengths, and tool/template changes can affect retention and reuse.

A separate four-turn application test used linked terminal/Discord identities and the real character tool binding: terminal established a conversation-local marker, Discord established another, and both recalled only their own marker on return. Recorded application histories contained no opposite-conversation marker. The server stopped cleanly afterward. The character profile remained shared by person as designed.

## Automated checks and limits

66 core and 12 mocked Discord checks pass. Coverage includes separate histories at the model-request boundary, conversation-scoped clear, linked character profiles, per-conversation rollover/failure handling, waiting for the previous preparation worker before switching, committing its result to the original history, terminal rendering, and standard launcher arguments. The updated launcher-specific checks also pass separately.

Live forced rollover across multiple conversations was not repeated; rollover ownership is covered by automated tests. Real Discord delivery was not exercised. The timing sample is small and synthetic; it is not a guarantee of the same latency for natural conversations, tool loops, cache misses, or long-running use. Histories remain in process memory until clear/restart; saved logs are not automatically reloaded. No automatic restart of the user's running session was performed.
