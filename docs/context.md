# Conversation history and context

`conversation.py` owns one shared terminal/Discord history and serializes turns. `inference.py` delegates trimming and streaming to Qwen-Agent 0.0.34. The custom `context.py` and background cache-preparation worker have been removed.

## Budget and trimming

The normal context capacity remains 65,536 tokens. Reasoning and the answer share up to 32,768 tokens; smaller test contexts reserve half their capacity. Qwen-Agent receives an input budget of capacity minus that allowance minus one spare token: normally 32,767.

Qwen-Agent counts message text with its bundled tokenizer. It removes oldest material first and can partially shorten an older message at the boundary, rather than always removing whole exchanges. This is not a summary or persistent memory. There is no separate next-input reserve, log-review window, or background preparation request.

Its estimate does not include the exact loaded model's chat-template overhead. Before generation, the adapter formats the actual trimmed messages through llama.cpp `/apply-template` and counts them through `/tokenize`. It limits generation to the smaller of the configured allowance and actual remaining space, keeping one spare token. If no generation space remains, it rejects the request without changing history.

The latest user message, including sender metadata, must remain unchanged. If the framework would shorten it, the request is rejected and the user is asked to shorten it. Older message text, including old identity labels, can be shortened by the framework.

## History and failures

After a successful nonempty answer, the client saves the exact trimmed messages sent to inference plus the final answer. Removed material therefore does not return on the next turn. A failed or empty response leaves the previous history unchanged. Only answers enter history; reasoning is displayed and logged locally. Discord receives only answers.

Owner-authorized `/clear` clears the shared history. No logs are read back into context, and no tools, personality prompt, setup report, or file-reading access are enabled. The owned loopback server stops when chat exits.

## Timing and visibility

Trimming and prompt evaluation happen when a message is submitted. There is no between-turn cache warmup. This simplifies the client but can put rollover processing back on the response path; it does not promise the former preparation latency. llama.cpp still manages its normal prompt cache.

Launch commands, log files, log windows, timestamps, and shared event numbers are unchanged. Diagnostics record Qwen-Agent message counts, whether history changed, the exact prompt budget, actual runtime token usage, and completion status. The viewer retains support for older preparation entries in saved logs.

See [Qwen-Agent integration](qwen-agent.md) for validation and dependencies, [logs](logs.md) for log formats, and [historical preparation measurements](experiments/idle-rollover.md) for the removed policy. Those historical timings are not measurements of the current implementation.
