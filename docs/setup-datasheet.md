# Setup datasheet

Audited November 11, 2026 against checkout `48b7da7` and the saved November 11
multi-user run. This is an operator reference, not a live probe or model prompt.
Startup automatically refreshes the marked section below. The remaining audit is historical. No snapshot utility or model access is enabled.

**Evidence labels:** **Design** = current code behavior; **Configured** = requested
launch setting or pinned artifact; **Recorded** = observed in the archived run;
**Unverified** = not established by retained evidence. A configured value is not
proof of what a running process loaded. Recorded values describe that historical
run, not the current machine state.

<!-- startup-observations:start -->
## Latest startup observations

No startup has been recorded by the automatic updater yet.
<!-- startup-observations:end -->

## Application design

| Item | Information | Evidence |
|---|---|---|
| Application | Marionette, a local Python terminal chat application | Design: [session composition](../src/marionette/session.py) |
| Inference interface | Local llama.cpp HTTP server; client owns its lifetime | Design: [session.py](../src/marionette/session.py), [inference.py](../src/marionette/inference.py) |
| Tool coordinator | Qwen-Agent; pinned version 0.0.34 | Configured: [dependency input](../scripts/native-linux/agent-requirements.in), [coordination guide](qwen-agent.md); installed version not re-probed in this audit |
| Registered production tools | `update_contact_notes` and `update_soul` on ordinary identified-contact turns | Design: [conversation.py](../src/marionette/conversation.py); available tools depend on turn context |
| Interfaces | Terminal chat and optional Discord human one-to-one DMs | Design: [startup guide](../STARTUP.md), [Discord guide](discord.md) |
| Conversation scope | Separate terminal/profile and Discord-sender histories | Design: [conversation.py](../src/marionette/conversation.py) |
| Memory | Contact notes persist per contact; soul is shared; ordinary restart starts fresh conversation histories | Design: [contact notes](contact-notes.md), [soul](soul.md), [context](context.md) |
| Storage | Durable SQLite conversations; diagnostics in recorder's in-memory SQLite, saved on orderly shutdown | Design: [storage](storage.md) |
| Diagnostic retention | 500,000,000 raw bytes in 20,000,000-byte batches; latest 20 recognized error windows, up to 20 events before/after | Design: [retention](log-retention.md); metadata/index overhead is additional |
| Access | No model-facing log lookup, general shell/file reader, browsing or scheduler | Design: explicit tool registration in [coordination.py](../src/marionette/coordination.py) |
| Network dependency | Core inference is local; optional Discord needs internet and an account | Design: [setup](setup.md), [Discord](discord.md) |

These descriptions require review when code changes. They are not measurements of
hardware, proof of deployment ownership, or guarantees about model answer quality.

## Model and session configuration

Current launch defaults come from [chat.sh](../scripts/native-linux/chat.sh) and
[downloads.json](../scripts/native-linux/downloads.json). Environment variables and
per-launch arguments can change allowed settings; consult the effective command.

| Item | Configured value | Retained-run verification |
|---|---|---|
| Model | Qwen3.5-4B | Archived command selects its GGUF; loaded model metadata is missing |
| Weight precision | Q4_K_M GGUF | Command/manifest only; not independently verified from retained loading output |
| Model origin / publisher | Qwen family; GGUF publisher `unsloth/Qwen3.5-4B-GGUF` | Manifest provenance; model/license references remain in [setup](setup.md) |
| GGUF revision | `e87f176479d0855a907a41277aca2f8ee7a09523` | Pinned in manifest; no new weight checksum was performed |
| Runtime | llama.cpp b12211 | Manifest and archived executable path; build output is missing |
| Device | `Vulkan0`, all GPU layers requested | Actual loaded device/offload count unverified from retained startup evidence |
| Hardware identity | Existing baseline reports AMD RX 7900 XT, 20 GB VRAM | Historical [baseline](baseline.md); not independently reverified by this audit |
| Context capacity | 65,536 tokens | Recorded message budget confirms 65,536 |
| Reply allowance | 32,768 tokens per model request, shared by reasoning and answer | Recorded budget confirms 32,768; code uses `min(32768, capacity // 2)` |
| Next-input reserve | 2,048 at this capacity | Design: `min(2048, capacity // 8)`; startup policy marker is missing |
| Thinking | Enabled; native template receives `enable_thinking: true` | Configured in launcher and [inference.py](../src/marionette/inference.py); not a retained startup-mode observation |
| Reasoning handling | `deepseek` format, reasoning budget `-1` (no separate reasoning cap) | Archived command; combined generation allowance still applies |
| Prompt cache | 5,120 MiB system-RAM cache budget | Archived command; actual cache occupancy is dynamic and not established here |
| Parallel inference | One server slot | Archived command `--parallel 1`; startup slot observation is missing |
| Listener | Loopback `127.0.0.1`, OS-selected port; web UI disabled | Archived command; current address/health not established |
| Context handling | Client-managed fitting; server context shift disabled | Design and archived command; see [context](context.md) |

The model string in the HTTP request is an application label, not independent
proof of the loaded weights. Likewise, a filename, runtime directory or requested
GPU flag is not a runtime observation. Manifest checksums and setup verification
procedures remain authoritative in [setup](setup.md); they are not duplicated here.

