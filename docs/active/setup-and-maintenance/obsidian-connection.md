# Scarecrow: read-only Obsidian connection

Scarecrow 0.3.0 is Marionette's local Obsidian desktop plugin. It runs an HTTP listener inside Obsidian on `127.0.0.1:27124`, serving only the open vault. There is no separate server process, cloud service, MCP middleware, embedding model or new database. Cyanheads and Local REST API are no longer used. Core chat works without Obsidian.

## Install and start

Use the existing Obsidian desktop installation (host application version: 1.15.1, installer 1.14.4). The manifest declares minimum 1.8.0 for the public APIs used; older-version compatibility is not separately tested.

```bash
./scripts/native-linux/sync-conversation-vault.sh
python scripts/native-linux/setup-scarecrow.py
```

Open `data/conversations/obsidian-vault/` in Obsidian. Allow community plugins for this vault if necessary. Setup enables Scarecrow while preserving other plugin entries; reload the vault if it was already open. The Scarecrow settings pane shows connection status. Start Marionette normally with `./scripts/native-linux/chat.sh`; configured access registers `read_vault`. Discord uses main chat's tool. No model/runtime or sampling changes are required.

Source is plain CommonJS JavaScript under `plugins/scarecrow/`. Setup assembles `main.js`, `operations.js`, `search.js`, `passages.js` and `server.js` into one installed `main.js` using a small deterministic Python wrapper, because Obsidian does not resolve sibling CommonJS imports. It also copies `manifest.json` and LICENSE. No compiler, npm installation or downloads are required. Run setup again after updating plugin source, then reload Obsidian and restart chat. The manifest version and HTTP status version must stay aligned.

The private `data/scarecrow/connection.json` and the plugin's `data.json` contain the matching token, vault ID and port; setup writes them with mode 600 and preserves them on reinstall. Neither is committed or supplied to the model. `--vault`, `--data` and `--port` support explicit alternate locations; align `--data` with `MARIONETTE_DATA_DIR` when launching. An explicit `--vault` wins; otherwise the vault is `obsidian-vault/` under `MARIONETTE_LOG_DIR`, or under the selected data directory’s `conversations/` folder when no log override is set. `--data` overrides `MARIONETTE_DATA_DIR` for setup. Use the same environment for mirror refresh and plugin setup. Default port is 27124. Port collisions produce an offline notice rather than falling back to another interface. To disconnect model access, set `enabled` false in the connection file. Main chat applies connection-file changes at the next idle/turn boundary, rebinds `read_vault`, restarts its existing diagnostic subscriber, and refreshes the setup datasheet. A busy turn finishes first. Python code updates still require restarting chat. Disable Scarecrow in Obsidian to stop the listener.

## Request form

The model calls one explicit Qwen-Agent tool, `read_vault`. Native tool schemas remain in the API `tools` field; concise guidance is in `prompts/vault.md`, separate from the editable soul. Credentials, server address and vault identity are application-owned.

| Action | Fields | Result |
|---|---|---|
| `list` | Optional `path` folder; omit for root | Immediate child files and folders |
| `search` | `query`, optional `mode`, `folder`, `tag`, `limit` and `offset` | Compact ranked previews, source references and pagination |
| `read` | Exact `path`; optional `section`, or returned `passage_id` with optional `context` | Whole note, heading section, or passage with optional neighbors |
| `inspect` | Exact `path` | Heading names/lines, tags, frontmatter properties |
| `tags` | None | Tags and number of notes using each |
| `links` | Exact `path` | Outgoing links/embeds, unresolved references, backlinks |
| `open` | Exact `path` | Opens an existing Markdown note for the human |

```json
{"action":"search","query":"Qwen"}
{"action":"read","path":"Welcome.md"}
{"action":"links","path":"Welcome.md"}
```

### Independent search engine

`plugins/scarecrow/search.js` is our independent implementation of standard lexical search techniques. MiniSearch's [public capabilities](https://lucaong.github.io/minisearch/) informed the feature review; no MiniSearch source was copied or added as a dependency. The implementation uses an inverted index (tokens mapped to passage identifiers), field-weighted BM25, and our existing exact-term proximity/phrase bonuses. This is a Scarecrow engine, not a drop-in MiniSearch API replacement.

