# Generated startup context

The launch command stays the same. After the model loads, a small local Python coordinator generates a session report from actual diagnostics and supplies it as factual system context with the first typed message. It adds no personality instructions, file-reading tools, or network service.

## Sequence

1. The launcher creates the chat/debug logs and starts the existing debug terminal.
2. `session.py` starts the pinned `llama-completion` process, copies diagnostics to the debug file, and waits for its first `waiting for user input` event. It does not forward typed input before that event.
3. It records the last reported model name, selected device, GPU layer offload, and loaded context size. The runtime version comes from the launcher's executable version query. Missing observations are explicitly unverified.
4. It saves `-setup.json` with a timestamp, process ID, command, observed values and their original evidence lines, and the exact context text.
5. On the first nonempty user message, it prefixes a private per-session envelope. The Jinja template converts the envelope into a system message followed by the user's actual message. The envelope is not shown as typed input in the chat transcript; the resulting prompt is visible in the debug file.
6. Later input passes through normally. The initial report remains in the current conversation context; it is not regenerated each turn.

This sequencing avoids a second model load and does not require changing the runtime binary. `llama-completion` has no API for revising a system message after startup, so the first-turn formatting carries the report. Its empty closed thinking block is retained.

## Evidence and boundaries

`observed` values are copied from this process's startup diagnostics. `context` also states configured operation and the coordinator's capability boundaries: local offline inference, text conversation, no browsing/file/command tools, and no access to previous logs. These capability statements describe the application, not additional hardware probes. Setup hashes are not reverified during this report. Selecting a device and reporting GPU offload are separate observations; unknown values are not replaced with guessed hardware.

The snapshot records `pending_first_message` initially and `supplied_with_first_message` after the coordinator writes that input. Delivery means supplied to the runtime, not proof that the model understood it. The report is a startup observation, not continuous monitoring. It consumes part of the 8,192-token context and can eventually be affected by context limits. It does not guarantee truthful model answers.

Only successful loading creates a snapshot. A startup failure is logged; a missing readiness event times out after 180 seconds. Exiting before the first message leaves the snapshot marked pending. The files are owner-readable/writable and remain under ignored `data/conversations/`. Export or back up the matching JSON and both text files together. Same-format restoration requires copying them back; the model does not reload them as memory.

This coordinator supports a fresh interactive conversation. Preloaded prompts, user-supplied system prompts, prompt caches, and flags that disable required conversation/logging behavior are rejected. Runtime inspection commands still work without creating a session. Model and context overrides must be checked against the observed report; snapshot parsing is tied to the pinned b12211 diagnostic format and must be retested on upgrades.

## Verification

The real-model test answered its observed model name, RX 7900 XT, 8,192-token context, local execution, and inability to open its own logs. A follow-up recalled a synthetic word. Debug input confirms the report is a system message before the first user message, with the empty thinking block intact.

Run `python -m unittest discover -s tests/native-linux -v` for the regression checks, including snapshot provenance, unknown observations, private portable JSON, one-time delivery, and startup failure without a false verified snapshot. Tests use temporary synthetic data rather than real conversations.
