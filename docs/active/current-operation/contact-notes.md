# Contact notes

Each contact has compact Markdown notes at `data/contact_notes/<contact-uuid>.md`. The UUID comes from the [contact registry](contacts.md); the heading uses their readable name, such as `# Phat`. Linked terminal and Discord accounts share the same file. Files are private and ignored by Git. No dependency, launch command, model setting, or context allowance changes are required.

## Reading and updating

Before each ordinary message, `conversation.py` reads the current sender's file and includes its content, character count, and limit in `contact_notes` inside the existing sender metadata. This is supplied user-message context, not a new personality/system prompt. The first message creates a heading-only file if none exists. New Discord accounts receive distinct identities automatically, initially named `Discord <account-id>`. Existing conversation logs and development chats are not imported.

`contact_notes.py` provides the small storage interface (`read`, `save`, `current`) and the `update_contact_notes` Qwen-Agent tool. The tool description tells the model to proactively retain lasting preferences, relevant facts, and relationship information, consolidate old notes, distinguish uncertainty, and avoid invented facts and credentials. Small talk needs no update. The model decides when to call the tool; proactive saving is a capability, not a guarantee that every useful detail will be saved accurately.

The `update_contact_notes` tool accepts one of three entry operations, bound to the resolved current sender:

| Action | Arguments | Effect |
|---|---|---|
| `add` | `content` | Append one note; exact duplicates are rejected |
| `patch` | `old_text`, `content` | Replace one uniquely matched text span inside one entry, preserving the rest |
| `remove` | `old_text` | Delete the whole uniquely identified entry |

An exact whole-entry match takes priority over substring matches. Otherwise `old_text` must identify exactly one entry, and a patch span must occur only once inside it. Missing or ambiguous matches fail without writing. The tool cannot change the name heading, target another UUID, edit account mappings, or replace the whole document. Empty values, reserved `§` characters in arguments, and extra fields are rejected. To remove a whole note, use `remove` rather than an empty patch.

For example, the model can send:

```json
{"action":"add","content":"Prefers short answers."}
{"action":"patch","old_text":"short answers","content":"detailed answers"}
{"action":"remove","old_text":"Prefers detailed answers."}
```

Each successful operation saves immediately and returns the current entries, full file text, character count, remaining capacity, and limit. Failure returns the current valid state and a correction hint. Oversized edits report the proposed count and exact excess; nothing is truncated or saved. The model may shorten its edit, or patch/remove stale notes before adding. Operations are individually atomic; there is no batch action, so a successful removal is not undone if a later addition fails. Only a successful tool result confirms a save. Saves survive restart and `/clear`, and are not rolled back if the subsequent answer fails.

## File format and existing profiles

The readable name heading stays above the entries. A standalone `§` line introduces each entry, including the first; this distinguishes the entry format from older free-form files and supports multiline notes without confusing blank lines with entry boundaries:

```markdown
# Phat
§
Building a local AI companion.
§
Prefers short answers.
```

Existing Markdown paragraphs are interpreted as separate legacy entries; their wording is preserved. Reading alone does not rewrite an existing file. Its next successful edit saves the new separator format, normalizing surrounding whitespace but keeping unrelated entry text. The separators count toward the same 1,375-character limit. If conversion plus the edit would exceed it, the entire write is rejected and the original file remains intact. A legacy file near the limit may need an entry shortened or removed before it can be saved in the new format. No facts are imported, inferred, or automatically corrected during conversion.

## Boundaries

- **1,375 characters maximum**, including the name heading, entry separators, spaces, and newlines. Counting uses Python Unicode code points, not UTF-8 bytes or tokens; a multi-part emoji may count as several characters. Over-limit writes are rejected without truncating or changing the existing file.
- Files use UTF-8, permission `600`, and atomic replacement. Stale updates are rejected if the file changed since it was supplied. Invalid existing files and symbolic links fail rather than being silently overwritten. Stop chat before manually editing files; this is a single-application writer, not a multi-process database.
- Profiles and tool schemas count toward the existing context budget. The latest snapshot is supplied again after rollover or a clear; earlier snapshots in retained messages are historical. There is no separate reserved memory window.
- Histories are separate for each Discord sender and the terminal. Only the current contact’s notes are supplied. Linked accounts intentionally share those notes, so a fact saved from your terminal chat may be available in your Discord DM. The local operator terminal and logs still display every conversation; they are not private from the operator.
- With a tool registered, reasoning still streams locally, but answer text is held until the final response to avoid displaying tool-call preambles as answers. Discord receives only final answers and existing status/error notices. Tool calls/results remain with the exchange in active conversation context until trimming or clear/restart. The durable Markdown is still supplied afresh on the next turn.
- This tool edits bounded contact notes only. Log queries and optional read-only vault browsing are separate tools; no automatic skill creation or general filesystem access is provided.

## Optional conversation links

For saved conversations, Sender metadata now supplies `conversation_reference`,
a stable `marionette-conversation:<32-hex-ID>` destination derived from the session,
conversation ID and contact UUID. It is included before exact prompt counting and
retained with that user message. It does not depend on a contact's current name or
vault filename. No reference is supplied for turns without a conversation store/session.

The feature prompt teaches optional inline Markdown, for example
`[Plays banjo](REFERENCE)`, replacing REFERENCE with the exact supplied destination.
The model should only cite a conversation that supports the statement, never invent
references, and may leave ordinary notes or explicitly subjective relationship
impressions unlinked. Patch/remove use the existing tool fields; link markup counts
toward the existing 1,375-character limit. No schema, new tool, or mandatory citation
is introduced. Reference correctness and relevance are model responsibilities;
existence of a link is not proof of a claim. Historical notes are not auto-linked.

Source note files retain these stable internal references. They are not browser URLs
or directly usable Obsidian paths. On vault sync (orderly shutdown or manual refresh), known destinations become
relative Markdown links to the current generated conversation pages. Renaming a
contact and resyncing regenerates the correct destination. Unknown or missing
references are kept as written, not resolved to guessed pages. A missing export or
conversation means the citation cannot be opened from the vault until available.
Unrelated note text and the original source file are unchanged by export.

Optional [read-only vault browsing](../setup-and-maintenance/obsidian-connection.md) can retrieve mirrored notes; direct vault editing remains disabled.

## Obsidian mirror

The [conversation-vault sync](../setup-and-maintenance/conversation-vault.md) mirrors existing notes
for contacts with exported conversations into their `<name> - Notes.md` page, linked
from the profile. The original file remains authoritative. No vault write-back is enabled. Optional read-only access is configured separately.

## Inspection, backup, and restoration

Read or edit the Markdown locally while chat is stopped. Keep edits within the limit; invalid UTF-8, control characters other than tabs/newlines, or oversized text will fail validation on the next message. Keep the readable `# Name` heading and use the separator format above; malformed entry layout is rejected when edited. Identity timestamps describe identity changes, not contact-note edits. Character supply/update/rejection events record the UUID and size in existing diagnostics; runtime/tool diagnostics may contain the notes themselves. Keep logs private too.

For a backup, stop chat and copy both `data/contacts/profiles.json` and the entire `data/contact_notes/` directory to private storage. Restore them together, preserving UUID filenames and file permissions, before launching again. Do not overwrite newer data without first saving it. Markdown is the portable storage format; the contact registry supplies contact/account provenance, and dated session logs record tool activity. There is no per-fact source ledger or automatic revision history.

Cross-database migration is not applicable to this Markdown file store. Back up the matching contact registry separately.
