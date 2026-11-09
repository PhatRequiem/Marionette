# Profiles and sender identity

At main-chat startup, choose a saved terminal profile or **Add new profile**. The initial profile is **Phat**. New names must be unique (ignoring case), printable, and 1–80 characters. A profile receives one random UUID when created; selecting it again never generates a new ID. Restart main chat to select a different terminal profile.

## Saved mapping

`data/identities/profiles.json` is the authoritative private registry, saved as readable UTF-8 JSON with file permission `600` and atomic replacement. It contains:

- `version`: format version, currently 1.
- `owner_uuid`: the initial Phat profile's permanent UUID.
- `profiles`: records containing `uuid`, display `name`, and `discord_id` (a string or null).

At startup, the configured `DISCORD_ALLOWED_USER_ID` from `data/discord/.env` is linked to the owner profile if not linked already. No bot token is copied into profiles. With no Discord configuration, terminal profiles still work offline. After adding Discord configuration, restart main chat before connecting Discord. A changed account or conflicting mapping stops startup with an error rather than silently transferring identity; review the saved mapping deliberately before relinking.

Selecting another terminal profile never transfers your Discord account to it. Discord still accepts only the configured owner; adding a terminal profile does not grant Discord access. Selecting a terminal name is identification, not authentication. Anyone able to use the local terminal can select that name.

## What she receives

`src/marionette/identity.py` resolves the sender and prefixes each user message with a labeled JSON metadata block containing `source`, `sender_id`, `display_name`, and `person_uuid`, followed by the original message. Terminal sender IDs use the selected profile's UUID; Discord sender IDs use the Discord account number. Thus Phat has the same person UUID across both sources. Unknown Discord identities are rejected instead of being treated as the owner.

The main diagnostic logs record **Sender identity** with these fields; the normal transcript records profile selection, messages and replies. Metadata is counted before generation and retained with each user message. `/clear` resets shared conversation history without deleting profiles. The application interprets `/clear` before adding metadata; it is not sent as ordinary message content.

All profiles still share one history, budget, and rollover policy. This adds no relationship records, separate histories, persistent model memory, or file-reading access. Sender labels help the model interpret messages; they do not enforce permissions or guarantee that it interprets identity correctly. Access restrictions remain in code.

## Backup and maintenance

Stop main chat before editing or restoring this file. Back it up privately and restore it to the same location to retain UUIDs and account links. Do not delete it to clear a conversation: recreating it generates different identities. Invalid data fails visibly rather than resetting profiles. Names may be changed while preserving UUIDs; keep names unique. Profiles are not committed to Git and are not part of the older `baseline-v2` checkpoint.

The same-version JSON backup/restore and source mapping are covered by synthetic tests in `tests/core/test_identity.py`. No cross-database migration or memory restoration is implemented or claimed. The format remains portable JSON with explicit account provenance. `MARIONETTE_DATA_DIR` overrides the identity/config lookup root for isolated tests; it does not relocate other launcher files. Normal launches use the checkout's `data/` folder.
