# Read-only Obsidian connection verification — November 13, 2026

> Historical: the Cyanheads integration was removed on 2026-11-13. Model vault access is disconnected; the custom plugin is not implemented.

Configuration: Cyanheads obsidian-mcp-server 3.9.0 with the locked Node dependency tree, Local REST API with MCP 5.5.2, Qwen-Agent 0.0.34, and the existing Qwen3.5-4B Q4_K_M / llama.cpp b12211 Vulkan configuration. The model, precision, 65,536 context, 5,120 MiB cache, thinking mode and sampling settings were unchanged.

- Real Cyanheads against a synthetic loopback API: read succeeded; write, delete and command tools were absent from discovery. Direct calls to these disabled tools were rejected without HTTP mutation requests reaching the fixture.
- Adapter checks reject invalid actions, path traversal, absolute/configuration paths and extra fields before starting the connector. Disabled configuration and a reset/missing mirror fail closed.
- Real Qwen-Agent over mocked inference: tool arguments reached the adapter, results returned to a second model request and remained in history. A separate regression preserves the vault tool across contact-note rebinding.
- Real 4B GPU test with temporary configuration, synthetic vault response and no saved profiles: asked the model to read Welcome.md for a test code. It made one successful vault call through Qwen-Agent and Cyanheads, returned the exact fixture code, and finished with `stop`. The model server was shut down cleanly. No synthetic conversations or facts were written to real personal data.
- Live Obsidian vault: read Welcome.md, list root and search for Qwen-Agent succeeded through the actual plugin. Private conversation content was not used for the model test.
- Regression run: 176 core and 16 mocked Discord checks passed. After adding the contact-rebinding case, all five targeted vault-tool checks passed. The first regression run exposed a missing source file in the synthetic launcher checkout; its fixture inventory was corrected before the successful run.
- Re-ran the locked npm/plugin installer and reloaded the plugin, then repeated actual list/read/search checks. Plugin artifacts match the pinned SHA-256 values. Installed dependency license files, including the README license for glob-to-regexp, were inspected.

This establishes installation, basic model tool dispatch, local reads and rejected mutations. It does not establish broad retrieval quality, spontaneous recall, long-session reliability or performance. Search is text-based, the adapter has no cursor continuation yet, and a note exceeding the result cap is unavailable. No semantic index, new memory backend or cross-database migration was introduced. See the [current connection guide](../../active/setup-and-maintenance/obsidian-connection.md) for operation and limits.

## Expanded retrieval and navigation — later November 13 pass

Reviewed all 14 tools in the installed 3.9.0 source/README. Marionette now exposes all five tools advertised by its read-only server: note projections, recursive listings, tags, text/JSONLogic searches with cursors, and existing-file UI opening. No dependency or model settings changed. The earlier no-cursor limitation above describes the initial installation, not this expansion.

Verification: 178 core checks passed; all six targeted vault checks also passed after adding the missing-note case. The real pinned Cyanheads process successfully handled synthetic document-map and heading-section reads, recursive listing, tag counts, text/JSONLogic search, and UI-open requests. A 51-hit search continued correctly in a fresh connector process without overlapping page hits. Opening a missing note failed without an open/create request reaching the fixture. Tool discovery exactly matched the five-tool allowlist; disabled writes/deletes/commands remained rejected before HTTP mutations. The normal Qwen-Agent dispatch/history and contact-rebinding checks passed. The documentation mirror was refreshed.

This pass used a synthetic API, not the real Obsidian UI, and did not run a new GPU/model answer-quality test. The earlier basic 4B test does not establish how reliably she chooses the new advanced options. Omnisearch and indexed link fields remain unavailable under the configured path restrictions; body searches and outgoing link reads remain supported. Cursor pages rerun searches across processes and can shift when the vault changes.
