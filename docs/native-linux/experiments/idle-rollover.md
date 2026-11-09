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
