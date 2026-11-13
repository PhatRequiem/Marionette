# Context rollover and preparation

`src/marionette/session.py` owns one pinned `llama-server` on a temporary loopback port. Startup still checks the loaded context capacity against `/props`. The startup datasheet is refreshed from observations; it is queried on demand. The [soul](soul.md) and editable profile name start blank. Once filled, they supply system context, prepared at startup and refreshed before each ordinary turn. Runtime configuration remains visible in the diagnostic logs.

Reasoning is enabled in the request template and server, with `deepseek` parsing to separate reasoning from final content. There is no separate reasoning cap; reasoning and the answer share the 32,768-token generation allowance. A long reasoning passage can exhaust that allowance before producing a final answer. The client streams reasoning in white and displays final content in pink (buffered until final when tools are enabled), logs completed reasoning, and retains final content and the tool-call/result exchange in active conversation history, but not reasoning content.

`conversation.py` owns separate histories and serializes turns; `context.py` implements fitting and preparation. `inference.py` applies the native template, counts exact tokens, prepares the local cache, and connects Qwen-Agent to the server. [Qwen-Agent coordination](qwen-agent.md) does not trim history; its approximate trimming is disabled. `terminal.py` handles user input and displays streamed reasoning/answers through a callback, so context and inference code have no terminal UI dependency.

## Conversation routing

Histories live in memory under `terminal:<selected-contact-uuid>` and `discord:<sender-account-id>`. Human one-to-one Discord DMs have one sender per conversation, so the account ID is sufficient; group/server chat remains unsupported. The same contact's terminal and Discord histories are separate, while their saved contact notes are shared. New histories start empty, and restarting main chat clears all histories. Logs are retained but never replayed into context.

Every request receives the shared self system prompt plus its own history, current sender metadata (including `conversation_id`), and current contact notes. The main terminal is an operator view of **all** exchanges; it is not itself the model's combined history. Source/sender labels distinguish terminal and Discord activity. `/clear` is allowed only for the resolved sender's originating conversation, including non-owner DMs, and does not delete contact notes or logs.

One server slot handles generation, tool follow-ups, and preparation sequentially. On switching, llama.cpp may save outgoing processed state into RAM and restore a useful token-prefix match. A miss rebuilds the needed context from that conversation's text. Cache eviction does not delete its message history. No custom cache files, conversation-count cap, or separate model instances are added. Message histories are retained until clear/restart; their aggregate Python memory is not bounded by the server's cache budget.

## RAM prompt cache

The launcher sets `--cache-ram 5120`: a **5 GiB (5,120 MiB) system-RAM prompt-cache budget**, with one active inference slot. This is a cache budget, not reserved RAM, a total-process memory limit, or three guaranteed conversation slots. Cached states can include checkpoints; llama.cpp chooses reusable entries by token-prefix matching and evicts entries when needed. The active GPU context and model use VRAM separately.

The RAM cache is independent of the separate message histories. Cache eviction can require rebuilding processed context when switching conversations; it does not reduce the context window or delete history. Check startup diagnostics for `prompt cache is enabled, size limit: 5120 MiB`.

## Between-turn preparation

The total context is 65,536 tokens. The client reserves 2,048 tokens for the next input and 32,768 for reasoning and its answer, inside that total. With the full input allowance, retained history and formatting must fit below 30,720 tokens. Smaller contexts use one eighth of capacity for the input allowance and one half for replies, capped at 2,048 and 32,768 respectively.

After each successful reply, one worker checks the formatted history plus the next-turn formatting. If the allowances would no longer fit, it removes oldest complete exchanges (user input, all assistant/tool calls and results, and final reply) until the history uses at most 75% of capacity and both allowances fit with one spare token. It then processes the retained prefix through `/completion` with `n_predict: 0` and prompt caching enabled. No preparation reply is added to history or printed.

The prefix is produced using the native chat template with a temporary next-user marker. Only the text before that marker is tokenized and prepared; the marker never goes to inference. The final boundary token is left for the actual input to avoid token merging differences. This also ensures Qwen treats the last assistant reply as historical, matching the next real request.

Input remains available during preparation. Before submitting the next message, the client waits for its worker if necessary, then commits the prepared history to the conversation that started it, before switching the active conversation or contact-notes tool. There is only one inference request at a time. Preparation errors retain the original history and are logged; the next request can fall back to ordinary trimming. `/clear` waits for preparation and discards only the originating conversation’s history. Exit shuts down the owned server, including pending preparation.

## Per-message safety and limitations

Each user message carries [sender metadata](contacts.md) as part of its user-role content, counted within the existing budget. Metadata stays with that exchange and is removed with it during rollover; there is no separate identity context window.

Every actual input is formatted with `/apply-template` and counted with `/tokenize`, including special tokens. If the message exceeds the reserved input space, it is still accepted when it fits: oldest complete exchanges are removed as needed to leave the reply allowance and one spare token. A message that cannot fit by itself is rejected without truncation. Failed streams do not add partial replies or the failed input to history.

The allowances are capacity planning, not separate model windows or hard input-length limits. Preparation moves work into reading/typing time; it does not eliminate processing. Rapid submission or an unusually long message can still cause a pause. Old messages are omitted, not summarized. Saved logs are not automatically reloaded as memory. Optional Scarecrow vault reads return selected mirror content through the tool loop; the full mirror is not automatically supplied to the model. The current sender’s [contact notes](contact-notes.md) are supplied afresh in each user-message metadata block and count toward this same budget; rollover does not delete their saved file.

## Logs and checks

The optional [Discord transport](../setup-and-maintenance/discord.md) attaches to the running conversation and shares this policy, with reasoning kept local and final answers delivered by DM.

Each launch records a SQLite session with conversation messages, terminal output, server/model diagnostics, and optional Discord events. These saved records are not automatically restored as model context. See [logs](logs.md) for formats and colors. The two diagnostic windows retain timestamps and shared event numbers. They record preparation start/completion, removed exchanges, cache timings, input-time fallback, and any wait after input. Preparation notices stay out of the chat display.

Run `runtime/agent/bin/python -m unittest discover -s tests/core -v`. Tests use synthetic conversations and loopback sockets. GPU verification must also check cache reuse after preparation; a successful preparation request alone does not prove the next reply avoids reprocessing.

## Tool exchanges

Tool exchanges use Qwen-Agent message records internally. Native rendering converts
them to matching `tool_calls` and `tool_call_id` messages for both counting and
generation. Input-time and background trimming use user-message boundaries rather
than assuming two records per exchange, so they cannot leave an orphan tool result.
Results remain dated evidence; current status still requires a fresh lookup.
Keeping results consumes context space and can cause earlier rollover. The SQLite
conversation schema, diagnostic durability policy, and fresh-history-on-restart
behavior are unchanged. A failed turn still leaves the previous history intact.
