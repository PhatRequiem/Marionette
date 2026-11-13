# Soul

The soul contains a permanent UUID, an editable name, and an editable personal description. Both editable fields start empty; no name, identity claim, or fixed self-description instruction is supplied. They are shared across terminal and Discord conversations, separately from contact profiles.

## Storage and editing

`data/soul/profile.json` is the authoritative private file. Schema 2 contains `uuid` and an ordered `revisions` list. Each revision is a complete snapshot with `name`, `content` (the soul), UTC `created_at`, and `source`. The last revision is current. New records start with blank name and content, labeled `blank initialization`.

The `update_soul` tool accepts `name`, `content`, or both. Omitted fields remain unchanged; empty strings clear them. Names allow at most 80 printable characters, and descriptions allow 1,375 characters including whitespace and formatting. Results include the UUID, current name and description, save status, and remaining description capacity. Invalid, oversized, and stale edits fail without overwriting data. Only changed snapshots create revisions. The tool cannot change the UUID, choose a file path, delete revisions, or edit contact account links or owner permissions. The contact `update_contact_notes` tool remains separate.

The tool description asks the model to proactively maintain its own name and personal description, and directs facts about contacts to `update_contact_notes`. There is no fixed system identity instruction. The model may choose not to edit anything; its training, user messages, and tool definitions still influence its behavior.

## Context and startup

Before readiness, startup reads the profile and prepares the native chat prefix. Tool guidance is supplied separately, even while the soul is blank. Once filled, the personal section appended after that guidance consists of `Name: <chosen name>` (only if set), followed by the description verbatim (only if set), separated by a blank line. No name is inferred from description text. Name edits do not rename the application, Discord account, or contact profiles.

Each ordinary turn refreshes this state and the tool binding. Edits become system context on the next turn in any conversation. The ongoing tool loop keeps its original prompt and receives the saved state through the tool result. A failed final answer does not undo a successful save. The inference boundary includes system text in template rendering, exact token counts, generation, and cache preparation. History rollover and `/clear` do not delete the soul. Restart clears conversation histories but preserves the soul.

The application does not supply a fixed self-description. Native chat-template/tool formatting and Qwen's learned identity still apply. Changing the description may invalidate cached prefixes. Startup preparation does not guarantee cache reuse.

## Migration, backup, and comparison

Opening schema 1 upgrades it to schema 2 by adding an empty name to every revision. UUIDs, description text, timestamps, and source labels are preserved. Migration alone does **not** clear an existing description. Old revisions are not included in model context. An already running process must stop before migrating or resetting its file.

Stop chat and copy `data/soul/profile.json` to private backup storage. Restore it before starting a replacement checkout to retain the UUID; preserve newer data first and use file permissions `600`. `MARIONETTE_DATA_DIR` redirects the soul directory for isolated tests. Deleting the file causes a new UUID at initialization. Invalid existing records fail visibly instead of creating a new identity.

JSON is the portable export: each revision contains plain-text name and description values suitable for comparison or Markdown export. Retain the complete file to preserve timestamps and provenance. Successful model edits are labeled `update_soul`; the file does not record a per-edit conversation ID. Revisions grow without automatic pruning. Writes use atomic replacement and private permissions; turns are serialized, and external writers must stop chat first.

Cross-database migration is not implemented or claimed. Back up contact profiles and conversations separately using their guides. A persistent UUID does not establish continuity of consciousness. Spontaneous self-editing and long-session reliability are not guaranteed.
