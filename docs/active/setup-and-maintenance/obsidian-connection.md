# Obsidian connection status

Model access to the vault is disconnected. The Cyanheads adapter, tool guidance, setup scripts, dependency manifests and project-local installation have been removed, together with the Local REST API plugin and its connection credentials.

The [Markdown mirror](conversation-vault.md) remains available for human browsing in Obsidian. It still refreshes on orderly shutdown or through `./scripts/native-linux/sync-conversation-vault.sh`. Conversations, contact notes and Active documentation remain intact. Core chat, Discord, contact-note/soul tools and `query_logs` are unchanged.

A custom read-only Obsidian plugin is planned, but has not been implemented or connected. There is currently no `read_vault` tool or direct model filesystem access. No replacement installation is required yet.

Prior connector test results remain in [the historical experiment report](../../development/experiments/obsidian-read-only-2026-11-13.md); they do not describe the current tool registry.