Search returns partial matches. Text is Unicode NFKC-normalized and lowercased, then split into letter/number/underscore tokens. Punctuation separates tokens (`llama.cpp` becomes `llama` and `cpp`); duplicate query tokens count once. An explicit empty or punctuation-only query is rejected; omit query for folder/tag-only browsing. Folder filtering includes descendants; tag filtering matches one exact tag, with or without `#`. These filters apply before indexing and scoring.

| Mode | Matching behavior |
|---|---|
| `exact` (default) | Whole tokens; `server` does not match `observer` or `servers`. |
| `prefix` | Exact matches plus tokens beginning with a query token of at least 3 characters, weighted at 0.7 of their score. |
| `fuzzy` | Exact matches plus a single insertion, deletion, substitution or adjacent transposition for query tokens of at least 4 characters, weighted at 0.5. It does not also enable prefixes. |

```json
{"action":"search","query":"inference server"}
{"action":"search","query":"infer serv","mode":"prefix"}
{"action":"search","query":"sevrer","mode":"fuzzy"}
```

BM25 uses `k1=1.2`, `b=0.75`, and positive inverse-document-frequency `ln(1 + (N-df+0.5)/(df+0.5))`. Each field contributes `weight * IDF * tf*(k1+1)/(tf + k1*(1-b+b*length/average_length))`. For passage searches, fields are passage body (weight 1), full path (0.1), filename without `.md` (0.2), and the passage heading (0.5). Filename and heading weights are deliberately lower than in 0.2.0 so shared note labels do not dominate passage content. Field averages and document frequencies use all passages in the filtered collection, including passages without hits. Heading/filename weighting is additive to their occurrence in the body/path. Frequency increases scores with saturation; unlike 0.1.1, repeated terms can increase the score, but not linearly. Length normalization reduces the advantage of long notes. These are initial engineering settings, not empirically tuned quality claims. See [BM25 explanation](https://www.elastic.co/blog/practical-bm25-part-2-the-bm25-algorithm-and-its-variables).

For each query token, only its best-scoring exact or expanded token contributes to the BM25 sum, avoiding a bonus just for containing many completions. Each distinct pair of **exact query tokens** within 12 token positions on one line adds half the smaller IDF. Adjacent ordered pairs from the deduplicated query add the smaller IDF again. Pair bonuses count once per passage and do not cross lines. Shared note paths do not receive passage phrase/proximity bonuses. Expansions never invent phrase/proximity evidence. Scores descend; path order breaks ties. Filter-only results retain path order with zero scores.

Results expose `score`, `matched_terms`, `missing_terms`, `term_matches` (query token, source token and exact/prefix/fuzzy kind), `nearby_pairs`, `matched_phrases`, and original `matching_lines` with one-based line numbers. Matched query terms can include expansions; inspect `term_matches` to distinguish them. Only the best variant per query token contributes to BM25. Compact previews report up to 12 matching variants and indicate omitted variants; group matching lines are shortened as described below. Scores are relative lexical relevance, not probabilities or factual confidence. A passage can rank highly with only part of the query. Read the original evidence before answering.

The engine has add/replace/remove operations, but production constructs a fresh **request-local RAM index** from passages of eligible notes for each search. No cached index survives a request and none is written to disk. This preserves current mirror/reset behavior and avoids stale cached entries after edits, renames or deletion. It still reads and tokenizes the eligible collection on each request; prefix/fuzzy modes additionally scan its vocabulary. Index memory grows with the collection, and concurrent requests may build separate indexes. A long-lived incremental index would require separate lifecycle and reset coordination work. No diagnostic retention policy changes or background processes are introduced.

Ranking is at passage level; each note group uses its best passage score, never a sum across unrelated passages. There is no noun extraction, synonym reasoning, semantic topic discovery, stemming, query-language parsing, autocomplete interface or persisted index. Search boundaries and headings are parsed from the scored text itself; inspect/read-section still use Obsidian metadata, which may briefly lag edits. A heading section for `read` requires an exact, unique heading; duplicates return an ambiguity error. Use inspect or a full read to resolve it.

### Passage boundaries and reading context

Query searches return note groups in `matches`. Each group carries its best passage score and compact matching evidence, and up to two `passages` previews sorted by relevance. `total` counts notes and `total_passages` counts matching passages. Each preview includes up to 240 characters of matching text (or a fallback snippet), `passage_id`, source `start_line`/`end_line` (one-based, inclusive), heading, and available `messages` containing record IDs, correlation IDs, roles, kinds and source `recorded_at` timestamps when present. Note headings are limited to 100 characters; group matching lines to two lines of 160 characters; expanded term evidence to 12 variants with an explicit truncation flag. Full excerpts and duplicate top-level passage payloads are omitted. `passages_total` counts all matching passages for that note. Matching-line numbers refer to the original note. Folder/tag-only browsing continues to return one entry per note without passage extraction.

For generated `Generated/Contacts/.../Conversations/` pages with conversation frontmatter, the parser recognizes message headings and the exporter's quoted JSON metadata. It pairs an input with its immediately following assistant answer only when both have the same nonempty correlation ID. Missing/mismatched metadata leaves messages separate; it never pairs by speaker name or inferred meaning. Generated navigation/frontmatter before the first message is not a conversation passage. Full-note reads still expose it. Message bodies remain literal; fenced headings cannot create new exchanges. Long exchanges stay intact to preserve question/answer context.

Other notes split into non-overlapping ATX (`#` through `######`) heading sections, including any preamble. Long sections split at blank-line paragraph boundaries after a soft 600-token target. Fenced code blocks stay intact. An indivisible paragraph, code block or conversation exchange can exceed the target; this is not a response-size cap. Setext/HTML headings are not recognized as section boundaries. No automatic overlap duplicates passages; request context when needed.

Use a returned path and passage ID to read the exact source range:

```json
{"action":"read","path":"<returned path>","passage_id":"<returned passage_id>"}
{"action":"read","path":"<returned path>","passage_id":"<returned passage_id>","context":"neighbors"}
```

`context` defaults to `none`. `neighbors` returns the complete selected exchange/section plus its preceding and following logical units within the same note, including all paragraph chunks of those sections. Context can therefore be substantially larger than the original hit. `section` and `passage_id` are mutually exclusive. IDs combine a content fingerprint and source range: any note text edit invalidates them, returning HTTP 409 with instructions to search again. A rename requires the new returned path. They are temporary retrieval references, not permanent memory identities. Original SQLite records, exporter format, vault files and reset behavior are unchanged.

Results carry exact vault-relative paths and note modification timestamps where applicable. Search queries are limited to 256 characters. Search returns at most five notes by default (`limit`: integer 1–10), and its data payload is capped below 12 KiB. `offset` and `next_offset` paginate note groups; `total` and `total_passages` count all matches, and `truncated` indicates more notes. Use the same query/filters when paging; edits between requests can change ranking. Narrow the query/folder for other passages within a note. Oversized single-note metadata returns an explicit budget error rather than damaged references. These are preview limits, not ranking/index or full-read limits. Full-note, focused and neighboring reads can still be large; start with a single passage. Search scans visible Markdown notes on demand, so performance at large vault sizes is not established. There is a 60-second HTTP inactivity timeout in the Python client and listener, plus Node's 60-second request/header reception timeouts; these are not a guaranteed total execution deadline for a long scan. Transport-level Node defaults still apply.

## Boundaries and lifecycle

The listener requires a private bearer token, checks the loopback Host header and rejects browser Origin requests. It offers `GET /v1/status`, `POST /v1/query` and the authenticated diagnostic stream `GET /v1/events`; there are no write, delete or command routes. The Python adapter fixes the hostname to 127.0.0.1, does not use proxies or follow redirects, and verifies the response vault ID. Unknown actions and action-inappropriate fields fail.

Operations use the public Vault, MetadataCache and Workspace APIs. Only visible vault paths are accepted; hidden directories (including `.obsidian`), traversal, absolute paths and symlinked note paths are excluded, including from search and link results. All contact collections remain readable. Open operates only on an existing Markdown file; it cannot create a missing note. It changes the human's visible workspace, not note content.

Plugin load starts the listener; unload closes it and active connections and unregisters metadata listeners. Requests wait for workspace readiness; unavailable note metadata is reported explicitly. Metadata and links can briefly lag edits. There is no new persistent index, payload log, background logging helper or memory store. Normal Marionette tool diagnostics continue through the existing RAM recorder.

## Mirror and reset

The source remains SQLite conversations, contact notes and Active docs. The existing mirror refreshes on orderly shutdown or manually, not every message. Scarecrow reads that mirror; `query_logs` remains the source for live status. Tool calls/results stay in conversation context and trim with the exchange.

Memory reset clears the whole vault, including Scarecrow's installed plugin/settings. Close the vault before a reset so Obsidian cannot recreate cached files. The adapter and listener refuse a missing managed-mirror marker. After reset, refresh the mirror, rerun setup and reopen Obsidian; setup issues new credentials when plugin settings are absent and updates the retained application connection file. Source code and the setup script survive reset. No synthetic test data is written to real profiles.

## Verification and references

```bash
node --test tests/scarecrow/*.test.js
runtime/agent/bin/python -m unittest discover -s tests/core
runtime/discord/bin/python -m unittest discover -s tests/discord
```

Version 0.4.0 introduces compact search previews and pagination, source dates on parsed message metadata, and focused-read/date guidance. Regression tests cover byte limits, paging, full passage reads, stale references and the bundled loader. Earlier 0.3.0 verification had 17 search/plugin tests and 200 core tests. Checks include synthetic exporter-shaped exchange pairing, literal fenced headings, source line ranges and message identifiers, section chunking, focused-versus-scattered ranking, multiple hits per note, neighboring context, and stale-reference rejection. Existing scoring, authorization, symlink, reset, diagnostics and installer checks remain applicable. These tests do not establish real-conversation answer quality or large-vault performance. Reload Obsidian and restart Marionette after installing to activate the bundle and tool schema.

Node is needed to run plugin tests, not as a separate production server. Tests use temporary synthetic vaults; public Obsidian API fixtures do not establish real app compatibility or model answer quality. See [the Scarecrow verification report](../../development/experiments/scarecrow-2026-11-13.md) for what has actually been exercised.

Official design references: [Vault API](https://docs.obsidian.md/Plugins/Vault), [public API definitions](https://github.com/obsidianmd/obsidian-api/blob/master/obsidian.d.ts), [plugin lifecycle](https://docs.obsidian.md/plugins/guides/lifecycle-management), [manifest](https://docs.obsidian.md/Reference/Manifest). The HTTP protocol and tool interface are Marionette design choices.

Reset refuses configured alternate Scarecrow vault locations before changing personal data, even when the connector is disabled. An operator must review and clear those memory copies separately; reset never deletes arbitrary configured folders.

## Connections and Requests logs

While configured access is enabled, a reader thread inside main chat subscribes to Scarecrow's authenticated `/v1/events` stream. Plugin/listener observations, Obsidian readiness, request receipt/completion/failure, HTTP status and elapsed milliseconds appear in **Connections and Requests**, labeled `Scarecrow` or `Obsidian`. The Python tool also records request start/end with the same UUID passed in `X-Request-ID`; its existing message/request/tool scope connects that UUID to the model call. Reasoning retains its brief tool summaries.

The stream reports the listener and vault state observed at connection, then live events. It does not replay startup events from before Marionette connected. Unload emits `plugin_stopping` best-effort; a crash or broken connection appears as `unavailable`, not a verified graceful shutdown. Main chat retries every two seconds and records state changes rather than every failed retry. Fifteen-second blank keepalives are not logged. `ready` describes workspace/index readiness; request results still determine whether a particular vault operation succeeded. Missing mirror markers are reported on stream connection and rejected by query operations. A listener that cannot bind cannot stream its own failure; its local Obsidian notice remains available and Marionette observes the connection as unavailable.

Only metadata is forwarded: no bearer tokens, query text, note paths, note contents or response bodies. The stream has no replay queue or disk log; events during disconnection are not recoverable. Slow subscribers are disconnected rather than accumulating a backlog. The reader stops before main chat's recorder shuts down. Events share the existing 500 MB RAM budget and shutdown save; no helper process or additional storage system is introduced. This captures Scarecrow integration events, not Obsidian's entire developer console.

After a code update, rerun setup and reload the vault to load the new plugin bundle; restart Marionette to start the diagnostic subscriber.

## Evidence and date handling

The model tool schema describes previews as navigation and requests an exact
`path` + `passage_id` read before factual answers. An application-authored reminder
is added to follow-up system messages after vault calls, before token counting.
It requests a focused read, adds neighbors only when needed, and distinguishes
unavailable transport from empty search results. This is model guidance, not an
enforced proof-checker; passing transport/prompt tests does not establish reliable
answer quality across real conversations.

New user-message metadata includes `current_time_utc`. The model is instructed to
compare source message dates with that current timestamp, honor explicit
corrections, treat undated plans as uncertain and never use mirror file modification
time as an event date. Contact-note guidance avoids retaining temporary plans and
requires supported explicit dates for worthwhile dated events. Existing personal
notes are not rewritten by this update. Search scores measure lexical relevance,
not truth; cite the selected dated source and omit unnecessary internal IDs.
