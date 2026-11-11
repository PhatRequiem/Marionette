# Project workflow

These instructions apply throughout this repository.

## Direction and change scope

- Future scaling is intended. Prioritize a reliable, understandable base and incremental additions; simplicity must not be mistaken for abandoning scalability.
- Consult README.md, docs/baseline.md, and the relevant component guide before making changes. Treat experiment reports as historical evidence, not current configuration. Preserve established launch commands and behavior unless the requested change requires otherwise.
- When the user requests discussion or confirmation first, investigate and present a concrete proposal without editing. Once implementation is authorized, complete the agreed scope without adding unrelated features.

- Treat `docs/ideas/` as discussion-only notes. Saving or editing an idea does not authorize implementation; require a separate explicit user instruction before acting on it. Ideas do not override the current baseline or project rules.

## Complete and sync changes

- Work in small, focused changes. Run appropriate checks, update relevant documentation, and review the diff.
- Commit only intended files with a clear message, then push to the configured GitHub remote and tracking branch. Routine commits and pushes are authorized without asking again.
- Verify the remote contains the commit before reporting success. If checks, committing, or pushing fail, report the problem and what remains local.
- Preserve unrelated user changes. Never force-push, overwrite remote history, or discard user changes without explicit permission; resolve conflicts safely.
- Review-only and explanatory requests do not require edits or commits.
- Explain what changed, why, and how it was checked. Distinguish planned features from verified behavior.

## Protect private files

- Never commit secrets, `.env`, conversations, memory databases, model weights, runtime binaries, VM disks, logs, or local backups. Do not bypass `.gitignore` to add them.
- Keep private application data under `data/` and safe configuration examples in `.env.example`.
- Use synthetic profiles and separate data directories for tests. Never add test conversations or facts to real profiles.

## Preserve long-term independence

- Choose free, open-source dependencies for core software. Verify actual licenses; distinguish open source from source available, and disclose paid feature restrictions before adoption. Review model licenses separately.
- Keep `docs/licenses.md` limited to software actively used by the application, runtime, setup, and maintenance workflows, including required runtime dependencies. Update it in the same change when those dependencies change. Exclude proposed tools and dependencies used only in tests or experiments, even if those tests have run.
- Keep core operation local, without required subscriptions, hosted APIs, vendor accounts, or license-server access.
- Keep conversations, identities, and memories exportable in documented, portable formats with provenance. Test backup restoration and migration before relying on a storage system for real memories. Report same-version restoration and cross-database migration separately; keep unverified requirements visible.
- Keep storage and memory integrations replaceable through small interfaces. Weigh project maintenance, upgrade paths, and custom-code burden alongside features; open source alone does not guarantee future support.
- Record dependency versions, setup steps, and significant tradeoffs in project documentation so another maintainer can rebuild and operate Marionette.
- When dependencies, download versions, paths, or setup requirements change, update the affected component's setup/bootstrap scripts, lockfiles, download manifests (including checksums), and rebuild instructions in the same change. Change the core bootstrap only when affected; verify the changed rebuild steps.

## Shared AI infrastructure

- Before downloading or installing an AI model or inference engine, check the existing shared libraries under `~/AI Infrastructure/`. Reuse a compatible installation or verified model file when available.
- Verify compatibility using the required version, model variant, format, precision, and checksum where available. Matching filenames alone are not enough. Do not substitute a different model or precision without approval.
- Store model weights under `~/AI Infrastructure/AI Local Models/<Provider>/<Family>/<Parameter Size>/<Variant>/`. Use appropriate variants such as `Instruct`, `Base`, `Heretic`, or `Embedding`, based on verified source information. Preserve original filenames and keep supporting files together.
- Provider means the original model developer. Record the actual download publisher, source URL, revision, precision, and checksum in the shared library’s `catalog.json`. Keep distinct derivatives or revisions in separate subfolders.
- Store inference engines under `~/AI Infrastructure/AI Apps/Inference Engines/<Category>/<Engine>/<Version>/`. Categories include `Language Models`, `Image Generation`, and `Speech`. Keep each installation’s bundled libraries and licenses together.
- Preserve versions required by other projects. Do not overwrite, remove, or relocate shared files without checking their consumers and obtaining authorization for destructive changes.
- Keep project-specific code, environments, credentials, conversations, profiles, and memories in their established project locations. System packages such as Vulkan and GPU drivers remain managed by Linux.
- Make setup and launch scripts use the same shared locations. Setup should verify and reuse existing files before downloading replacements. Update relevant manifests and documentation, and verify setup and generation after changes.

## Model configuration and sampling

On initial setup or changes to the model, weight precision, reasoning mode, or runtime, review the model publisher's official guidance for sampling, chat templates, token limits, and reasoning handling. Use the recommended sampling settings for the selected model, mode (thinking or non-thinking), and task. Do not silently inherit runtime defaults or the previous model's settings. Explain material quality, speed, and memory tradeoffs before selecting a default. Do not choose quantization solely because it is common or smaller. Verify the effective settings in the runtime logs, document the source and any deliberate deviations, and test generation before calling the change complete. If official recommendations are unavailable, state that explicitly and document the chosen settings.

## Evidence and evaluation

- Distinguish successful loading, functional tests, answer quality, performance, and long-session reliability. A passing smoke test does not establish all five. When comparing configurations, keep other variables consistent where practical and record what changed.
- Use configuration, model metadata, runtime logs, and process observations to establish how the system works. The model's statements about its identity, hardware, hosting, or capabilities are not verification.

## Organize for human maintainers

Keep the project understandable without reading development chats.

1. **Clear folder responsibilities:** Follow the folder map in the README and document new folders. Keep application guides directly under `docs/`; keep platform-specific launch and setup scripts under `scripts/native-linux/`. Store session transcripts and diagnostic logs under `data/conversations/`; keep project-specific tools under `runtime/` and shared inference engines in the shared AI infrastructure locations above.
2. **Concise documentation:** Keep the main README focused on purpose, status, quick start, architecture, folder map, and guide links. Give each topic one authoritative explanation and link to it. Put experiment reports under `docs/experiments/`.
3. **Repeatable scripts:** Save documented setup, start, and stop commands in `scripts/`, including supported background operation and logging.
4. **Documented decisions:** Record significant architecture choices and their reasons in `docs/`, linked from the README.
5. **Source and operation:** Native Linux runs directly from its Git checkout using scripts/native-linux/. Keep setup and operation reproducible from this checkout.
