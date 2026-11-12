# Qwen-Agent tool coordination

Marionette uses pinned **Qwen-Agent 0.0.34** for model streaming and its `FnCallAgent` tool loop. The registered production tools are `update_contact_notes` (add, patch, or remove an individual entry), bound to the current sender’s [contact notes](contact-notes.md), `update_soul`, bound to [Marionette’s soul](soul.md), and read-only `read_docs`, connected to the [docs Obsidian vault](obsidian.md). `query_logs` is disconnected from production but retained for operator use and tests. There is no unrestricted retrieval, skill creation, scheduler, shell access, or automatic tool discovery. Ordinary terminal and Discord chat still work as before.

## Responsibilities

- `coordination.py` inherits Qwen-Agent's model → tool → result → model loop. It accepts only explicit `BaseTool` objects with JSON Schema parameter objects (required by llama.cpp’s native tool API); no tool names, MCP configurations, or automatic file attachments are accepted. The application supplies the current-contact and soul update tools and the docs vault read tool. Other tools must be separately implemented, authorized, and registered in code.
- The coordinator uses Qwen-Agent's public `Agent` initializer instead of `FnCallAgent`'s file-memory initializer. This avoids constructing its document parser and retrieval components. The inference adapter composes enabled [feature instructions](../prompts/README.md) before the current soul in the system message. Its inherited loop and override hooks are tested against the pinned release.
- `inference.py` supplies the local OpenAI-compatible transport with proxy inheritance and automatic retries disabled. Qwen-Agent assembles streamed messages; the SDK parses HTTP events. Our adapter preserves completion status and actual token usage, and normalizes the pinned framework's legacy tool-result `id` to `tool_call_id` for llama.cpp.
- `conversation.py` and `context.py` maintain separate conversation histories, exact token fitting, whole-exchange removal, and background cache preparation after replies. Qwen-Agent trimming is disabled with `max_input_tokens=0`. Launch commands, shared terminal/Discord identity, colors, logs, model, context capacity, and sampling configuration remain unchanged.

## Tool-turn behavior and boundaries

Registered tool schemas are included in exact native template counting and cache preparation. Every model request in the tool loop is checked against the context capacity and existing reply allowance. An oversized tool result fails the turn instead of silently trimming history. The allowance applies per model request; Qwen-Agent's default limit is 20 model calls per turn (upstream allows `QWEN_AGENT_MAX_LLM_CALL_PER_RUN` to override it). Exhausting that loop without a final response is an error, not a successful answer.

Only registered tools can execute. Unknown tool names, interrupted tool streams, truncated tool requests, and shutdown prevent dispatch. Tools are called through Qwen-Agent; ordinary tool exceptions are returned to the model by the framework. Future tools must enforce their own argument, access, and authorization rules; this coordinator is not a filesystem sandbox or a complete permission system.

Reasoning stays in local display/logs. With tools enabled, intermediate assistant text is withheld until the final response so it is not mistaken for the answer. The contact-notes tool is registered on ordinary messages, so final answers are buffered while reasoning streams. Successful turns retain the user input, intermediate assistant/tool-call messages, tool results and final answer in the originating conversation’s active context. Reasoning content is omitted from replay. The next turn receives those calls/results through Qwen-Agent, without re-executing old calls. Token counting and cache preparation use the same native message conversion. Trimming removes the entire exchange at its next user boundary. This does not add durable tool-result storage or reload history after restart. Contact notes persist separately. Failed turns leave conversation history unchanged, but successful contact-note writes are not automatically undone.

Model-request and tool-call start/end markers, each tool-loop prompt budget, model usage, and completed reasoning use the existing diagnostic stream. [Per-message request/tool IDs](logs.md#model-requests-and-tool-calls-within-a-message) link each call and its outcome; tool identity records also preserve the protocol call ID. A tool ending with `returned` can contain an error result and does not certify domain success. No extra log files are created. No tools are sent to Discord; it continues to receive final answers and existing status/error notices.

## Setup and upgrades

For an existing checkout run `./scripts/native-linux/setup-agent.sh`. Complete installation through `python scripts/native-linux/setup.py` also invokes it after verifying the existing shared model and inference engine. The launcher runs main chat with `runtime/agent/bin/python`; viewers keep system Python and Discord keeps its own environment.

The hash-locked `scripts/native-linux/agent-requirements.txt` pins the core framework and dependencies. No optional GUI, RAG, code-interpreter, or MCP extras are installed. Upstream's 0.0.34 minimal metadata omits NumPy, SoundFile, tqdm, and python-dateutil despite startup imports, so they are explicit requirements. Their installation does not enable those capabilities. See [licenses](licenses.md).

To deliberately upgrade, edit `agent-requirements.in`, regenerate with `uv pip compile --python python --generate-hashes scripts/native-linux/agent-requirements.in -o scripts/native-linux/agent-requirements.txt`, rerun setup, and retest the adapter, tool-result schema, inherited loop, native budgets, and background preparation. Current verification uses Python 3.14.8 on x86_64 Linux.

## Coordination verification — 2026-11-10 (before contact notes)

52 core and 11 mocked Discord checks pass. The suites cover normal streaming, reasoning separation, unchanged background preparation, command permissions, identities, launcher lifecycle, and shared-library paths. A synthetic tool test drives the real Qwen-Agent loop through HTTP-boundary mocks, verifies tool-result delivery to a second model request, and confirms only the final answer is retained. Unknown tools, incomplete/truncated calls, and oversized follow-up prompts are rejected. Synthetic tools exist only in tests, not in the live launcher.

Full setup verified and reused the existing shared runtime/model and all 68 locked Python packages. A normal 65,536-context GPU session displayed reasoning, answered `2 plus 2 equals 4.`, recorded 124 prompt/841 completion tokens, and shut down cleanly. A separate 8,192-context run exposed only the synthetic test tool: the real Qwen model called it with `coordination-test`, received its result, and gave a final answer. The server stopped cleanly. No personal histories, live Discord DMs, or production tools were used. Background preparation is covered by regression tests; forced GPU rollover was not rerun for this change. This is functional verification, not a claim of improved model quality or long-session reliability. Baseline V3 remains a fixed historical recovery checkpoint.

For current contact-notes tool verification, see [contact notes](contact-notes.md).

Official references: [Qwen-Agent](https://github.com/QwenLM/Qwen-Agent), [function-call agent](https://github.com/QwenLM/Qwen-Agent/blob/main/qwen_agent/agents/fncall_agent.py), [Qwen3.5 native API example](https://github.com/QwenLM/Qwen-Agent/blob/main/examples/assistant_qwen3.5.py).

Current regression checks cover tool-result replay on the next user turn, preserved
call IDs across multiple calls, sender isolation, input-time and background trimming
of whole exchanges, and native-template preparation with retained evidence. Earlier
verification paragraphs above describe the former final-answer-only policy.
