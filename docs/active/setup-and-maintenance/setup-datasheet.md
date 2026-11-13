# Setup datasheet

This sheet records the last startup attempt, not live health. Startup refreshes only the marked block. The `query_logs` setup request reads that block on demand; the full sheet is not automatically supplied as a model prompt.

<!-- startup-observations:start -->
## Latest startup observations

No startup has been recorded by the automatic updater yet.
<!-- startup-observations:end -->

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

Default target: `docs/active/setup-and-maintenance/setup-datasheet.md` in this checkout. For isolated tests or
another operator document, `MARIONETTE_SETUP_DATASHEET_PATH` selects an existing
file containing the same marker pair. Tests must use temporary documents, never
the real datasheet. This update is a bounded startup configuration summary, not
routine per-event disk logging or a change to RAM diagnostic retention.

Startup collection uses the existing launcher/runtime/API observations; it adds no
model request, inference process or ongoing polling. Unknown server properties are
ignored. Changes to startup collection take effect on the next normal launch. Existing generated observations
are kept locally when documentation changes are committed.
