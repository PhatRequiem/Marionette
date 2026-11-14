# Operator commands

Type `/help` in terminal or a Discord DM for the complete command list and permission labels.
Commands are handled by application code, not the model. Terminal-only commands retain their
existing restrictions. Discord admission rules apply before accepting non-owner commands.

| Command | Behavior | Permission |
|---|---|---|
| `/status` | Fresh model health, Discord and Scarecrow probes, main-chat uptime and DM policy counts | Owner |
| `/connections` | Terminal presence and fresh Discord/Scarecrow connection observations | Owner |
| `/context` | Token count of this conversation’s retained history with current template/tools, reply allowance and remaining input budget | Current contact |
| `/sync` | Full conversation, contact-note and Active documentation mirror refresh | Owner |
| `/cancel` | Request cancellation of the active generation, including a different contact’s generation | Owner |
| `/ddm allow <user>` | Allow a numeric Discord user ID or mention even when general DM access is off | Owner |
| `/ddm block <user>` | Block that user even when general DM access is on | Owner |

Status observations are bounded probes, not a guarantee of subsequent success. Unreachable
services report unavailable/unknown. Uptime starts when main chat initializes its conversation
controller. `/context` counts retained context, not lifetime token consumption. A new message,
its identity metadata and refreshed notes consume additional input budget. It does not generate
a reply or deliberately trim history; any previously pending preparation completes first.

`/sync` calls the existing exporter using this session’s database and data directory. It can
create the managed mirror if absent, including after a memory reset. It exports saved data at
that point; routine RAM diagnostics remain in RAM. Errors are reported and can be retried.
See [mirror ownership and refresh](../setup-and-maintenance/conversation-vault.md).

## Cancelling a response

In an interactive terminal, type `/cancel` and press Enter while generation is running. The
input watcher passes cancellation directly to the owner-checked handler. Other complete lines
typed during a turn are queued in order for the normal input loop. This watcher is not enabled
for piped/non-interactive stdin. Owner Discord `/cancel` bypasses both the adapter’s turn queue
and main chat’s turn queue, so it can interrupt a reply already running.

Cancellation sets a per-generation flag and closes an available HTTP stream. It is checked at
stream and tool boundaries. Waiting for response headers or a tool already executing may delay
completion; this is not a hard process kill. Completed tool actions are not undone. Partial
streamed terminal text may already be visible and diagnostic/input records remain, but the
cancelled input and partial answer are not added to active context. The model stays loaded,
existing history stays intact, and the next ordinary turn clears the cancellation flag. If no
generation is active, the command reports that rather than clearing queued messages or memory.

The other operator commands run through the normal serialized turn path and may wait while a
generation is active. Use `/cancel` first when necessary.

## Per-user Discord rules

`/ddm allow 123456789` and `/ddm block <@123456789>` accept IDs or Discord mentions,
not display names. Setting one rule removes the opposite rule for that user. A block takes
precedence over general access; an allow overrides general-off. The owner cannot be blocked.
`/ddm` reports general access and rule counts; `/ddm on` and `/ddm off` preserve exceptions.
Rules persist in the private admission-policy JSON, survive restart/reset, and apply on the
next admission check. They do not erase earlier conversations or recall delivered messages.
Invalid policy files fail closed for other users. See [DM admission](../setup-and-maintenance/discord.md#dm-access-control).
