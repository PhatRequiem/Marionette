# Last saved stable baseline — baseline-v4 (2026-11-11)

Recovery checkpoint: **`baseline-v4`** in `PhatRequiem/Marionette`. This is the deliberately saved working foundation before further self-knowledge and retrieval changes. Keep this tag fixed. It captures tracked code and documentation, not personal data or an assertion that answer quality is solved. Future changes need their own checkpoint.

The [V3 guide](archive/baseline-v3-2026-11-09.md) is archived; its original tag remains unchanged. V4 adds Qwen-Agent tool coordination, separate conversations and RAM prompt caching, persistent contacts and editable soul, SQLite storage, rolling RAM diagnostics, and owner-only memory reset. Launch commands remain unchanged.

## Current checkout versus V4

The tag stays fixed. The current checkout keeps V4's model/runtime settings and
chat, Discord, soul, contact-note and diagnostic-retention foundation, with these later changes:

- Connected scoped `query_logs`, searchable metadata (SQLite schema 5), a request form and automatic startup datasheet updates.
- Tool calls/results retained with each conversation exchange and trimmed together.
- Separate feature guidance and a brief system reminder after log-tool results.
- Removed the old snapshot utilities. The experimental idle cycle, scratchpads and Obsidian integration are also removed.

See [log-query reliability limits](log-queries.md#current-reliability-limits) for
current answer-quality observations. A memory reset changes personal data, not
the code version or the baseline tag.

## Configuration at this checkpoint

| Component | Setting |
|---|---|
| Runtime | llama.cpp b12211 (`7d7f02875`), Vulkan `llama-server` |
| Model | Qwen3.5-4B Q4_K_M; Unsloth GGUF revision `e87f176479d0855a907a41277aca2f8ee7a09523` |
| Hardware used | AMD RX 7900 XT, 20 GB VRAM; Vulkan0, all GPU layers |
| Context / generation | 65,536 total; 32,768 shared reasoning/answer allowance; 2,048 next-input reserve inside the total |
| Sampling | Temperature 1.0, top-p 0.95, top-k 20, min-p 0, presence penalty 1.5, repetition penalty 1.0, repeat-last-n 65,536 |
| Reasoning | Enabled, separate local display/logging; no separate reasoning cap; Discord receives final answers and status notices |
| Inference / cache | One sequential inference slot; 5 GiB (5,120 MiB) system-RAM prompt-cache budget; active context/model use VRAM |
| Tool coordinator | Qwen-Agent 0.0.34; explicit `update_contact_notes` and `update_soul` tools only |
| Storage | SQLite schema 4 for messages/events; JSON contact registry; Markdown contact notes; revisioned JSON soul |
| Diagnostic retention | Existing recorder holds 500,000,000 raw bytes in 20,000,000-byte batches; latest 20 recognized failure windows, 20 events before/after |

Q4 is a deliberate speed tradeoff for infrastructure testing; BF16 remains in the shared model library. Publisher guidance, dependencies, licenses and reproducible downloads are documented in [setup](setup.md), [licenses](licenses.md), and [download checksums](../scripts/native-linux/downloads.json). Nothing in this checkpoint changes sampling or model precision.

## Behavior and organization

- Follow [STARTUP.md](../STARTUP.md): `./scripts/native-linux/chat.sh`, choose a terminal profile, then optionally `./scripts/native-linux/discord.sh`. Main chat plus two diagnostic views and the optional Discord connection make four terminals.
- Human one-to-one Discord DMs are accepted. Each sender has a separate conversation; terminal history is separate too. Linked accounts share contact notes, not conversation history. The main terminal displays all exchanges. Generation and preparation are sequential.
- The client owns exact token counting, oldest-complete-exchange trimming and between-turn cache preparation. Cache eviction does not erase text history. See [context](context.md).
- [Contacts](contacts.md) have permanent UUIDs and account links. [Contact notes](contact-notes.md) use Markdown entries separated by `§`, with add/patch/remove and a 1,375-character total limit. Current-contact notes are supplied automatically.
- The [soul](soul.md) has a permanent UUID, editable name (80 characters), and description (1,375 characters). Revisions preserve timestamps/source. Blank name and description produce no custom system message; populated values become system context on subsequent turns. The soul is shared across conversations. Earlier revisions are not supplied to the model.
- [Qwen-Agent](qwen-agent.md) coordinates only the registered tool loop. Tool results are available within that turn; ordinary retained history contains user messages and final answers. Persistent profile writes survive independently.
- [SQLite](storage.md) durably stores messages, terminal and Discord output. Routine diagnostics stay in RAM until orderly recorder shutdown; two colored views show shared event IDs and timestamps. [Retention](log-retention.md) governs saving and limits.
- The [log snapshot utility at V4](https://github.com/PhatRequiem/Marionette/blob/baseline-v4/docs/log-snapshots.md) exists for operators but remains disconnected from the model. No automatic log recall, general file access, browsing, skill creation, or scheduler is enabled. This describes V4; the snapshot utilities have since been removed from the current checkout.
- `/clear` clears only the sender's conversation, preserving saved records/notes. `/resetmemory` is owner-only and clears personal memory/logs while preserving permanent IDs, the owner account link and core installation. Operator resets leave the program stopped; live resets keep it loaded. See [reset scope](reset-memory.md) and [project rules](../AGENTS.md).
- Local inference needs no hosted API/account. Discord is an optional external service. The temporary unauthenticated HTTP listener remains loopback-only and stops with main chat.

The [README folder map and source guide](../README.md) remain authoritative: source under `src/marionette/`, application guides under `docs/`, platform scripts under `scripts/native-linux/`, private data under `data/`, project environments under `runtime/`. Shared model weights and inference engines live under `~/AI Infrastructure/`. No private data is included in Git.

## Verification at V4

The November 11 multi-user run lasted approximately 4 hours 53 minutes after its initial memory reset. It recorded 48 inputs, 48 reasoning records and 48 final answers across four Discord conversations. Every answer finished with `stop` and had a matching Discord delivery record. Two reconnects resumed in 120.09 ms and 102.92 ms; no recognized failures were retained. Chat-only end-to-end reply timing was 1.60–14.71 seconds, median 3.19 seconds. These are observations, not a controlled performance benchmark.

There were 62 model usage events, 13 contact-note tool invocations and one soul-update invocation. Maximum recorded prompt usage was 9,073 tokens. No nonzero exchange removal was recorded: **this run did not exercise context rollover**. Separate conversation IDs establish routing behavior, not exhaustive privacy isolation or simultaneous-load resilience.

The operator preserved a private external archive under `~/Marionette Archives/2026-11-11-multi-user-run/` before resetting memory. It contains transcripts, reasoning, retained diagnostics, final personal state, source snapshot and a full run summary. It is outside normal project memory-reset scope, contains no Discord credentials, and must not be committed. The archival source snapshot precedes the V4 documentation/tag. SQLite backup integrity and foreign keys passed; SQL export/import into an isolated SQLite database matched every table. All archived file checksums were verified. This is same-schema SQLite recovery, not cross-engine migration or a complete fresh-machine rebuild. Retention/reset-deleted evidence cannot be reconstructed.

After archiving, the authorized personal-data reset left an empty valid database, blank soul name/description with one initial revision, no contact notes, and only Phat's contact record. Both permanent IDs, owner/Discord mapping and credentials were verified unchanged. Main chat and Discord remain stopped. This local state is **not embedded in the Git tag**.

Automated checkpoint checks on 2026-11-11: **134 core and 14 mocked Discord tests passed**; all launch/setup shell scripts passed syntax checks and the changed documentation links were checked. Tests use isolated synthetic data and mocked Discord; they do not send real Discord messages. Prior live GPU/tool/cache experiments are linked from the component guides and are historical evidence, not repeated V4 load tests.

```bash
runtime/agent/bin/python -m unittest discover -s tests/core -v
runtime/discord/bin/python -m unittest discover -s tests/discord -v
for script in scripts/native-linux/*.sh; do bash -n "$script" || break; done
```

## Known limitations

- Self-knowledge is unreliable: the model invented cloud/enterprise hosting and disclosure restrictions, denied its model family, and accepted an unverified repository link as confirmation. No verified application setup report is supplied. The existing diagnostic snapshot does not answer most model/framework/ownership questions.
- Contact notes can be duplicated, poetic, subjective or factually overstated. Successful storage does not establish useful memory quality. Soul edits work, but proactive editing and explanations of earlier choices are not reliable. Stored revision provenance is not fully included in system context; persistent files do not establish consciousness or autobiographical recall.
- Context is finite. Removed exchanges are not summarized, logs are not automatically recalled, and restart begins fresh conversation histories. Heavy concurrent use, near-full-context switching/rollover at the current cache budget, and long-term reliability remain unverified by this run. The cache budget is not a guaranteed number of resident conversations or a total memory cap.
- A failed answer does not undo earlier successful tool writes. Cross-conversation shared soul changes can invalidate cached prefixes. Model-editable self-description is not an authorization boundary; permissions remain enforced in code.
- Routine RAM diagnostics can be lost on SIGKILL, OOM, crash or power failure. Expired diagnostics cannot be recovered. Conversation/terminal/Discord storage is not capped by the diagnostic budget. Same-drive archives do not protect against drive loss.
- The local HTTP server has no API key; keep it bound to loopback. Local terminal profile selection is identification, not strong authentication. Successful observed reconnects do not establish replay behavior for every missed message.
- Functional tests, loading, answer quality, performance and long-session reliability are separate claims. This checkpoint does not certify all five as complete.

## Recover this checkpoint

Stop main chat and Discord and wait for recorders. Preserve later work and private data separately; do not hard-reset or clean away changes. Use an unused recovery directory:

```bash
cd /home/phatkitty/Projects
git clone --branch baseline-v4 https://github.com/PhatRequiem/Marionette.git Marionette-baseline-v4
cd Marionette-baseline-v4
git switch -c codex/restart-from-baseline-v4
python scripts/native-linux/setup.py
```

Follow [setup prerequisites](setup.md); scripts verify/reuse the shared pinned weights and runtime. Rebuild virtual environments at the new path. For Discord, run `./scripts/native-linux/setup-discord.sh` and restore or enter credentials locally before launch. Stop any other instance using that bot.

Before first launch, privately restore `data/contacts/profiles.json` and `data/soul/profile.json` if preserving permanent IDs. Restore matching notes and the database only if wanted; use the stopped [storage recovery procedure](storage.md#backup-and-restore), never mix old WAL/SHM sidecars with a different database. A fresh checkout without those private records creates new IDs. Do not restore stale session sockets. Restore credentials with mode 600; they are never in Git.

Then use `./scripts/native-linux/chat.sh` and optionally `./scripts/native-linux/discord.sh` from that checkout. Database restoration preserves records, not automatic live conversation context. Restore personal state from the external test archive only when deliberately choosing to undo the fresh reset. Model weights, environments, credentials, conversations, profiles, visual references and OS/GPU drivers are outside this tag. A full fresh-machine restoration has not been performed for V4.
