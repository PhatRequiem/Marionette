# Character profiles

Each person has compact Markdown notes at `data/characters/<person-uuid>.md`. The UUID comes from the [identity registry](identity.md); the heading uses their readable name, such as `# Phat`. Linked terminal and Discord accounts share the same file. Files are private and ignored by Git. No dependency, launch command, model setting, or context allowance changes are required.

## Reading and updating

Before each ordinary message, `conversation.py` reads the current sender's file and includes its content, character count, and limit in `character_profile` inside the existing sender metadata. This is supplied user-message context, not a new personality/system prompt. The first message creates a heading-only file if none exists. Existing conversation logs and development chats are not imported.

`characters.py` provides the small storage interface (`read`, `save`, `current`) and the `update_character` Qwen-Agent tool. The tool description tells the model to proactively retain lasting preferences, relevant facts, and relationship information, consolidate old notes, distinguish uncertainty, and avoid invented facts and credentials. Small talk needs no update. The model decides when to call the tool; proactive saving is a capability, not a guarantee that every useful detail will be saved accurately.

The tool accepts only the complete replacement Markdown in `content`. Marionette binds it to the resolved current sender before generation. The model cannot choose a path, another UUID, or edit identity/account mappings. A successful result confirms the write; a rejected result returns the error and current valid notes so the model can revise and retry. Saves survive restart and `/clear`. A save is not rolled back if the subsequent model answer fails.

## Boundaries

- **1,375 characters maximum**, including the name heading, spaces, and newlines. Counting uses Python Unicode code points, not UTF-8 bytes or tokens; a multi-part emoji may count as several characters. Over-limit writes are rejected without truncating or changing the existing file.
- Files use UTF-8, permission `600`, and atomic replacement. Stale updates are rejected if the file changed since it was supplied. Invalid existing files and symbolic links fail rather than being silently overwritten. Stop chat before manually editing files; this is a single-application writer, not a multi-process database.
- Profiles and tool schemas count toward the existing context budget. The latest snapshot is supplied again after rollover or a clear; earlier snapshots in retained messages are historical. There is no separate reserved memory window.
- History remains shared across terminal and Discord. Binding writes to the current person does **not** isolate previous messages or profile snapshots from other people in that shared conversation. Separate private conversations are not implemented.
- With a tool registered, reasoning still streams locally, but answer text is held until the final response to avoid displaying tool-call preambles as answers. Discord receives only final answers and existing status/error notices. Tool calls/results stay within the active turn, while the durable Markdown is supplied again on the next turn.
- This adds bounded character notes only: no log reader, broader memory search, automatic skill creation, or general file access.

## Inspection, backup, and restoration

Read or edit the Markdown locally while chat is stopped. Keep edits within the limit; invalid UTF-8, control characters other than tabs/newlines, or oversized text will fail validation on the next message. Identity timestamps describe identity changes, not character-note edits. Character supply/update/rejection events record the UUID and size in existing diagnostics; runtime/tool diagnostics may contain the notes themselves. Keep logs private too.

For a backup, stop chat and copy both `data/identities/profiles.json` and the entire `data/characters/` directory to private storage. Restore them together, preserving UUID filenames and file permissions, before launching again. Do not overwrite newer data without first saving it. Markdown is the portable storage format; the identity registry supplies person/account provenance, and dated session logs record tool activity. There is no per-fact source ledger or automatic revision history.

Same-format restoration and reopening are tested with synthetic notes, including Unicode and exact-limit content. Cross-database migration is not applicable to this file store and is not claimed. Returning to historical `baseline-v3` does not load character files; preserve them and follow the identity guide's separate registry rollback instructions.

## Verification — 2026-11-10

The complete regression run passes 63 core and 11 mocked Discord checks. Seven character checks cover exact boundaries, rejected writes, identity/path restrictions, stale edits, disk failure, linked accounts, clear/rollover refresh, same-format restore, and the real Qwen-Agent loop over mocked HTTP responses. The loop test rejects oversized notes, accepts the model's corrected replacement, and retains only the final answer in conversation history.

A local GPU test used the existing Q4 model, normal 65,536 context and sampling settings, and isolated synthetic data. The model proactively saved a hobby and response preference, then answered the hobby question in a new conversation using the saved file. The server shut down afterward. This demonstrates functional persistence and tool use, not long-session reliability, universal recall, or profile accuracy. No real profiles or Discord messages were used.
