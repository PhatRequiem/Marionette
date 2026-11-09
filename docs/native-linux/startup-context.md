# Startup report and context rollover

`session.py` is the terminal client. It starts one pinned `llama-server` on a temporary loopback port, waits for loading, and generates the setup report from diagnostics. No personality file or custom first-message envelope is used.

## Startup report

The report records the observed runtime version, model, selected GPU, layer offload, context capacity, server address, log paths, and capability limits. Original diagnostic evidence is retained in the private `-setup.json` file. The client verifies the context capacity against `/props`; a mismatch stops startup. Missing optional facts remain explicitly unverified. This is not a full requested-versus-loaded configuration audit.

The context limit is capacity, not usage. The report explicitly says it does not measure live token usage. It is a startup snapshot, not continuous monitoring, and cannot guarantee that the model answers accurately. Model-file checksums are verified by setup, not each chat launch.

The report is an ordinary `system` message. User messages and completed assistant replies are kept separately in memory. Every request includes the system message, including after `/clear` and automatic rollover. The snapshot starts with `pending_first_message`; `supplied_with_first_message` is recorded after the first response completes successfully. This confirms a completed request, not model comprehension.

## Automatic rollover

1. Append the new user message to a copy of the active conversation.
2. Ask the local server to format it with the model's native chat template (`/apply-template`, thinking disabled), then count the exact prompt tokens (`/tokenize`, special tokens included).
3. Reserve 512 tokens for the reply at the default 8,192-token capacity. Smaller contexts reserve one quarter of capacity, capped at 512. Leave one additional token spare.
4. If the request does not fit, remove the oldest whole user/assistant exchange and count again. Never remove the system report or shorten the new message.
5. Stream the reply from `/v1/chat/completions`. On success, keep the fitted history and reply. If the request fails, retain the previous history. Partial failed replies may appear in the transcript but are not retained as conversation context.

A message too large to fit with the report and reply allowance is rejected with a visible explanation. A response reaching its allowance is retained and marked in the terminal. Rollover is announced and recorded with prompt counts and removed-exchange counts. It does not summarize or retrieve old conversations. Reprocessing a shortened history may cause a pause; the model remains loaded.

The 8,192-token total includes report, message formatting, active history, and replies. The previously discussed extra 500 tokens have not been added. If the report grows, it leaves less room for history; review the context size and reply allowance when changing it.

## Operation and verification

`/clear` removes active exchanges while keeping the report. `/exit`, Ctrl+D, and Ctrl+C exit the client and shut down its server. The client has no file-reading, browser, command, memory, or attachment tools. Logs are not fed back into the model. Export the matching setup JSON and three text logs together; copying them back does not restore model memory.

Automated checks cover complete-exchange trimming, system preservation, oversized messages, exact budget boundaries, failure recovery, clearing, snapshot provenance, logging, and server lifecycle. Synthetic HTTP tests require local loopback sockets, not internet access. Real GPU checks verified repeated rollover at 1,024 tokens, exact agreement between preflight and server token counts, report retention, oversized-message recovery, and clean shutdown. Normal-capacity checks verify chat and word recall at 8,192 tokens.
