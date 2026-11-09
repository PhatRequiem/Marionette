# Context rollover and preparation

`src/marionette/session.py` owns one pinned `llama-server` on a temporary loopback port. Startup still checks the loaded context capacity against `/props`. No setup report, setup JSON file, personality file, or application system message is generated. Existing reports from older sessions are left untouched. Runtime configuration remains visible in the diagnostic logs.

Reasoning is enabled in the request template and server, with `deepseek` parsing to separate reasoning from final content. There is no separate reasoning cap; reasoning and the answer share the 32,768-token generation allowance. A long reasoning passage can exhaust that allowance before producing a final answer. The client streams reasoning in white and final content in pink, logs completed reasoning, and retains only final content in conversation history.

`conversation.py` owns history and serializes turns; `context.py` implements fitting and preparation. `inference.py` applies the native template and calls the local server. `terminal.py` handles user input and displays streamed reasoning/answers through a callback, so context and inference code have no terminal UI dependency.

## Between-turn preparation

The total context is 65,536 tokens. The client reserves 2,048 tokens for the next input and 32,768 for reasoning and its answer, inside that total. With the full input allowance, retained history and formatting must fit below 30,720 tokens. Smaller contexts use one eighth of capacity for the input allowance and one half for replies, capped at 2,048 and 32,768 respectively.

After each successful reply, one worker checks the formatted history plus the next-turn formatting. If the allowances would no longer fit, it removes oldest complete user/reply pairs until the history uses at most 75% of capacity and both allowances fit with one spare token. It then processes the retained prefix through `/completion` with `n_predict: 0` and prompt caching enabled. No preparation reply is added to history or printed.

The prefix is produced using the native chat template with a temporary next-user marker. Only the text before that marker is tokenized and prepared; the marker never goes to inference. The final boundary token is left for the actual input to avoid token merging differences. This also ensures Qwen treats the last assistant reply as historical, matching the next real request.

Input remains available during preparation. Before submitting the next message, the client waits for its worker if necessary, then adopts the prepared history. There is only one inference request at a time. Preparation errors retain the original history and are logged; the next request can fall back to ordinary trimming. `/clear` waits for any preparation and discards all history. Exit shuts down the owned server, including pending preparation.

## Per-message safety and limitations

Each user message carries [sender metadata](identity.md) as part of its user-role content, counted within the existing budget. Metadata stays with that exchange and is removed with it during rollover; there is no separate identity context window.

Every actual input is formatted with `/apply-template` and counted with `/tokenize`, including special tokens. If the message exceeds the reserved input space, it is still accepted when it fits: oldest complete exchanges are removed as needed to leave the reply allowance and one spare token. A message that cannot fit by itself is rejected without truncation. Failed streams do not add partial replies or the failed input to history.

The allowances are capacity planning, not separate model windows or hard input-length limits. Preparation moves work into reading/typing time; it does not eliminate processing. Rapid submission or an unusually long message can still cause a pause. Old messages are omitted, not summarized. Logs are not automatically reloaded as memory. The model can request bounded active-session evidence through [read_logs](log-reader.md); it has no arbitrary file access.

## Logs and checks

The optional [Discord transport](discord.md) attaches to the running conversation and shares this policy, with reasoning kept local and final answers delivered by DM.

Each chat session saves `-chat.jsonl`, `-server.jsonl`, and `-model.jsonl`; each optional Discord connection also saves its own `-discord.jsonl`. See [logs](logs.md) for formats and colors. The two diagnostic windows retain timestamps and shared event numbers. They record preparation start/completion, removed exchanges, cache timings, input-time fallback, and any wait after input. Preparation notices stay out of the chat display.

Run `python -m unittest discover -s tests/core -v`. Tests use synthetic conversations and loopback sockets. GPU verification must also check cache reuse after preparation; a successful preparation request alone does not prove the next reply avoids reprocessing.

Verified on the pinned runtime and RX 7900 XT at 65,536 tokens; earlier checks used 1,024, 8,192, and 16,384 tokens. See [historical Q4 GPU preparation results](experiments/idle-rollover.md). Q4_K_M is selected again for infrastructure testing; see [current loading and generation verification](experiments/q4-return.md). This switch does not change rollover policy.

## Log tool and context

The read_logs guide/schema is supplied on every model request, including template rendering for token counting and rollover preparation. It uses the existing context capacity, with no additional reserved window or setup report.

Within a turn, sequential log calls have no fixed count limit. Assistant tool-call messages (including that call's reasoning) and tool results exist only in the working request chain, so the template can continue correctly. Each continuation is counted against actual context capacity; preceding generations consume the same per-turn reasoning/answer allowance rather than receiving a fresh 32K budget. Tool choice remains enabled on every continuation; repeated lookups can exhaust the shared allowance without producing an answer. Context snapshots are recorded before the initial generation and each continuation. The log reader labels these as pre-generation measurements, distinct from completed-generation usage.

After a successful turn, history still retains only the user input and final answer. Tool evidence, intermediate commentary, and reasoning stay in saved logs, not future model history. Existing whole-exchange rollover remains unchanged. A later question can request evidence again. /clear resets conversation history but does not revoke access to earlier records in the same active session. Starting a new main session excludes the old session's logs.
