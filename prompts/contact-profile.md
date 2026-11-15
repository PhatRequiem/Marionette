## update_contact_profile

Maintain the current contact's name, preferred name and timezone from explicit information they provide. For "call me Jack", save preferred_name as Jack without asking again. Use name only for an explicit display-name change. A null preferred_name means no preference is recorded; do not treat display_name or the notes heading as a preferred name. The current explicit preference takes precedence over older labels or notes. Update a clearly contradicted note when needed; do not duplicate structured profile fields in notes just to save them.

Omitted fields stay unchanged. Null clears preferred_name or timezone. Do not guess a timezone. The application owns UUIDs, linked accounts, owner/terminal permissions and timestamps. Only claim a save after success is true. Returned profile fields supersede earlier metadata; new metadata arrives next turn. Contact notes store other lasting facts. Profile edits do not write to Obsidian or prove its connection works.
