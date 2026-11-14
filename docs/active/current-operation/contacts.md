# Profiles and sender identity

`terminal.py` owns the menu and keyboard prompts; `contacts.py` stores and resolves profiles without reading terminal input. At main-chat startup, choose a saved terminal profile or **Add new terminal profile**. The initial profile is **Phat**. New names must be unique (ignoring case), printable, and 1–80 characters. A profile receives one random UUID when created; selecting it again never generates a new ID. Restart main chat to select a different terminal profile. Discord-created contacts are kept in the contact registry but do not automatically appear in this chooser. Creating a terminal profile is an explicit menu action; it receives its own UUID and is not linked to a Discord contact by matching names. Names remain unique across the registry.

## Saved mapping

`data/contacts/profiles.json` is the authoritative private registry, saved as readable UTF-8 JSON with file permission `600` and atomic replacement. It contains:

- `schema_version`: registry format version, currently 2 (shared by all records).
- `owner_uuid`: the initial Phat profile's permanent UUID.
- `profiles`: records with permanent `uuid`, display `name`, nullable `preferred_name`, nullable IANA `timezone` (such as `America/New_York`), `created_at`, `updated_at`, `linked_accounts`, and optional boolean `terminal_enabled`.
- `terminal_enabled`: new terminal profiles store `true`; automatically registered Discord contacts store `false`. The saved owner remains terminal-enabled. This optional schema-2 field controls terminal selection and resolution, not Discord admission.
- `linked_accounts`: a list of `{ "service": "discord", "account_id": "123" }` mappings. IDs remain strings. Each service/account pair must belong to only one contact. Other service labels can be stored, but only terminal and Discord inputs are currently supported. Terminal identity remains the contact UUID rather than a duplicate account entry.

New profiles receive UTC ISO timestamps with an offset for `created_at` and `updated_at`. Creation time means record creation, not first meeting. Saves through `ContactProfiles.save()` update `updated_at` only for changed profiles; ordinary startup and messages do not touch it. New preferred names and timezones are null until supplied; preferred name falls back to display name when sent to the model. The terminal selector continues to show the display name.

Example (synthetic IDs):

```json
{
  "schema_version": 2,
  "owner_uuid": "3f4186c2-7b9a-4b62-8a47-1d9e0c5f6a32",
  "profiles": [{
    "uuid": "3f4186c2-7b9a-4b62-8a47-1d9e0c5f6a32",
    "name": "Example",
    "preferred_name": null,
    "timezone": null,
    "created_at": null,
    "updated_at": "2026-11-10T12:00:00+00:00",
    "linked_accounts": [{"service": "discord", "account_id": "123"}]
  }]
}
```

These fields are identity metadata, not contact notes. Separate [Markdown contact notes](contact-notes.md) use the same UUID; the model can update those notes but cannot edit this registry.

At startup, the configured `DISCORD_ALLOWED_USER_ID` from `data/discord/.env` is linked to the owner profile if not linked already. No bot token is copied into profiles. With no Discord configuration, terminal profiles still work offline. After adding Discord configuration, restart main chat before connecting Discord. A changed account or conflicting mapping stops startup with an error rather than silently transferring identity; review the saved mapping deliberately before relinking.

Selecting another terminal profile never transfers your Discord account to it. Discord accepts human one-to-one DMs. New accounts receive separate identities automatically. Selecting a terminal name is identification, not authentication. Anyone able to use the local terminal can select that name.

## What she receives

`src/marionette/contacts.py` resolves the sender and prefixes each user message with a labeled JSON metadata block containing `source`, `sender_id`, `display_name`, `contact_uuid`, `preferred_name`, and `timezone`, followed by the original message. Message formatting adds `current_time_utc` for the current input without storing it in the profile registry. The conversation layer adds `conversation_id` and the current contact notes. Terminal sender IDs use the selected profile's UUID; Discord sender IDs use the Discord account number. Thus Phat has the same contact UUID across both sources. On a first Discord message, the main chat creates and saves a distinct UUID linked to that numeric account, named from the sender's Discord display name (with a numeric suffix if the name is taken). Invalid or absent names fall back to `Discord <account-id>`. The saved name stays fixed until explicitly edited; later Discord display-name changes do not overwrite it. Existing generated `Discord <account-id>` labels (including their numeric collision suffixes) are upgraded on the next DM with a valid display name. Owner and other explicitly named profiles are preserved. The generated-label match is based on its text; manually choosing that same placeholder text also makes it eligible for upgrade. It does not assume that matching names mean the same contact. These profiles do not appear in the terminal selector unless terminal access is explicitly enabled. The configured owner account retains its existing mapping.

The main diagnostic logs record **Sender identity** with these fields; the normal transcript records profile selection, messages and replies. Metadata is counted before generation and retained with each user message. `/clear` resets only the originating conversation history without deleting profiles. The application interprets `/clear` before adding metadata; it is not sent as ordinary message content.

