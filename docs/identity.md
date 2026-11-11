# Profiles and sender identity

`terminal.py` owns the menu and keyboard prompts; `identity.py` stores and resolves profiles without reading terminal input. At main-chat startup, choose a saved terminal profile or **Add new profile**. The initial profile is **Phat**. New names must be unique (ignoring case), printable, and 1–80 characters. A profile receives one random UUID when created; selecting it again never generates a new ID. Restart main chat to select a different terminal profile.

## Saved mapping

`data/identities/profiles.json` is the authoritative private registry, saved as readable UTF-8 JSON with file permission `600` and atomic replacement. It contains:

- `schema_version`: registry format version, currently 2 (shared by all records).
- `owner_uuid`: the initial Phat profile's permanent UUID.
- `profiles`: records with permanent `uuid`, display `name`, nullable `preferred_name`, nullable IANA `timezone` (such as `America/New_York`), `created_at`, `updated_at`, and `linked_accounts`.
- `linked_accounts`: a list of `{ "service": "discord", "account_id": "123" }` mappings. IDs remain strings. Each service/account pair must belong to only one person. Other service labels can be stored, but only terminal and Discord inputs are currently supported. Terminal identity remains the person UUID rather than a duplicate account entry.

New profiles receive UTC ISO timestamps with an offset for `created_at` and `updated_at`. Creation time means record creation, not first meeting. Saves through `Profiles.save()` update `updated_at` only for changed profiles; ordinary startup and messages do not touch it. New preferred names and timezones are null until supplied; preferred name falls back to display name when sent to the model. The terminal selector continues to show the display name.

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

These fields are identity metadata, not character notes. No Markdown character files or profile-editing model tools are introduced by this change.

At startup, the configured `DISCORD_ALLOWED_USER_ID` from `data/discord/.env` is linked to the owner profile if not linked already. No bot token is copied into profiles. With no Discord configuration, terminal profiles still work offline. After adding Discord configuration, restart main chat before connecting Discord. A changed account or conflicting mapping stops startup with an error rather than silently transferring identity; review the saved mapping deliberately before relinking.

Selecting another terminal profile never transfers your Discord account to it. Discord still accepts only the configured owner; adding a terminal profile does not grant Discord access. Selecting a terminal name is identification, not authentication. Anyone able to use the local terminal can select that name.

## What she receives

`src/marionette/identity.py` resolves the sender and prefixes each user message with a labeled JSON metadata block containing `source`, `sender_id`, `display_name`, `person_uuid`, `preferred_name`, and `timezone`, followed by the original message. Terminal sender IDs use the selected profile's UUID; Discord sender IDs use the Discord account number. Thus Phat has the same person UUID across both sources. Unknown Discord identities are rejected instead of being treated as the owner.

The main diagnostic logs record **Sender identity** with these fields; the normal transcript records profile selection, messages and replies. Metadata is counted before generation and retained with each user message. `/clear` resets shared conversation history without deleting profiles. The application interprets `/clear` before adding metadata; it is not sent as ordinary message content.

All profiles still share one history, budget, and rollover policy. This adds no relationship records, separate histories, persistent model memory, or file-reading access. Sender labels help the model interpret messages; they do not enforce permissions or guarantee that it interprets identity correctly. Access restrictions remain in code.

## Command permissions

`permissions.py` separately authorizes commands using the resolved person UUID and saved `owner_uuid`. `/clear` is owner-only, whether sent from the Phat terminal profile or its linked Discord account. Another profile cannot clear shared history merely because it exists. Unlinked service senders fail identity lookup; linked non-owners receive a permission-denied reply, with history unchanged and no model generation. Missing identities and unknown commands are denied by the permission function. `conversation.py` routes `/clear` to `commands.py`, which checks authorization before changing history or waiting for pending preparation. `permissions.py` decides who may execute it; `commands.py` performs the action.

This is deliberately limited to `/clear`, the current shared-history command. `/exit`, Ctrl+C, and closing the terminal remain local lifecycle controls; selecting a profile is still not a secure login. Future service adapters must resolve identity and invoke the same permission check for privileged commands.

## Backup and maintenance

Stop main chat before editing or restoring this file. Back it up privately and restore it to the same location to retain UUIDs and account links. Do not delete it to clear a conversation: recreating it generates different identities. Invalid data fails visibly rather than resetting profiles. Names may be changed while preserving UUIDs; keep names unique. Preferred name and timezone can be edited here while chat is stopped. Direct manual edits must also set `updated_at` to an accurate offset-bearing timestamp; no file watcher or edit menu is added. Profile data is not committed to Git or included in any baseline tag. `baseline-v3` restores the identity code; preserve the private JSON file separately to retain your UUIDs.

On opening a valid version-1 registry, `identity.py` migrates it to schema 2. UUIDs, names, and ownership stay unchanged; each old `discord_id` moves into `linked_accounts`. Existing `created_at`, preferred-name, and timezone facts were not recorded in version 1, so they become null; `updated_at` records the migration time. Before replacing the original, migration saves its exact bytes as private `profiles.v1.backup.json`. An existing backup must match the source or migration stops for review. Invalid records and unsupported schema versions fail without overwriting the registry. Reopening schema 2 does not rewrite it.

The same-version JSON backup/restore, version-1-to-2 migration, retry after a failed write, and source mapping are covered by synthetic tests in `tests/core/test_identity.py`. No cross-database migration or memory restoration is implemented or claimed. Baseline V3 only understands version 1: before returning to it, stop chat and preserve the current registry separately, then restore the version-1 backup. That backup will not include later profile edits. The format remains portable JSON with explicit account provenance. `MARIONETTE_DATA_DIR` overrides the identity/config lookup root for isolated tests; it does not relocate other launcher files. Normal launches use the checkout's `data/` folder.
