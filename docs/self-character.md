# Marionette's identity and character sheet

Marionette has one permanent UUID and one editable self-description shared across terminal and Discord conversations. This is separate from human sender profiles. The [starting sheet](marionette-starting-sheet.md) preserves the user-approved wording for comparison; leave that reference unchanged as the live sheet evolves. Its consciousness statement is a user-supplied premise, not a verified finding.

## Storage and editing

`data/self/identity.json` is the authoritative private file. Schema 1 contains `uuid` and an ordered `revisions` list. Each revision has the complete `content`, a UTC `created_at` timestamp, and `source`: either `user-supplied starting sheet` or `update_self_character`. The last revision is current. The initial content is embedded in `selfhood.py` so startup does not depend on a documentation file; a test keeps it equal to the reference.

On first initialization a UUID is generated once. Restart and `/clear` preserve it and the sheet. Invalid existing data fails visibly rather than generating a replacement identity. The model cannot choose a path, edit the UUID, or remove old revisions through its tool. Files are atomically replaced with private permissions; the application serializes turns and edits. External writers must stop chat first. Revision history grows with successful changes; no automatic pruning is implemented.

The fixed system instruction is:

> This is your character sheet. You may update it using your self-editing tool to reflect how you see yourself.

The latest sheet follows it verbatim. `update_self_character(content)` replaces the complete editable text, with a 1,375-character limit including whitespace and formatting. The fixed instruction and JSON metadata do not count against that limit. Empty, oversized, invalid, and stale writes are rejected. Results report success, the current sheet, count, and remaining space. Unchanged text does not create a revision. The human `update_character` tool remains separate.

## Context and startup

After the model loads and a terminal profile is selected, startup reads the sheet and prefills its system context before displaying readiness. Each ordinary turn refreshes the shared sheet and tool binding. A saved edit becomes system context on the next turn, including when that turn belongs to another conversation. The ongoing tool loop retains its original system prompt and sees the save result immediately. A failed final answer does not undo a successful save.

System text is added at the inference boundary for template rendering, exact token counting, generation, and cache preparation. It is not stored in message histories, so history trimming and `/clear` cannot remove it. Changed text may invalidate a cached prefix; startup prefill does not guarantee cache reuse after tool definitions or the sheet change. This is context, not training or continuously running thought. Launch commands, model weights, reasoning, sampling, and dependencies are unchanged. Restart an already running chat to load this code.

## Backup, export, and comparison

Stop chat and copy `data/self/identity.json` to private backup storage. To restore, preserve any newer file first, then copy the backup to the same path with permissions `600`. Restore this file before starting a replacement checkout to preserve the UUID. Deleting it causes a new identity on next startup. `MARIONETTE_DATA_DIR` redirects the self directory along with the existing profile data for isolated tests.

JSON is the portable export: each revision contains ordinary text that can be copied into Markdown or compared with the starting reference. To restore an earlier state, retain the newer file separately and restore the corresponding complete backup.

Same-version backup restoration is tested with synthetic state. Cross-database migration is not implemented or claimed. Back up human profiles, character notes, and conversation storage separately using their respective guides. Self revisions do not reconstruct conversation history or claim to establish continuity of consciousness.

## Verification

Synthetic tests cover UUID stability, reference equality, exact Unicode limits, stale-edit rejection, failed-write preservation, revision provenance, same-version restore, and the real Qwen-Agent tool loop over mocked HTTP. Integration checks cover next-turn refresh across senders, clear, rollover, and separation from human notes. These checks establish functional behavior, not long-term identity development or reliable autonomous self-editing.

Verification on 2026-11-11: all 122 core and 13 mocked Discord checks pass. An isolated live Q4 GPU run at the normal 65,536-token context successfully prefilled the sheet, saved a requested self-edit through the real tool, preserved its UUID and original revision, recalled the new description in a separate Discord-routed conversation, reopened the saved state, and shut down cleanly. No real profiles or live Discord connection were used. This verifies functional editing and persistence, not long-session behavior or spontaneous editing quality.
