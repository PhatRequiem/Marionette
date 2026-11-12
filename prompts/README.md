# Application prompts

Versioned instructions for application features. Keep one focused prompt per feature.
These are separate from the editable soul and contain behavior rules, not private
conversation data or hard-coded runtime facts.

`log-queries.md` is loaded by `API.with_system()` only when `query_logs` is registered.
It is placed before the soul in the system message and participates in exact token
counting, generation and cache preparation. Each API instance loads it once;
restart chat after editing. Missing files fail visibly rather than silently
removing the instruction. Adding a file here does not automatically enable it:
new prompts require an explicit code binding.