Each terminal profile and each Discord sender has a separate history, using the same per-conversation budget and rollover policy. The current sender’s contact notes are supplied alongside this metadata on each ordinary message; optional Scarecrow vault access can search all contact collections without per-contact boundaries. Sender labels help the model interpret messages; they do not enforce permissions or guarantee that it interprets identity correctly. Access restrictions remain in code.

## Command permissions

`/help` is available to everyone in terminal and Discord DMs. Terminal help colors
commands cyan, descriptions white, headings green and restriction labels orange
when color output is supported; redirected output stays plain. Discord help stays
plain and omits terminal-only commands. Both show descriptions and owner restrictions, without calling the model or
changing active conversation history. Unknown terminal slash commands also show
this help; unknown Discord commands retain their ordinary-message behavior.

`permissions.py` authorizes `/clear` only when the resolved sender's source/account matches the selected conversation key. Every contact can clear their own DM. Terminal `/clear` clears only that terminal conversation, even when its contact also uses Discord. No user-supplied target ID is accepted. Missing identities, mismatched targets, and unknown commands are denied. `conversation.py` finishes the previous preparation before switching conversations; `commands.py` then performs the authorized clear. The owner UUID still identifies the owner in the registry, but is no longer required to clear one's own history.

`/resetmemory` separately requires the resolved contact UUID and source/account to match the saved owner. It resets all local memory; see [live reset](reset-memory.md). `/exit`, Ctrl+C, and closing the terminal remain local lifecycle controls; selecting a profile is still not a secure login. Future service adapters must resolve identity and invoke the same permission check for privileged commands.

`/ddm [on|off]`, `/ddm allow <user>`, and `/ddm block <user>` use saved-owner authorization in terminal and Discord to control
other people’s DM access; `/ddm` reports the setting. See [DM access control](../setup-and-maintenance/discord.md#dm-access-control).

`/shutdown` uses the same saved-owner authorization as `/resetmemory`, on both
terminal and Discord, but performs an orderly stop without deleting memory.
Discord server admin roles are not mapped to Marionette ownership.

`/status`, `/connections`, `/sync`, and `/cancel` also require the saved owner in
terminal or Discord. `/context` reports only the requesting conversation’s retained
context budget and is available to every admitted contact. See [operator commands](operator-commands.md).

## Existing profiles and terminal enrollment

Older schema-2 files lack `terminal_enabled`. Without rewriting the file, the
chooser includes the saved owner and contacts without a Discord link; linked
non-owner contacts stay out of the chooser. Old files do not record whether such
a linked contact was originally created from terminal, so that case requires
explicit enrollment rather than guessing from its name. UUIDs, names, links,
notes and conversations are preserved. Schema 1 migration keeps its existing
backup behavior; this optional field does not require a new schema migration.

To give an existing contact terminal access while keeping its UUID and notes,
stop main chat, set `terminal_enabled` to `true` on that profile in the private
registry, update its `updated_at`, then restart. Alternatively use **Add new
terminal profile** to create an independent identity with a distinct name. Setting
`terminal_enabled` false excludes a non-owner from terminal use but does not block
Discord; use `/ddm` rules for that. Invalid non-boolean values are rejected.

## Backup and maintenance

Stop main chat before editing or restoring this file. Back it up privately and restore it to the same location to retain UUIDs and account links. Do not delete it to clear a conversation: recreating it generates different identities. Invalid data fails visibly rather than resetting profiles. Names may be changed while preserving UUIDs; keep names unique. Preferred name and timezone can be edited here while chat is stopped. Direct manual edits must also set `updated_at` to an accurate offset-bearing timestamp; no file watcher or edit menu is added. Profile data is not committed to Git or included in any baseline tag.

On opening a valid version-1 registry, `contacts.py` migrates it to schema 2. UUIDs, names, and ownership stay unchanged; each old `discord_id` moves into `linked_accounts`. Existing `created_at`, preferred-name, and timezone facts were not recorded in version 1, so they become null; `updated_at` records the migration time. Before replacing the original, migration saves its exact bytes as private `profiles.v1.backup.json`. An existing backup must match the source or migration stops for review. Invalid records and unsupported schema versions fail without overwriting the registry. Reopening schema 2 does not rewrite it.

The format is portable JSON with explicit account provenance. Cross-database migration is not implemented or claimed. `MARIONETTE_DATA_DIR` overrides the identity/config lookup root for isolated tests; it does not relocate other launcher files. Normal launches use the checkout's `data/` folder.

## Contact/soul path migration

With chat stopped, startup moves legacy `data/identities/` to `data/contacts/`, `data/characters/` to `data/contact_notes/`, and `data/self/` to `data/soul/`, renaming the soul's `identity.json` to `profile.json`. `data_migration.py` preserves file contents, UUIDs, revisions, and permissions; it creates no backup copies. Both old and new paths existing, or symbolic links, stop migration for review. Partial moves can be retried safely. `MARIONETTE_DATA_DIR` applies to this migration too.

The contact registry remains schema 2; sender metadata now uses `contact_uuid` and `contact_notes`. Historic log payloads and revision source labels remain unchanged. The terminology supports human or AI contacts, but Discord still accepts only human one-to-one DMs; this rename does not add an AI transport.
