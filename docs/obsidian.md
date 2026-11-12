# Read-only Obsidian docs vault

Marionette's `docs/` folder is the vault: files are not copied or synchronized elsewhere. The retained Qwen-Agent `read_docs` adapter uses Local REST API 5.5.2. **Currently disconnected:** normal startup and contact turns register neither `read_docs` nor `query_logs`. Vault settings, plugin installation, adapter, prompt and tests remain intact; enabling the Obsidian plugin alone does not reconnect the model. The log tool, CLI, prompt and tests remain in the checkout for operators; no model log access is registered.

## Setup and operation

Install Obsidian desktop (plugin requires 1.13.1 or newer), then run:

```bash
python scripts/native-linux/setup-obsidian.py
```

The script verifies pinned plugin hashes or downloads missing files into `docs/.obsidian/plugins/obsidian-local-rest-api/`. It preserves existing plugin settings and refuses mismatched plugin binaries. Open the existing `docs/` folder as an Obsidian vault and enable the community plugin **Local REST API with MCP**. Keep that vault open. Start Marionette and Discord using the usual commands in STARTUP.md. Restart main chat after application or prompt changes.

The dedicated endpoint is `http://127.0.0.1:27133`, bound only to loopback, authenticated with a generated API key. HTTPS is disabled for this local adapter; no key is sent over the network. Settings and credentials stay in ignored `.obsidian/` files, mode 600 for plugin settings at installation. The model never receives credentials. No Sync, Publish, account or subscription is needed. Obsidian itself is proprietary; the plugin is MIT. This optional integration does not make Obsidian necessary for core chat or memory storage.

## Model operations and boundaries

- `list`: discover Markdown notes and folders (100 entries per directory result; reports truncation).
- `search`: use Obsidian full-text search, returning at most 20 note paths and three bounded snippets per note. This is not exhaustive absence evidence.
- `read`: read a returned Markdown path, up to 200 lines and 16,000 characters, with `next_line` for continuation.

Only these operations are exposed. The adapter constructs fixed local routes, disables redirects/proxies, bounds responses and timeouts, and rejects hidden paths, symlinks, traversal, arbitrary URLs and non-Markdown files. It does not expose plugin write routes, command execution, active-file operations, or automatic MCP tool discovery. The upstream plugin API key itself has broader capabilities; read-only enforcement is in Marionette's wrapper, not an upstream read-only credential. Other local code with access to the key is outside that model-tool boundary.

The wrapper also verifies returned search/list paths against this checkout's docs directory. No raw logs, conversation databases, credentials or private profiles are in scope. Tool results remain in normal conversation context and diagnostic RAM under the existing retention policy. The model cannot edit vault files; the operator and startup-datasheet updater still can.

Current guides, historical experiments, archived baselines and discussion-only ideas all exist in this vault. Tool guidance distinguishes them and asks for note-path citations. The dated setup sheet is startup evidence, not a live connection/status probe. Documentation retrieval does not prove answer accuracy.

## Verification

Synthetic tests cover path traversal, hidden settings, symlinks, rejected write actions/extra fields, pagination, filtered search/list results, credential-safe errors, and production registration without query_logs. Setup/launcher tests continue using synthetic stores; the retained log adapter tests explicitly opt into their isolated binding. All 163 core and 14 mocked Discord checks passed. Before disconnection, the live application registry was verified with `read_docs` and without `query_logs`. The docs vault opened in Obsidian, but its API was not reachable: community-plugin activation is pending. Live vault reads and model retrieval quality are therefore not yet verified.
