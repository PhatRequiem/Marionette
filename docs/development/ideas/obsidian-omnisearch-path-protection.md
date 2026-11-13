# Revisit Obsidian Omnisearch without exposing configuration

> Historical: the Cyanheads integration was removed on 2026-11-13. Model vault access is disconnected; the custom plugin is not implemented.

Date: 2026-11-13

**Status: idea only — not approved or implemented**

We may want Omnisearch's relevance ranking, typo tolerance and richer text queries in Marionette's vault connection. It is an additional Obsidian plugin, not embedding-based semantic search. PDF/image text search also depends on extraction support.

## Current constraint

The installed Cyanheads 3.9.0 connector withholds Omnisearch whenever read-path restrictions are configured. Marionette denies `.obsidian/`, which holds application/plugin settings and the Local REST API credential. This restriction does not separate contacts; all mirrored contact collections remain readable. Omnisearch is not installed or exposed. Text and JSONLogic searches work through the existing adapter.

Removing the restriction could expose credentials and settings to model context, diagnostic capture or replies. Cyanheads enforces our read-only mode; the underlying API credential is not itself a read-only credential. Disclosure would not automatically grant the model another execution tool, but a separate client possessing that credential could potentially perform writes through the API. Removing the restriction alone would not install or enable Omnisearch.

## Questions before any future change

- Does a newer Cyanheads release support Omnisearch while enforcing denied paths, including result snippets and metadata?
- Can credentials remain outside model-readable material while retaining reliable protection for configuration files?
- Can an alternative integration provide ranked search without bypassing the existing path and read-only controls?
- Verify excluded content cannot leak through search results, excerpts, metadata or subsequent reads. Check upstream behavior rather than assuming the search index excludes `.obsidian/`.
- Compare retrieval benefit and maintenance cost against the existing text/structured searches before adding dependencies.

Keep the current protection in place. This note authorizes no installation, configuration change or experiment. Revisit only on a separate explicit request.

References: [current connection and limits](../../active/setup-and-maintenance/obsidian-connection.md), [Cyanheads upstream documentation](https://github.com/cyanheads/obsidian-mcp-server).
