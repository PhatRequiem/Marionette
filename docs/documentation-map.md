# Documentation map

## Active — mirrored into Obsidian

- [Current operation](active/current-operation/current-operation.md): how the implemented application works.
- [Setup and maintenance](active/setup-and-maintenance/setup-and-maintenance.md): install, configure, run and maintain it.

The [project-wide subsystem map](active/setup-and-maintenance/subsystem-map.md) defines source ownership and what subsystem replacements must preserve.

Only `docs/active/` is mirrored under Self documentation in the private vault.
The [Scarecrow connection guide](active/setup-and-maintenance/obsidian-connection.md) covers optional read-only model access to the mirror through a local Obsidian plugin.

## Development — outside Obsidian

Start with the [Development index](development/development-index.md).

- [Experiments](development/experiments/experiment-index.md): recorded tests and investigations, not current configuration.
- [Reports extracted from Active guides](development/experiments/active-guide-reports-2026-11-12/report-index.md): prior verification runs and rollout notes.
- [History](development/history/history-index.md): baselines and retired documents.
- [Ideas](development/ideas/ideas-guide.md): discussion-only proposals; saving an idea does not authorize implementation.

The active guides may cite development evidence, but those cited files are not
copied into the vault. See [the saved baseline](development/history/baseline.md)
for recovery to the historical checkpoint, not the current code's behavior.

Keep current instructions, supported migrations and known limitations in Active. Put dated test outcomes and measurements in Experiments, retired descriptions and audits in History, and unapproved proposals in Ideas. Maintenance commands may stay in Active; their recorded results belong in Development.

The project root keeps `README.md` for repository navigation. Other indexes use descriptive filenames. Active section indexes match their folder name (`current-operation/current-operation.md` and `setup-and-maintenance/setup-and-maintenance.md`); the vault links these from Self documentation.
