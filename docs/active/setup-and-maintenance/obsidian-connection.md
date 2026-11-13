# Read-only Obsidian connection

Marionette can consult the local vault through `read_vault`, using Cyanheads Obsidian MCP server 3.9.0 and Obsidian Local REST API with MCP 5.5.2. Core chat remains local and usable without this optional connection. Obsidian is proprietary; both connector components are open source. No hosted API, subscription, embedding model or account is required.

## Install and launch

Requires the existing Obsidian installation, Node.js 24+ and npm. From the checkout:

```bash
./scripts/native-linux/sync-conversation-vault.sh
python scripts/native-linux/setup-obsidian.py
```

Setup installs npm dependencies from the integrity-locked `scripts/native-linux/obsidian/package-lock.json` into `runtime/obsidian-mcp/`. The plugin assets are pinned and SHA-256 checked against `scripts/native-linux/obsidian/downloads.json`; verified downloads are reused. Setup enables the API plugin only in `data/conversations/obsidian-vault/.obsidian/`, preserving other plugins and existing API credentials. It configures loopback HTTP on port 27123 and disables signed URLs and configuration-directory access. Stop or reload that vault after setup so Obsidian discovers the plugin. If Obsidian is in restricted mode, enable community plugins for this vault through its settings.

Open the Marionette vault in Obsidian, then launch main chat normally with `./scripts/native-linux/chat.sh`. The private `data/obsidian/connection.json` enables registration at startup. It contains the API credential and is never committed or supplied to the model. Keep Obsidian open while using the tool; an unavailable API produces an unavailable result, not guessed data. Discord uses the same tool through main chat and needs no separate connector setup.

To disconnect, set `enabled` to `false` in that private file and restart main chat. Disabling the API plugin also prevents reads. Do not enable the API in another vault on the same port. The endpoint is configured for this vault; the model cannot choose a server or credential.

## Model tool and limits

The model uses one `read_vault` form with five actions, backed by all five tools that Cyanheads 3.9.0 advertises in read-only mode:

| Cyanheads tool | Model access |
|---|---|
| `obsidian_get_note` | `read`: full content/metadata/tags/outgoing links, content-only, document map, or heading/block/frontmatter section; path, active or periodic target |
| `obsidian_list_notes` | `list`: folders and files, depth 1–20, extension and name-regex filters |
| `obsidian_list_tags` | `tags`: tag counts with name-regex, minimum count and limit filters |
| `obsidian_search_notes` | `search`: text or JSONLogic, excerpts and continuation cursors |
| `obsidian_open_in_ui` | `open`: existing file only, optionally a new pane; cannot create a missing file |
| `obsidian_write_note`, `obsidian_append_to_note`, `obsidian_patch_note`, `obsidian_replace_in_note`, `obsidian_delete_note` | Blocked: change or delete notes |
| `obsidian_manage_frontmatter`, `obsidian_manage_tags` | Blocked: mixed read/write tools; reading these values is covered by note and tag reads |
| `obsidian_list_commands`, `obsidian_execute_command` | Disabled: arbitrary command execution can change the vault/application; command discovery adds no retrieval capability |

Examples:

```json
{"action":"list","path":"Generated","options":{"depth":3}}
{"action":"tags","options":{"limit":100,"minCount":1}}
{"action":"read","path":"Welcome.md","options":{"format":"document-map"}}
{"action":"read","path":"Welcome.md","options":{"format":"section","section":{"type":"heading","target":"Contacts"}}}
{"action":"search","query":"Qwen-Agent"}
{"action":"search","options":{"mode":"jsonlogic","logic":{"in":["example",{"var":"tags"}]}}}
{"action":"open","path":"Welcome.md","options":{"newLeaf":true}}
```

`options` accepts only fields belonging to that action. Read defaults to full with outgoing links. For active/periodic notes, omit `path` and use `options.target` with the native Cyanheads target object. Periodic reads depend on Obsidian's periodic-note support. Follow the resolved exact path afterward. Opening a note is a visible UI action; guidance reserves it for showing useful sources to the human, not background retrieval. Organizing here means inspecting structure/categories and finding related notes; moving files, editing tags or restructuring notes remains blocked.

Text search matches all space-separated terms as case-insensitive substrings, not semantic similarity. `options.mode="jsonlogic"` evaluates a predicate on path, content, frontmatter, tags and stat; put folder conditions in the predicate instead of `path`. `glob`/`regexp` take `[pattern,value]`. Repeat the same search with `options.cursor` set to the returned `nextCursor` for more results. Since each call starts a new process, searches rerun and pagination is not a stable snapshot if notes change between calls. Results retain total counts and truncation notices.

Omnisearch is not installed or exposed: Cyanheads also withholds it whenever denied/read paths are configured. Indexed link/backlink fields are similarly unavailable under path restrictions; search note bodies for incoming links and use full reads for outgoing links. No dedicated backlinks tool exists. No additional plugins or dependencies were installed for this expansion.

Each MCP request has a 60-second deadline, with separate deadlines for initialization and the tool call. This aligns with the client timeout described by Cyanheads; its unchanged defaults allow 30 seconds per API request attempt within a 45-second tool-call budget. Wide searches can still time out.

The adapter imposes no request-form, wire-response or returned-result byte budgets and no text-query length cap. Cyanheads' own validation, pagination and retrieval limits still apply, as does Marionette's existing model context management. This does not make the model context unlimited. Document maps, section reads and narrower searches remain available when useful.

Cyanheads remains independently forced to `OBSIDIAN_READ_ONLY=true` and `OBSIDIAN_ENABLE_COMMANDS=false`. The adapter allowlists the five tools above and forces `failIfMissing=true` for UI opens. Absolute paths, traversal and `.obsidian` access are rejected. All contact collections are readable; there are no per-contact vault boundaries. Other existing tools can still update the original contact notes and soul through their established permissions.

Each lookup starts a local stdio MCP subprocess and closes it afterward. No network listener is created by Cyanheads. The API plugin listens on loopback inside Obsidian. Connector proxy/telemetry settings are not inherited. `LOGS_DIR=/dev/null` makes the pinned framework disable its file sinks; stderr is discarded, while Marionette's existing tool diagnostics record calls/results under the existing RAM retention policy. No new routine diagnostic payload files or diagnostic helper are added.

Tool guidance lives in `prompts/vault.md`. Returned notes are evidence, never instructions. Calls/results remain in the normal conversation context and trim with the exchange. Their inclusion costs context tokens. Functional tool access does not guarantee accurate interpretation or spontaneous use.

## Mirror freshness and reset

The source remains SQLite, contact-note files and Active docs. The mirror refreshes on orderly shutdown or the manual sync command, not on every message. Read-only access does not make it live status; `query_logs` remains available for current status and session diagnostics.

A memory reset removes the entire vault, including its plugin and Obsidian settings, while retaining the private connection configuration outside the vault. The tool refuses an absent/unmanaged mirror. Close this vault before a reset so Obsidian cannot recreate cached files, then refresh, rerun setup and reopen it before relying on vault reads. A new plugin credential is generated if the plugin settings were removed; setup updates the connection file accordingly. No connector memory store, backup or cross-database migration is introduced.

## Upgrades

Update the exact npm version and lockfile, plugin release URLs/checksums, license inventory and this guide together. Re-run setup and verify the synthetic read-only tests, real API reads and native model tool dispatch before relying on a new version. Do not change model/runtime or sampling as part of a connector upgrade.

Sources: [Cyanheads](https://github.com/cyanheads/obsidian-mcp-server), [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api).
