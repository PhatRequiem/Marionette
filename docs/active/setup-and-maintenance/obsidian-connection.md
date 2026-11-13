# Scarecrow: read-only Obsidian connection

Scarecrow 0.1.1 is Marionette's local Obsidian desktop plugin. It runs an HTTP listener inside Obsidian on `127.0.0.1:27124`, serving only the open vault. There is no separate server process, cloud service, MCP middleware, embedding model or new database. Cyanheads and Local REST API are no longer used. Core chat works without Obsidian.

## Install and start

Use the existing Obsidian desktop installation (host application version: 1.15.1, installer 1.14.4). The manifest declares minimum 1.8.0 for the public APIs used; older-version compatibility is not separately tested.

```bash
./scripts/native-linux/sync-conversation-vault.sh
python scripts/native-linux/setup-scarecrow.py
```

Open `data/conversations/obsidian-vault/` in Obsidian. Allow community plugins for this vault if necessary. Setup enables Scarecrow while preserving other plugin entries; reload the vault if it was already open. The Scarecrow settings pane shows connection status. Start Marionette normally with `./scripts/native-linux/chat.sh`; configured access registers `read_vault`. Discord uses main chat's tool. No model/runtime or sampling changes are required.

Source is plain CommonJS JavaScript under `plugins/scarecrow/`. Setup assembles `main.js`, `operations.js` and `server.js` into one installed `main.js` using a small deterministic Python wrapper, because Obsidian does not resolve sibling CommonJS imports. It also copies `manifest.json` and LICENSE. No compiler, npm installation or downloads are required. Run setup again after updating plugin source, then reload Obsidian and restart chat. The manifest version and HTTP status version must stay aligned.

The private `data/scarecrow/connection.json` and the plugin's `data.json` contain the matching token, vault ID and port; setup writes them with mode 600 and preserves them on reinstall. Neither is committed or supplied to the model. `--vault`, `--data` and `--port` support explicit alternate locations; align `--data` with `MARIONETTE_DATA_DIR` when launching. An explicit `--vault` wins; otherwise the vault is `obsidian-vault/` under `MARIONETTE_LOG_DIR`, or under the selected data directory’s `conversations/` folder when no log override is set. `--data` overrides `MARIONETTE_DATA_DIR` for setup. Use the same environment for mirror refresh and plugin setup. Default port is 27124. Port collisions produce an offline notice rather than falling back to another interface. To disconnect model access, set `enabled` false in the connection file and restart chat. Disable Scarecrow in Obsidian to stop the listener.

## Request form

The model calls one explicit Qwen-Agent tool, `read_vault`. Native tool schemas remain in the API `tools` field; concise guidance is in `prompts/vault.md`, separate from the editable soul. Credentials, server address and vault identity are application-owned.

| Action | Fields | Result |
|---|---|---|
| `list` | Optional `path` folder; omit for root | Immediate child files and folders |
| `search` | `query`, `folder` and/or `tag` | Matching Markdown paths, tags and matching lines |
| `read` | Exact `path`; optional `section` heading | Whole note or heading and its subsections |
| `inspect` | Exact `path` | Heading names/lines, tags, frontmatter properties |
| `tags` | None | Tags and number of notes using each |
| `links` | Exact `path` | Outgoing links/embeds, unresolved references, backlinks |
| `open` | Exact `path` | Opens an existing Markdown note for the human |

```json
{"action":"search","query":"Qwen"}
{"action":"read","path":"Welcome.md"}
{"action":"links","path":"Welcome.md"}
```

Search returns **ranked partial matches**: any query token may occur in the note path or content. Both are Unicode NFKC-normalized and lowercased, then split into letter/number/underscore tokens; punctuation separates tokens. Thus `server` does not match `observer`, and `llama.cpp` becomes `llama` and `cpp`. Duplicate query tokens count once. An explicit empty or punctuation-only query is rejected; omit query for folder/tag-only browsing.

Folder filtering includes descendants; tag filtering matches one exact tag (with or without `#`). Within that filtered collection, each distinct matching term contributes `1 + ln((1 + note count)/(1 + notes containing term))`. Less-common terms therefore carry more weight. Each distinct unordered pair occurring within 12 token positions on the same line adds half the smaller term weight. Each adjacent ordered pair from the deduplicated query occurring adjacently on that line adds the smaller term weight again. Paths are scored as a separate line. Each term/pair contributes at most once per note, so repeating words does not inflate scores. Scores descend, with path order breaking ties; filter-only results retain path order.

Results expose `score`, `matched_terms`, `missing_terms`, `nearby_pairs`, `matched_phrases`, and original `matching_lines` with one-based line numbers. Scores are relative lexical evidence, not probabilities or factual confidence. Ranking is at note level; nearby-term bonuses are line-local, not conversation-exchange-aware. This is not noun extraction, synonym matching, stemming, semantic inference, or Obsidian search-language parsing. Generic terms get less weight only when common in the filtered collection. There is no stored topic index or new dependency. A heading section requires an exact, unique heading; duplicates return an explicit ambiguity error. Use inspect or a full read to resolve it.

