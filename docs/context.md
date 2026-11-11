# Context rollover and preparation

`src/marionette/session.py` owns one pinned `llama-server` on a temporary loopback port. Startup still checks the loaded context capacity against `/props`. No setup report or setup JSON file is generated. The [self character sheet](self-character.md) supplies a system prompt that is prefilled at startup and refreshed before each ordinary turn. Existing reports from older sessions are left untouched. Runtime configuration remains visible in the diagnostic logs.

Reasoning is enabled in the request template and server, with `deepseek` parsing to separate reasoning from final content. There is no separate reasoning cap; reasoning and the answer share the 32,768-token generation allowance. A long reasoning passage can exhaust that allowance before producing a final answer. The client streams reasoning in white and displays final content in pink (buffered until final when tools are enabled), logs completed reasoning, and retains only final content in conversation history.

`conversation.py` owns separate histories and serializes turns; `context.py` implements fitting and preparation. `inference.py` applies the native template, counts exact tokens, prepares the local cache, and connects Qwen-Agent to the server. [Qwen-Agent coordination](qwen-agent.md) does not trim history; its approximate trimming is disabled. `terminal.py` handles user input and displays streamed reasoning/answers through a callback, so context and inference code have no terminal UI dependency.

## Conversation routing

Histories live in memory under `terminal:<selected-person-uuid>` and `discord:<sender-account-id>`. Human one-to-one Discord DMs have one sender per conversation, so the account ID is sufficient; group/server chat remains unsupported. The same person's terminal and Discord histories are separate, while their saved character notes are shared. New histories start empty, and restarting main chat clears all histories. Logs are retained but never replayed into context.

Every request receives the shared self system prompt plus its own history, current sender metadata (including `conversation_id`), and current character profile. The main terminal is an operator view of **all** exchanges; it is not itself the model's combined history. Source/sender labels distinguish terminal and Discord activity. `/clear` is allowed only for the resolved sender's originating conversation, including non-owner DMs, and does not delete character notes or logs.

One server slot handles generation, tool follow-ups, and preparation sequentially. On switching, llama.cpp may save outgoing processed state into RAM and restore a useful token-prefix match. A miss rebuilds the needed context from that conversation's text. Cache eviction does not delete its message history. No custom cache files, conversation-count cap, or separate model instances are added. Message histories are retained until clear/restart; their aggregate Python memory is not bounded by the server's cache budget.

## RAM prompt cache

The launcher sets `--cache-ram 9216`: a **9 GiB (9,216 MiB) system-RAM prompt-cache budget**, with one active inference slot. This is a cache budget, not reserved RAM, a total-process memory limit, or three guaranteed conversation slots. Cached states can include checkpoints; llama.cpp chooses reusable entries by token-prefix matching and evicts entries when needed. The active GPU context and model use VRAM separately.

This setting takes effect on the next main-chat launch. The RAM cache is an optimization independent of the separate message histories. Three cached conversations are a target, not a guaranteed entry count. Verify the startup diagnostic reports `prompt cache is enabled, size limit: 9216 MiB` after restarting. Background preparation and the existing token allowances are unchanged.

## Between-turn preparation

The total context is 65,536 tokens. The client reserves 2,048 tokens for the next input and 32,768 for reasoning and its answer, inside that total. With the full input allowance, retained history and formatting must fit below 30,720 tokens. Smaller contexts use one eighth of capacity for the input allowance and one half for replies, capped at 2,048 and 32,768 respectively.

After each successful reply, one worker checks the formatted history plus the next-turn formatting. If the allowances would no longer fit, it removes oldest complete user/reply pairs until the history uses at most 75% of capacity and both allowances fit with one spare token. It then processes the retained prefix through `/completion` with `n_predict: 0` and prompt caching enabled. No preparation reply is added to history or printed.

The prefix is produced using the native chat template with a temporary next-user marker. Only the text before that marker is tokenized and prepared; the marker never goes to inference. The final boundary token is left for the actual input to avoid token merging differences. This also ensures Qwen treats the last assistant reply as historical, matching the next real request.

Input remains available during preparation. Before submitting the next message, the client waits for its worker if necessary, then commits the prepared history to the conversation that started it, before switching the active conversation or character tool. There is only one inference request at a time. Preparation errors retain the original history and are logged; the next request can fall back to ordinary trimming. `/clear` waits for preparation and discards only the originating conversation’s history. Exit shuts down the owned server, including pending preparation.

## Per-message safety and limitations

Each user message carries [sender metadata](identity.md) as part of its user-role content, counted within the existing budget. Metadata stays with that exchange and is removed with it during rollover; there is no separate identity context window.

Every actual input is formatted with `/apply-template` and counted with `/tokenize`, including special tokens. If the message exceeds the reserved input space, it is still accepted when it fits: oldest complete exchanges are removed as needed to leave the reply allowance and one spare token. A message that cannot fit by itself is rejected without truncation. Failed streams do not add partial replies or the failed input to history.

The allowances are capacity planning, not separate model windows or hard input-length limits. Preparation moves work into reading/typing time; it does not eliminate processing. Rapid submission or an unusually long message can still cause a pause. Old messages are omitted, not summarized. Logs are never reloaded as memory and the model has no general file-reading tools. The current sender’s [character notes](characters.md) are supplied afresh in each user-message metadata block and count toward this same budget; rollover does not delete their saved file.

## Logs and checks

The optional [Discord transport](discord.md) attaches to the running conversation and shares this policy, with reasoning kept local and final answers delivered by DM.

Each launch records a SQLite session with conversation messages, terminal output, server/model diagnostics, and optional Discord events. These saved records are not automatically restored as model context. See [logs](logs.md) for formats and colors. The two diagnostic windows retain timestamps and shared event numbers. They record preparation start/completion, removed exchanges, cache timings, input-time fallback, and any wait after input. Preparation notices stay out of the chat display.

Run `runtime/agent/bin/python -m unittest discover -s tests/core -v`. Tests use synthetic conversations and loopback sockets. GPU verification must also check cache reuse after preparation; a successful preparation request alone does not prove the next reply avoids reprocessing.

Verified on the pinned runtime and RX 7900 XT at 65,536 tokens; earlier checks used 1,024, 8,192, and 16,384 tokens. See [historical Q4 GPU preparation results](experiments/idle-rollover.md). Q4_K_M is selected again for infrastructure testing; see [current loading and generation verification](experiments/q4-return.md). This switch does not change rollover policy.

## Separate-conversation verification

See [the November 10 cache-switch experiment](experiments/conversation-cache-2026-11-10.md): 66 core and 12 mocked Discord checks pass. A real GPU run retained three 60,000-token cached contexts with one active slot under the 9 GiB budget; cached returns took 0.80–1.22 seconds versus 25.5–26.3 seconds initially. These are synthetic cache timings, not promised full-response latency. Separate linked terminal/Discord histories were also checked with real generation.
