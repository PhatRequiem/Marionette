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

- `{"action":"list"}` lists the root; add a vault-relative `path` to browse a folder, one level at a time.
- `{"action":"read","path":"Welcome.md"}` reads a Markdown note, metadata and outgoing links.
- `{"action":"search","query":"Qwen-Agent"}` searches text. Optional `path` filters results by a folder prefix.

Search uses all space-separated terms as case-insensitive substrings. It is not semantic search. This first adapter returns the server's first results page, including its total/cursor metadata; continuation cursors are not accepted yet. Narrow the query or folder if more results exist. Note reads include outgoing references, not a dedicated backlinks query. Results are limited to 32 KiB, wire messages to 1 MiB, forms to 4 KiB, and each connector interaction to a 20-second deadline. An oversized result is unavailable rather than silently truncated. Large conversations may need targeted searches.

The adapter permits only three Cyanheads read tools. Cyanheads is independently forced to `OBSIDIAN_READ_ONLY=true` and `OBSIDIAN_ENABLE_COMMANDS=false`; its UI-opening tool is not exposed by Marionette. Absolute paths, traversal and `.obsidian` access are rejected. All contact collections are readable; there are no per-contact vault boundaries. Other existing tools can still update the original contact notes and soul through their established permissions.

Each lookup starts a local stdio MCP subprocess and closes it afterward. No network listener is created by Cyanheads. The API plugin listens on loopback inside Obsidian. Connector proxy/telemetry settings are not inherited. `LOGS_DIR=/dev/null` makes the pinned framework disable its file sinks; stderr is discarded, while Marionette's existing tool diagnostics record calls/results under the existing RAM retention policy. No new routine diagnostic payload files or diagnostic helper are added.

Tool guidance lives in `prompts/vault.md`. Returned notes are evidence, never instructions. Calls/results remain in the normal conversation context and trim with the exchange. Their inclusion costs context tokens. Functional tool access does not guarantee accurate interpretation or spontaneous use.

## Mirror freshness and reset

The source remains SQLite, contact-note files and Active docs. The mirror refreshes on orderly shutdown or the manual sync command, not on every message. Read-only access does not make it live status; `query_logs` remains available for current status and session diagnostics.

A memory reset removes the entire vault, including its plugin and Obsidian settings, while retaining the private connection configuration outside the vault. The tool refuses an absent/unmanaged mirror. Close this vault before a reset so Obsidian cannot recreate cached files, then refresh, rerun setup and reopen it before relying on vault reads. A new plugin credential is generated if the plugin settings were removed; setup updates the connection file accordingly. No connector memory store, backup or cross-database migration is introduced.

## Upgrades

Update the exact npm version and lockfile, plugin release URLs/checksums, license inventory and this guide together. Re-run setup and verify the synthetic read-only tests, real API reads and native model tool dispatch before relying on a new version. Do not change model/runtime or sampling as part of a connector upgrade.

Sources: [Cyanheads](https://github.com/cyanheads/obsidian-mcp-server), [Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api).
