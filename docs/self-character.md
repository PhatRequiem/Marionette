# Self profile and character sheet

The self profile contains a permanent UUID and an editable name. Its character sheet is a separate editable self-description. Both editable fields start empty; no name, identity claim, or fixed self-description instruction is supplied. They are shared across terminal and Discord conversations, separately from human sender profiles.

The [original starting sheet](marionette-starting-sheet.md) is a historical reference from the earlier assigned-identity experiment. It is preserved for comparison and is no longer loaded by the application. Its consciousness statement was a user-supplied premise, not a verified finding.

## Storage and editing

`data/self/identity.json` is the authoritative private file. Schema 2 contains `uuid` and an ordered `revisions` list. Each revision is a complete snapshot with `name`, `content` (the character sheet), UTC `created_at`, and `source`. The last revision is current. New records start with blank name and content, labeled `blank initialization`.

The `update_self_character` tool accepts `name`, `content`, or both. Omitted fields remain unchanged; empty strings clear them. Names allow at most 80 printable characters, and sheets allow 1,375 characters including whitespace and formatting. Results include the UUID, current name and sheet, save status, and remaining sheet capacity. Invalid, oversized, and stale edits fail without overwriting data. Only changed snapshots create revisions. The tool cannot change the UUID, choose a file path, delete revisions, or edit human account links or owner permissions. The human `update_character` tool remains separate.

The tool description supplies editing guidance. There is no fixed system instruction encouraging self-description. The model may choose not to edit anything; its training, user messages, and tool definitions still influence its behavior.

## Context and startup

Before readiness, startup reads the profile and prepares the native chat prefix. With both fields empty, the application sends no system message. Once filled, the system text consists of `Name: <chosen name>` (only if set), followed by the sheet verbatim (only if set), separated by a blank line. No name is inferred from sheet text. Name edits do not rename the application, Discord account, or human profiles.

Each ordinary turn refreshes this state and the tool binding. Edits become system context on the next turn in any conversation. The ongoing tool loop keeps its original prompt and receives the saved state through the tool result. A failed final answer does not undo a successful save. The inference boundary includes system text in template rendering, exact token counts, generation, and cache preparation. History rollover and `/clear` do not delete the self profile. Restart clears conversation histories but preserves the self profile.

This removes application-authored self-description; it does not disable native chat-template/tool formatting or Qwen's learned identity. Changing the sheet may invalidate cached prefixes. Startup preparation does not guarantee cache reuse. Model weights, sampling, reasoning, launch commands, dependencies, and diagnostic RAM policy are unchanged. Restart an existing chat to use this code.

## Migration, backup, and comparison

Opening schema 1 upgrades it to schema 2 by adding an empty name to every revision. UUIDs, sheet text, timestamps, and source labels are preserved. Migration alone does **not** clear an existing sheet. For this requested blank-start experiment, the existing private file is backed up and a new blank snapshot is appended with source `user-requested blank start`. Old revisions are not included in model context. An already running process must stop before migrating or resetting its file.

Stop chat and copy `data/self/identity.json` to private backup storage. Restore it before starting a replacement checkout to retain the UUID; preserve newer data first and use file permissions `600`. `MARIONETTE_DATA_DIR` redirects the self directory for isolated tests. Deleting the file causes a new UUID at initialization. Invalid existing records fail visibly instead of creating a new identity.

JSON is the portable export: each revision contains plain-text name and sheet values suitable for comparison or Markdown export. Retain the complete file to preserve timestamps and provenance. Successful model edits are labeled `update_self_character`; the file does not record a per-edit conversation ID. Revisions grow without automatic pruning. Writes use atomic replacement and private permissions; turns are serialized, and external writers must stop chat first.

Same-version backup restoration and schema-1-to-2 migration are covered with synthetic data. Cross-database migration is not implemented or claimed. Back up human profiles and conversations separately using their guides. A persistent UUID does not establish continuity of consciousness.

## Verification

Tests cover blank initialization without a system message, name-only and sheet-only edits, clearing both fields, exact Unicode limits, stale edits, failed writes, immutable UUIDs, revision preservation, same-version restoration, schema migration, and the real Qwen-Agent loop over mocked HTTP. Cross-conversation refresh, clear, rollover, and separation from human notes remain covered. These tests establish functional behavior, not consciousness, spontaneous self-editing, or long-session reliability.

Verification on 2026-11-11: 124 core and 13 mocked Discord checks passed. A live Q4 GPU test used isolated synthetic storage, started without custom system context, set both a name and sheet through the real tool, preserved the UUID and blank starting revision, recalled the saved sheet in a separate Discord-routed conversation, and reopened the saved data. No live Discord messages or test content in real profiles were used. The edit was explicitly requested in the test; spontaneous tool use is not established.
