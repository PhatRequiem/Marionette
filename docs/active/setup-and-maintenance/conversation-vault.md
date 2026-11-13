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
`Generated/Contacts`. Search finds message text; the graph links conversation,
contact pages and contact-specific date indexes. No Obsidian Sync, Publish, account or community plugin is
needed. Keep this private vault separate from the source-code vault.

Sync runs **automatically on orderly main-chat shutdown**, after the terminal and
diagnostic recorders drain and the session-end update is attempted. This covers
`/shutdown`, `/exit`, EOF and handled interrupts that reach launcher cleanup.
It refreshes conversations, contact notes and Active documentation. There is no
periodic refresh or background helper process, and no change to RAM diagnostic retention.
Discord may finish delivery/event logging separately; this mirror does not export
those diagnostic events. SIGKILL, power loss and OS crashes cannot guarantee a refresh.

A refresh failure is reported and makes the launcher exit unsuccessfully; it does
not delete the saved SQLite records. Retry with the manual command above. Run it
any time while chat remains open; it does not restart the model or Discord.
For a completed session export, stop chat and Discord cleanly first. `MARIONETTE_LOG_DIR`
selects an alternate database directory; the vault stays beside that database.
Alternate log locations require operator review for memory reset, as before.

## Contents and ownership

- `Generated/Contacts/<name>-<ID hash>/<name>.md`: contact name/ID and links to
  that contact's conversations. These are browsing pages, not full saved profiles.
- Each profile links to `<name> - Notes.md`, a Markdown mirror of
  `data/contact_notes/<contact-uuid>.md` at sync time. Missing source files get an
  explicit placeholder; sync never creates or edits the original notes. Editing
  the mirror does not write back and is overwritten on refresh. No conversation
  links are inferred from notes. Direct model editing of vault notes is not enabled.
- Each contact folder has its own `<name> - Dates.md` and `Conversations/` directory.
  Conversation filenames include the saved name, UTC date and a short ID. Graph
  labels therefore use readable names instead of generic Profile/Dates labels.
  Conversations are grouped by session + conversation ID + contact UUID. Names
  are readable labels; the ID suffix distinguishes contacts with identical names.
  Renaming a contact moves its generated folder on the next sync.
- `Generated/Groups/`: reserved empty folder; group chat ingestion and member links
  are not implemented. No group membership is inferred from messages.
- `Generated/Contacts.md`: shared navigation hub linking every contact profile.
  Welcome links to this index. Contact collections therefore connect through the
  Contacts hub in graph view, but there are no shared date pages. Conversation,
  profile and date links within each collection stay local to that contact.
  These are organizational compartments, not access restrictions.
- `Generated/Self documentation.md`: index linked from Welcome.
- `Generated/Self documentation/active/`: one-way mirror of the project `docs/`
  `active/` subtree only, preserving subfolders and file bytes, including Markdown, JSON and text.
  Hidden/editor files are excluded and symlinks refused. Ordinary sync refreshes
  these copies and removes copies of deleted source files. Original docs are never
  edited by sync. Internal active-docs links keep their relative layout; links outside
  `docs/active/` are not mirrored and may not resolve in the vault. Everything under `docs/development/` (experiments, history, ideas) is excluded.
  Sync removes the earlier full-docs mirror, including historical and idea copies. No model access
  or new source of model instructions is enabled.
- `Annotations/`: your own optional notes; ordinary sync leaves them alone.
- `Welcome.md`: generated starting instructions, refreshed on every sync. Obsidian manages its own `.obsidian/` settings.

Messages retain content, row ID, correlation ID, source, sender, contact UUID,
role, status and receipt timestamp. Contact names are current registry labels,
not historical evidence of names at message time. Assistant labels use Marionette.
Dates use recorded UTC timestamps. A saved answer does not establish Discord delivery.
Reasoning, command notices, tool results and raw diagnostics are excluded.

Contact notes preserve their wording and Markdown formatting. Supplied stable
`marionette-conversation:` citation destinations are translated into relative links
to exported conversations; other links remain as written. The source notes are
never rewritten. Missing destinations remain unresolved. See [note citations](../current-operation/contact-notes.md#optional-conversation-links).
Message text is fenced as literal text: quoted Markdown, embedded images and
wikilinks do not become active graph links or remote image fetches. The generated
links supply the graph. No semantic relationships or tags are inferred.

SQLite remains authoritative. Welcome and Generated edits are overwritten on the next sync;
removed records lose their generated pages. Sync also migrates the earlier flat
layout by removing its generated shared contact/date pages. Existing annotations
and Obsidian settings are preserved; manually created links to old paths may need
updating. Put annotations outside Generated.
The vault is a replaceable mirror, **not a backup or a new memory database**.

## Reset, consistency and limits

The whole vault lives under the existing reset-managed `data/conversations/`
folder and is ignored by Git. Memory reset deletes it, including annotations and
Obsidian settings and documentation copies. The original project `docs/` remains
untouched and can be mirrored again. Close the vault during resets so Obsidian does not recreate
cached edits. Copies outside the project remain outside automatic reset scope.

Sync reserves SQLite's writer lock while reading and publishing without changing
any database rows. This prevents an old export from being published after a
concurrent reset deletes old records. Chat writes can briefly wait; very large
histories may make manual sync disruptive. No background helper process or routine diagnostic
payload writes are added. The existing RAM diagnostic policy is unchanged.

Individual files are replaced atomically; a failed sync can leave a mixture of
old and new pages. Rerun sync to repair. Symlinked export paths are refused, and
an existing unrecognized Generated directory is not overwritten. Standard local
permissions protect newly generated private files (600) and directories (700).

Synthetic launcher tests also verify shutdown exports the last saved messages and
Active documentation, and a failed export leaves the closed session and database
intact with a visible error.

Synthetic tests cover literal message preservation, IDs, contact separation,
repeat sync, annotations, stale-page deletion, symlink refusal, missing databases,
contact-local link resolution, migration from the flat layout,
and live reset deleting both generated conversations and annotations. Existing
SQLite backup/restore tests remain separate; this feature adds no restoration or
cross-database migration capability.
