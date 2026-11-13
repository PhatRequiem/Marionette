# Application prompts

Concise behavior guidance, separate from the editable soul and native tool schemas.

| File | Loaded when |
|---|---|
| `tool-guidance.md` | Any supported tool is registered |
| `log-queries.md` | `query_logs` is registered (enabled in production) |
| `log-results.md` | Follow-up model requests after `query_logs` returns in the current turn |
| `contact-notes.md` | `update_contact_notes` is registered |
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
Log-query guidance uses explicit field names and JSON argument examples. See
[current reliability limits](../docs/active/current-operation/log-queries.md#current-reliability-limits)
for interpretation limits and [archived evaluations](../docs/development/experiments/active-guide-reports-2026-11-12/log-queries.md)
for earlier checks; those reports do not measure every later prompt revision.

The log-result reminder is appended to a copy of the initial system message for
follow-up requests only, before exact token counting. It is not tool data and is
not retained as conversation history or applied to the next ordinary turn.

Contact-note guidance allows optional inline citations using the exact stable
`conversation_reference` supplied in Sender metadata. The vault exporter resolves
these internal destinations on sync; the model does not construct filenames or
gain file access. See [contact-note citations](../docs/active/current-operation/contact-notes.md#optional-conversation-links).

These files are application inputs, not part of the `docs/active/` mirror. Current tool behavior is documented in [Qwen-Agent coordination](../docs/active/current-operation/qwen-agent.md); test reports and retired guidance belong in [Development](../docs/development/README.md) or Git history. Only Active documentation is mirrored into Obsidian.
