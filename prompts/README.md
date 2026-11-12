# Application prompts

Concise behavior guidance, separate from the editable soul and native tool schemas.

| File | Loaded when |
|---|---|
| `tool-guidance.md` | Any supported tool is registered |
| `log-queries.md` | `query_logs` is registered (enabled in production) |
| `docs-vault.md` | `read_docs` is registered |
| `contact-notes.md` | `update_contact_notes` is registered |
| `scratchpads.md` | `update_scratchpad` is registered |
| `soul.md` | `update_soul` is registered |

`API.with_system()` composes only enabled sections, then appends the current saved
name and soul description. The soul remains editable and refreshes on subsequent
turns. These files do not set a fixed personality or grant tool permissions.

Qwen-Agent uses the native API (`use_raw_api=True`): tool definitions travel in
`tools`, while guidance and personal context travel in the system message.
Qwen's chat template formats them for the model. Do not manually duplicate tool
schemas or add another tool-call syntax to these instructions. See the official
[Qwen3.5 Qwen-Agent example](https://github.com/QwenLM/Qwen-Agent/blob/main/examples/assistant_qwen3.5.py)
and [Qwen3.5-4B chat template](https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/chat_template.jinja).
The wording and brevity here are project choices, not a prescribed Qwen prompt.

Guidance participates in exact counting, generation and cache preparation. Files
are cached per API instance: restart chat after editing. Missing/empty files fail
visibly. Adding a file does not enable it; new bindings must be explicit in code.
The previous detailed log prompt remains in Git history and the private evaluation
metadata; earlier evaluation scores do not establish this shorter prompt's quality.