Results carry exact vault-relative paths and note modification timestamps where applicable. No application-level query/result byte budgets or pagination are imposed. Large results consume model context and memory; existing conversation context limits still apply. Search scans visible Markdown notes on demand, so performance at large vault sizes is not established. There is a 60-second HTTP inactivity timeout in the Python client and listener, plus Node's 60-second request/header reception timeouts; these are not a guaranteed total execution deadline for a long scan. Transport-level Node defaults still apply.

## Boundaries and lifecycle

The listener requires a private bearer token, checks the loopback Host header and rejects browser Origin requests. It offers `GET /v1/status`, `POST /v1/query` and the authenticated diagnostic stream `GET /v1/events`; there are no write, delete or command routes. The Python adapter fixes the hostname to 127.0.0.1, does not use proxies or follow redirects, and verifies the response vault ID. Unknown actions and action-inappropriate fields fail.

Operations use the public Vault, MetadataCache and Workspace APIs. Only visible vault paths are accepted; hidden directories (including `.obsidian`), traversal, absolute paths and symlinked note paths are excluded, including from search and link results. All contact collections remain readable. Open operates only on an existing Markdown file; it cannot create a missing note. It changes the human's visible workspace, not note content.

Plugin load starts the listener; unload closes it and active connections and unregisters metadata listeners. Requests wait for workspace readiness; unavailable note metadata is reported explicitly. Metadata and links can briefly lag edits. There is no new persistent index, payload log, background logging helper or memory store. Normal Marionette tool diagnostics continue through the existing RAM recorder.

## Mirror and reset

The source remains SQLite conversations, contact notes and Active docs. The existing mirror refreshes on orderly shutdown or manually, not every message. Scarecrow reads that mirror; `query_logs` remains the source for live status. Tool calls/results stay in conversation context and trim with the exchange.

Memory reset clears the whole vault, including Scarecrow's installed plugin/settings. Close the vault before a reset so Obsidian cannot recreate cached files. The adapter and listener refuse a missing managed-mirror marker. After reset, refresh the mirror, rerun setup and reopen Obsidian; setup issues new credentials when plugin settings are absent and updates the retained application connection file. Source code and the setup script survive reset. No synthetic test data is written to real profiles.

## Verification and references

```bash
node --test tests/scarecrow/scarecrow.test.js
runtime/agent/bin/python -m unittest discover -s tests/core
runtime/discord/bin/python -m unittest discover -s tests/discord
```

Version 0.1.1 verification: all 7 Scarecrow tests and 200 core tests passed. Synthetic search cases cover partial matches, rarity weighting, ordered phrases, the 12-token proximity boundary, repetition resistance, Unicode/punctuation, filters and empty queries. The setup script rebuilt and installed the bundle successfully. These checks do not establish real-conversation retrieval quality or large-vault performance. Reload Obsidian to activate the installed bundle and restart Marionette to load the updated search guidance.

Node is needed to run plugin tests, not as a separate production server. Tests use temporary synthetic vaults; public Obsidian API fixtures do not establish real app compatibility or model answer quality. See [the Scarecrow verification report](../../development/experiments/scarecrow-2026-11-13.md) for what has actually been exercised.

Official design references: [Vault API](https://docs.obsidian.md/Plugins/Vault), [public API definitions](https://github.com/obsidianmd/obsidian-api/blob/master/obsidian.d.ts), [plugin lifecycle](https://docs.obsidian.md/plugins/guides/lifecycle-management), [manifest](https://docs.obsidian.md/Reference/Manifest). The HTTP protocol and tool interface are Marionette design choices.

Reset refuses configured alternate Scarecrow vault locations before changing personal data, even when the connector is disabled. An operator must review and clear those memory copies separately; reset never deletes arbitrary configured folders.

## Connections and Requests logs

While configured access is enabled, a reader thread inside main chat subscribes to Scarecrow's authenticated `/v1/events` stream. Plugin/listener observations, Obsidian readiness, request receipt/completion/failure, HTTP status and elapsed milliseconds appear in **Connections and Requests**, labeled `Scarecrow` or `Obsidian`. The Python tool also records request start/end with the same UUID passed in `X-Request-ID`; its existing message/request/tool scope connects that UUID to the model call. Reasoning retains its brief tool summaries.

The stream reports the listener and vault state observed at connection, then live events. It does not replay startup events from before Marionette connected. Unload emits `plugin_stopping` best-effort; a crash or broken connection appears as `unavailable`, not a verified graceful shutdown. Main chat retries every two seconds and records state changes rather than every failed retry. Fifteen-second blank keepalives are not logged. `ready` describes workspace/index readiness; request results still determine whether a particular vault operation succeeded. Missing mirror markers are reported on stream connection and rejected by query operations. A listener that cannot bind cannot stream its own failure; its local Obsidian notice remains available and Marionette observes the connection as unavailable.

Only metadata is forwarded: no bearer tokens, query text, note paths, note contents or response bodies. The stream has no replay queue or disk log; events during disconnection are not recoverable. Slow subscribers are disconnected rather than accumulating a backlog. The reader stops before main chat's recorder shuts down. Events share the existing 500 MB RAM budget and shutdown save; no helper process or additional storage system is introduced. This captures Scarecrow integration events, not Obsidian's entire developer console.

After a code update, rerun setup and reload the vault to load the new plugin bundle; restart Marionette to start the diagnostic subscriber.