## Sampling

The archived command and retained sampler records agree on these settings. Source:
archived database events **402892** and **402894**. This is historical sampler
output, not a fresh check of a running process or every request in the run.

| Setting | Value |
|---|---:|
| Temperature | 1.0 |
| Top-p | 0.95 |
| Top-k | 20 |
| Min-p | 0.0 |
| Presence penalty | 1.5 |
| Repetition penalty | 1.0 |
| Repeat-last-n | 65,536 |
| Frequency penalty | 0.0 (recorded runtime value; not explicitly set by launcher) |

This audit changes no sampling defaults. Publisher guidance and prior tradeoffs
remain in [setup](setup.md).

## Audit evidence and gaps

Read-only sources were the current code/manifest and the private external archive
`~/Marionette Archives/2026-11-11-multi-user-run/`: `run.sqlite3`,
`evidence/launch-command.json`, `evidence/manifest.json`, and exported logs.
No personal messages, identities or credentials are reproduced here.

- The current project database has zero sessions and events; it supplies no startup evidence.
- The archived manifest explicitly describes post-reset records. Reset-deleted or expired records cannot be reconstructed.
- Retained diagnostics have no matching startup markers for model name/type, loaded device, offload count, runtime build, per-sequence context, listening address or initial context policy. Do not attribute their absence specifically to eviction: reset is also documented.
- Event **402950**, recorded **2026-11-11 18:57:53.868927 UTC**, reports a 906-token prompt, 32,768-token reply allowance and 65,536-token capacity. This is one message budget, not a startup hardware observation.
- Session startup code checks `/health` and compares `/props` context capacity with runtime output before chat begins. The checks exist in code; their original startup records/API responses are not available in this archive.
- The archived command describes the selected executable and flags. Its capture does not verify binary contents, GGUF contents or effective settings independently.

## Live facts and refresh rules

| Information | Required treatment |
|---|---|
| Model, precision, runtime build, loaded device, effective limits | Confirm at the next authorized launch and associate with that session; do not silently reuse historical values |
| Tools available to a particular turn | Read actual registered tools for that turn |
| Discord ready/disconnected/resumed | Use timestamped connection events; a past connection does not establish current connectivity |
| Model server health, port, PID, cache occupancy | Treat as live/session-specific; do not freeze into permanent self-knowledge |
| Token usage, errors and delivery | Retrieve evidence for the selected message and session |
| Application architecture/policy | Review this datasheet when the relevant code changes |

A future setup collector would need to retain verified, session-scoped facts and
handle refresh/reset explicitly. The startup updater now implements the bounded observation section above; it does
not create a queryable session-history collector. This historical audit did not
launch the model. The updater does not alter diagnostic retention or supply the
datasheet to her. Unknown facts remain unknown until verified.

## Automatic startup update

`session.py` updates only the `startup-observations` marker block. It first marks
the attempt `starting`, then `ready` after runtime readiness, `/health` and the
existing context agreement check; failed startup is marked `failed`. Every attempt
clears old observed values. `ready` describes startup verification, not ongoing
health, profile selection or a completed chat turn. It remains historical after
shutdown. After profile selection and component initialization, a final startup capture adds application state before the local bridge begins serving. No updates occur for individual messages or Discord connection changes.

The updater reads bounded, recognized runtime startup fields. Model name, GGUF
file type, runtime build, loaded devices, offloaded layers, context/parallelism and
sampling are shown when present; missing/conflicting observations stay unverified. The existing launcher `--version` output supplies runtime identity, and numeric server defaults from `/props` supply sampling when available. Explicit launch arguments are a labeled configured fallback, not proof of effective settings.
Configured filenames, hardware defaults and old audit values never fill gaps.
Only allowed fields are rendered, with Markdown escaped. The application section records terminal/local bridge state, Discord offline at the initial main-chat boundary, actual startup tool registration, per-turn contact-note tool availability, installed Qwen-Agent version, initialized memory/storage components and configured retention. Discord remains a separately launched interface; this startup-only entry is not a live connectivity monitor. The sheet distinguishes a registered tool from one that binds only when a contact sends an ordinary message. No identities, session
IDs, conversations, paths or credentials are intentionally included.

Updates use atomic replacement in the document directory and preserve text outside
the markers. Missing/malformed/unwritable files produce a diagnostic warning and
leave chat startup usable; fix the file/permissions before relying on its freshness.
Do not remove or duplicate the marker pair. A detected concurrent edit cancels the
update. There is no backup copy or background updater. Launching changes this tracked
Markdown file locally; runtime never commits or pushes it.

Default target: `docs/setup-datasheet.md` in this checkout. For isolated tests or
another operator document, `MARIONETTE_SETUP_DATASHEET_PATH` selects an existing
file containing the same marker pair. Tests must use temporary documents, never
the real datasheet. This update is a bounded startup configuration summary, not
routine per-event disk logging or a change to RAM diagnostic retention.

Startup collection uses the existing launcher/runtime/API observations; it adds no
model request, inference process or ongoing polling. Unknown server properties are
ignored. The current instance is not restarted when this code changes: the expanded
account is generated on its next normal launch. Existing generated observations
are kept locally when documentation changes are committed.
