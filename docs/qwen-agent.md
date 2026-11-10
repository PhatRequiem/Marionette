# Qwen-Agent integration

Main chat uses **Qwen-Agent 0.0.34** for history trimming, model message conversion, and streamed reasoning/answer assembly. llama.cpp still runs the Q4 model locally. No tools, log access, document retrieval, extra context allocation, personality, or background tasks are enabled. The launch commands and text logs remain the same.

## Ownership

`src/marionette/inference.py` uses Qwen-Agent's `TextChatAtOAI` model interface with `use_raw_api=True`. This is the model-request part of the framework, not its document-reading `Assistant` or a tool-execution agent. A future tool integration is a separate change.

Marionette continues to own identities, shared terminal/Discord history, permissions, a final exact token check, server lifetime, and UI. The existing callbacks receive incremental reasoning and answer text derived from Qwen-Agent's accumulated messages. Only final answer text enters history or Discord.

The adapter replaces Qwen-Agent's `_chat_complete_create` hook with a locally configured OpenAI-compatible SDK client. It observes completion status and usage, which the framework otherwise drops. The SDK parses the HTTP event stream; we do not maintain a second SSE parser. Missing completion status rejects a partial response. Tool calls are rejected because no tools are enabled. This hook is specific to the pinned release and must be checked on upgrade.

## Settings preserved

- Local loopback endpoint, explicit placeholder API key, no inherited HTTP proxies, no automatic request retries, 120-second request timeout.
- No added system message (the pinned release's default is empty). The newest input, including sender metadata, must survive trimming unchanged.
- Qwen-Agent trims to `max_input_tokens = capacity - reply_allowance - 1` (32,767 normally). Native `/apply-template` and `/tokenize` check the resulting prompt; reply allowance is reduced if needed to fit actual remaining capacity. See [context policy](context.md).
- Context remains 65,536; reasoning and answer share up to 32,768 tokens. No additional 32K log-review allocation.
- Thinking stays enabled. Requests leave sampling parameters to the existing explicitly configured server; `seed=-1` preserves random seeding rather than Qwen-Agent choosing a seed.
- No framework response cache, document workspace, retrieval configuration, tool schema, or file access is supplied.

## Installation and upgrades

Run `./scripts/native-linux/setup-agent.sh` for an existing checkout, or `python scripts/native-linux/setup.py` for complete setup. Both use the hash-locked `scripts/native-linux/agent-requirements.txt` and install under `runtime/agent/`. The launcher uses that environment only for the main session; log viewers use system Python and Discord keeps its separate environment. No service or login is installed.

Qwen-Agent's minimal dependency metadata omits NumPy, SoundFile, tqdm, and python-dateutil, despite importing them at startup in 0.0.34. They are explicitly included in `agent-requirements.in`. Their presence does not enable audio or Python execution. Dependencies and licenses are listed in [licenses](licenses.md).

For an intentional dependency update, edit the input requirements, regenerate the lock with `uv pip compile --python python --generate-hashes scripts/native-linux/agent-requirements.in -o scripts/native-linux/agent-requirements.txt`, rerun setup, and repeat validation. The current lock was resolved on Python 3.14.8/x86_64 Linux; other Python/platform combinations are not verified.

## Verification (2026-11-09)

36 core and 11 mocked Discord tests pass. They cover framework trimming, retaining the exact outgoing history, unchanged newest input, rejection of oversized messages, exact remaining generation space, failed/empty response rollback, reasoning display, identities, permissions, shared Discord/terminal routing, and shutdown. Obsolete custom-preparation tests were replaced, not retained as coverage of the new policy.

An isolated real GPU run at a deliberately small 2,048-token context forced trimming on two consecutive requests and answered `4` and `2`. Exact counts matched server usage (1,042 and 1,051 prompt tokens); generation allowances were safely reduced to 1,005 and 996 tokens. The server stopped cleanly. This verifies trimming and subsequent generation, not long-session reliability, improved quality, or unchanged rollover latency. A separate normal 65,536-token session displayed reasoning and answered `4`, recorded 132 prompt and 428 completion tokens, and exited with status zero after stopping its server. No personal history or live Discord messages were used. Baseline V3 remains a fixed historical checkpoint predating this integration.

Official references: [Qwen-Agent repository](https://github.com/QwenLM/Qwen-Agent), [Qwen3.5 example](https://github.com/QwenLM/Qwen-Agent/blob/main/examples/assistant_qwen3.5.py), [Qwen3.5-4B guidance](https://huggingface.co/Qwen/Qwen3.5-4B). The upstream Qwen3.5 example uses the native API mode; our text-only adapter retains the same template and reasoning settings already used by this project.
