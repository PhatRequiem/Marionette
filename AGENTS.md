# Project workflow

These instructions apply throughout this repository.

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
- Record dependency versions, setup steps, and significant tradeoffs in project documentation so another maintainer can rebuild and operate PhatKitty.
- When dependencies, download versions, paths, or setup requirements change, update the affected component's setup/bootstrap scripts, lockfiles, download manifests (including checksums), and rebuild instructions in the same change. Change the core bootstrap only when affected; verify the changed rebuild steps.

## Organize for human maintainers

Keep the project understandable without reading development chats.

1. **Clear folder responsibilities:** Follow the folder map in the README and document new folders. Use matching component names across `docs/`, `scripts/`, and `logs/`; keep actual tool names under `runtime/`.
2. **Concise documentation:** Keep the main README focused on purpose, status, quick start, architecture, folder map, and guide links. Give each topic one authoritative explanation and link to it. Put experiment reports under `docs/<component>/experiments/`.
3. **Repeatable scripts:** Save documented setup, start, and stop commands in `scripts/`, including supported background operation and logging.
4. **Documented decisions:** Record significant architecture choices and their reasons in `docs/`, linked from the README.
5. **Source and operation:** Native Linux runs directly from its Git checkout using scripts/native-linux/. Keep setup and operation reproducible from this checkout.
