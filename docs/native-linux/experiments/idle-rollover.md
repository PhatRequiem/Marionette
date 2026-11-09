# Between-turn rollover check — 2026-11-08

Environment: pinned llama.cpp b12211, Qwen3.5-4B Q4_K_M, RX 7900 XT with Vulkan, reasoning off, temperature zero. Synthetic sessions used the unchanged `chat.sh` launcher with `MARIONETTE_LOG_DIR` pointing to temporary directories. A temporary terminal-command stub suppressed desktop windows; log routing still ran normally. No real conversation data was used.

## Checks and observations

- At 1,024 tokens, ten prompts containing 45 repetitions of “pebble” forced repeated preparation. Following requests reused 562 cached tokens and processed 111 new prompt tokens. Oversized input (` x` repeated 1,100 times) was rejected, the next request recovered, `/clear` started fresh, and `/exit` removed the owned process and listener.
- At 8,192 tokens, fourteen prompts containing 400 repetitions of “pebble” forced three preparations. Each removed two complete exchanges. The next prompts reused 5,756–5,759 tokens and processed 821–822 new tokens, taking about 272–273 ms of prompt evaluation.
- Preparation took about 1.43 seconds. The test deliberately submitted the next message after approximately one second; the client correctly waited the remaining 408–414 ms before sending it. This verifies early-input coordination, not zero latency. Reading or typing longer than preparation should hide that work; ordinary prompt processing still remains.
- All normal-context requests fit without input-time trimming. `/clear`, subsequent chat, and clean shutdown passed. Both test sizes created the three expected text logs and no setup JSON.

The first experimental prefix ended on an assistant turn. Qwen rendered that differently from historical assistant replies and failed to reuse most of the cache. The final implementation renders through the next user boundary and excludes its temporary marker and last boundary token from prefill. GPU logs verified reuse after that correction.

These measurements are synthetic, not a guarantee for every conversation or GPU load. Large inputs can still require input-time rollover. Preparation does not summarize messages or provide permanent memory.

## Source-layout recheck

After moving application code to `src/marionette/` (commit `e93ad96`), the unchanged launcher completed 17 synthetic replies at 8,192 tokens, including three preparations. The following requests reused 5,756, 5,757, and 5,759 tokens. `/clear`, all three text logs, absence of setup JSON, and removal of the owned server process and listener on exit were verified again. The 20 synthetic regression checks also passed. Desktop log windows were suppressed for this GPU check; viewer behavior is covered separately by the regression suite.

## Thinking-mode recheck

With thinking enabled, a 256-token server thinking cap, and a 1,024-token combined generation allowance, the 8,192-token synthetic session completed 17 replies, automatic preparation, `/clear`, and clean shutdown. Reasoning appeared before final answers and was recorded in the diagnostic logs. After preparation, requests reused the retained cache (for example, 5,767 cached tokens and 12 newly processed tokens). The 21 automated checks also passed, including white reasoning/pink answer output and retaining only final answers. The larger generation reserve can trigger preparation earlier; the context capacity and oldest-pair removal policy are unchanged.

## Doubled token limits

The 16,384-token configuration completed 23 synthetic replies and six rollover preparations on the same GPU, with a 512-token thinking cap and 2,048-token input and combined generation allowances. Following requests reused over 11,000 cached tokens. Preparation took about 2.96 seconds with the larger retained history. `/clear`, fresh generation, and server/socket cleanup passed; all 21 automated checks passed. These timings describe the synthetic run, not a guarantee for every conversation.

## 64K context and recommended sampling

The pinned runtime loaded a 65,536-token context on the RX 7900 XT, allocating 2,048 MiB for the KV cache, 2,603.50 MiB for GPU model weights, 50.25 MiB for recurrent state, and 143.02 MiB for the GPU compute buffer. These are reported buffers, not total process VRAM.

An isolated launcher chat and a synthetic history test verified the 32,768-token request allowance, thinking/final-answer separation, and the effective general-thinking sampling values documented in the setup guide. No separate thinking cap was applied. A 34,306-token synthetic next-turn prompt triggered removal of two oldest exchanges; preparing the retained 30,264-token prefix took about 9.4 seconds. The following reply reused all 30,264 cached tokens and processed 14 new tokens. Generation and server/socket cleanup succeeded. The 22 automated checks passed. This verifies loading, generation, and rollover; it does not benchmark a full 32K-token output or prove that repetitive reasoning is eliminated.
