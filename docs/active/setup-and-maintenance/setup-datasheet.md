# Setup datasheet

This sheet records startup evidence and the latest observed application configuration, not live health. Refreshes replace only the marked block. The `query_logs` setup request reads that block on demand; the full sheet is not automatically supplied as a model prompt.

<!-- startup-observations:start -->
## Latest startup observations

No startup has been recorded by the automatic updater yet.
<!-- startup-observations:end -->

## Automatic startup update

`session.py` updates only the `startup-observations` marker block. It first marks
the attempt `starting`. It becomes `ready` only after runtime readiness, `/health`,
the context agreement check, profile selection, personal-data initialization and
entry into the local connection context. Startup failures or exit before that
point are marked `failed`. Every attempt clears old observed values. `ready`
describes completed startup verification, not ongoing health or a completed chat
turn. It remains historical after shutdown. The final startup capture adds
application state before the input loop accepts messages. Later refreshes preserve
startup evidence while replacing the application snapshot.

The updater reads bounded, recognized runtime startup fields. Model name, GGUF
file type, runtime build, loaded devices, offloaded layers, context/parallelism and
sampling are shown when present; missing/conflicting observations stay unverified. The existing launcher `--version` output supplies runtime identity, and numeric server defaults from `/props` supply sampling when available. Explicit launch arguments are a labeled configured fallback, not proof of effective settings.
Configured filenames, hardware defaults and old audit values never fill gaps.
Only allowed fields are rendered, with Markdown escaped. The application section records terminal/local bridge state, observed Discord process presence, actual tool registration, per-turn contact-note tool availability, installed Qwen-Agent version, initialized memory/storage components and configured retention. Discord remains a separately launched interface; this entry is not a live connectivity monitor. The sheet distinguishes a registered tool from one that binds only when a contact sends an ordinary message. No identities, session
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
the real datasheet. This update is a bounded setup configuration summary, not
routine per-event disk logging or a change to RAM diagnostic retention.

Startup collection uses the existing launcher/runtime/API observations; it adds no
model request or inference process. The existing terminal idle loop checks a local
configuration-file stamp; remote checks happen only for relevant events or manual refresh. Unknown server properties are
ignored. Changes to startup collection take effect on the next normal launch. Existing generated observations
are kept locally when documentation changes are committed.

## Refresh triggers

After startup, main chat refreshes at an idle or completed-turn boundary when:

- Discord starts or stops through the terminal controls, the foreground adapter
  reports startup/exit, or an owned background process exits. It observes the
  process/control endpoint; successful launch is not proof of network readiness.
- Scarecrow's connection file changes, including enable/disable. Tool registration
  and the existing event subscriber follow that configuration. Authenticated plugin
  readiness/listener events recheck the loaded version; an unchanged snapshot does
  not rewrite the page. Temporary network failures retain the last verified version
  for the same configuration/run, explicitly labeled as such.
- Registered tools or context capacity change, or memory reset completes.
- The owner enters `/refreshsetup` in the terminal. This also rechecks `/props`;
  failure retains earlier runtime evidence with an explicit unavailable observation.

Runtime/model/launch-setting changes currently require restarting Marionette; the
next startup captures them. Ordinary messages, busy/idle transitions, and transient
Discord reconnects do not themselves rewrite the sheet. Tool changes are checked at
turn boundaries. There is no new helper process or periodic document writer. While
a turn is running, background notifications wait for the main thread. Unreported
external process crashes may need a manual refresh.

Each successful source update atomically copies this document to the existing
managed Obsidian mirror beside the conversation database. It uses the database lock
shared with reset/export and never creates missing directories or pages. After
reset, the cleared vault stays absent until a normal full mirror sync. Other pages
still follow the full export schedule. Source/mirror failures are diagnosed;
`/refreshsetup` can retry. Runtime refreshes never commit or push generated facts.
