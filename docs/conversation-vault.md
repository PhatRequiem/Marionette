# Browse saved conversations in Obsidian

The operator-only exporter builds a local Markdown vault from SQLite user inputs
and final answers. It does not give Marionette a new tool or feed saved history
into her context. No plugin, hosted service, embedding model, or Python dependency
is required. Obsidian is an optional proprietary viewer; the files also work in
other Markdown editors.

## Refresh and open

From the checkout:

```bash
./scripts/native-linux/sync-conversation-vault.sh
```

In Obsidian, choose **Open folder as vault**, then select
`data/conversations/obsidian-vault` inside this checkout. Open `Welcome` or
`Generated/Conversations`. Search finds message text; the graph links conversation,
contact and date pages. No Obsidian Sync, Publish, account or community plugin is
needed. Keep this private vault separate from the source-code vault.

Sync is **on demand**, not automatic. Run the same command again to refresh saved
messages. It works while chat is running and does not restart the model or Discord.
For a completed session export, stop chat and Discord cleanly first. `MARIONETTE_LOG_DIR`
selects an alternate database directory; the vault stays beside that database.
Alternate log locations require operator review for memory reset, as before.

## Contents and ownership

- `Generated/`: replaceable conversation pages, contact hubs, date hubs and index.
  One conversation page represents one session + conversation ID, with stable
  hash-based filenames. Contacts link by permanent UUID, not name.
- `Annotations/`: your own optional notes; ordinary sync leaves them alone.
- `Welcome.md`: starting instructions. Obsidian manages its own `.obsidian/` settings.

Messages retain content, row ID, correlation ID, source, sender, contact UUID,
role, status and receipt timestamp. Contact names are current registry labels,
not historical evidence of names at message time. Assistant labels use Marionette.
Dates use recorded UTC timestamps. A saved answer does not establish Discord delivery.
Reasoning, command notices, tool results and raw diagnostics are excluded.

Message text is fenced as literal text: quoted Markdown, embedded images and
wikilinks do not become active graph links or remote image fetches. The generated
links supply the graph. No semantic relationships or tags are inferred.

SQLite remains authoritative. Generated edits are overwritten on the next sync;
removed records lose their generated pages. Put annotations outside Generated.
The vault is a replaceable mirror, **not a backup or a new memory database**.

## Reset, consistency and limits

The whole vault lives under the existing reset-managed `data/conversations/`
folder and is ignored by Git. Memory reset deletes it, including annotations and
Obsidian settings. Close the vault during resets so Obsidian does not recreate
cached edits. Copies outside the project remain outside automatic reset scope.

Sync reserves SQLite's writer lock while reading and publishing without changing
any database rows. This prevents an old export from being published after a
concurrent reset deletes old records. Chat writes can briefly wait; very large
histories may make manual sync disruptive. No helper process or routine diagnostic
payload writes are added. The existing RAM diagnostic policy is unchanged.

Individual files are replaced atomically; a failed sync can leave a mixture of
old and new pages. Rerun sync to repair. Symlinked export paths are refused, and
an existing unrecognized Generated directory is not overwritten. Standard local
permissions protect newly generated private files (600) and directories (700).

Synthetic tests cover literal message preservation, IDs, contact separation,
repeat sync, annotations, stale-page deletion, symlink refusal, missing databases,
and live reset deleting both generated conversations and annotations. Existing
SQLite backup/restore tests remain separate; this feature adds no restoration or
cross-database migration capability.
