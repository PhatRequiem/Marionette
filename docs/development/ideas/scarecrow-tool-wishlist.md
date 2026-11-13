# Scarecrow tool wishlist

Date: 2026-11-13

**Status: idea only — not approved or implemented**

Potential additions collected from our Obsidian connector review. Saving this list does not authorize implementation, installation, downloads or experiments. These are capability ideas, not a commitment to expose a separate model tool for every item. Current behavior belongs in the [Scarecrow guide](../../active/setup-and-maintenance/obsidian-connection.md).

Scarecrow already supports immediate folder listing, basic text search, whole-note and heading reads, metadata inspection, tag counts, outgoing links/backlinks, and opening existing notes. The items below extend that foundation.

## Read-only additions

| Capability | Purpose | Reference |
|---|---|---|
| Read several notes together | Retrieve a profile, notes and selected conversations in one request. | [MCPVault](https://github.com/bitbonsai/mcpvault) |
| Read specific lines | Retrieve surrounding context for a search hit without reading the full conversation. | [MCPVault](https://github.com/bitbonsai/mcpvault) |
| Resolve names and aliases | Convert a human name into an exact note path; return choices for ambiguous names. | [MCPVault](https://github.com/bitbonsai/mcpvault) |
| Folder tree and vault overview | Understand the hierarchy without repeatedly listing individual folders. | [istefox](https://github.com/istefox/obsidian-mcp-connector) |
| Ranked, typo-tolerant search | Rank stronger matches first and tolerate misspellings. | [Omnisearch](https://github.com/scambier/obsidian-omnisearch), [lstpsche](https://github.com/lstpsche/obsidian-mcp) |
| Advanced search filters | Exact phrases, excluded words and property-value filters. | [Omnisearch](https://github.com/scambier/obsidian-omnisearch), [Cyanheads](https://github.com/cyanheads/obsidian-mcp-server) |
| Recent changes | Find notes added or modified since a chosen time. Distinguish mirror export time from original conversation time. | [istefox](https://github.com/istefox/obsidian-mcp-connector) |
| Active note and open tabs | Understand which note the human is referring to when asking about the current view. | [istefox](https://github.com/istefox/obsidian-mcp-connector) |
| Read Canvas diagrams | Inspect cards and connections in visual maps. | [istefox](https://github.com/istefox/obsidian-mcp-connector) |
| Attachment inventory | List attachments and their referring notes. | [istefox](https://github.com/istefox/obsidian-mcp-connector) |
| Task lookup | Find incomplete checkboxes across notes or folders. | [istefox](https://github.com/istefox/obsidian-mcp-connector) |
| Read periodic notes | Resolve daily or weekly notes by date without guessing filenames. | [Cyanheads](https://github.com/cyanheads/obsidian-mcp-server) |

## Exploring connections

| Capability | Purpose |
|---|---|
| Multi-step link traversal | Explore profile → contact notes → supporting conversations in one request. |
| Find a connection path | Return the actual chain of links connecting two notes. |
| Search connected notes | Search material linked to a chosen starting note. |
| Find shared tags | Discover overlapping topics even without direct links. |
| Vault health checks | Identify broken links, isolated notes and missing metadata. |

References: [Semantic Notes Vault graph tools](https://github.com/aaronsb/obsidian-mcp-plugin/blob/main/docs/tools/graph.md), [Archiver-RAG](https://github.com/FernandoJRR/archiver-rag). Shared tags or link proximity suggest relationships to investigate; they do not prove that claims are equivalent or true.

## Larger retrieval additions

| Capability | Benefit and additional work |
|---|---|
| Local semantic search | Match meaning despite different wording; requires an embedding model and index. |
| Hybrid search | Combine keyword relevance with semantic similarity. |
| Related-passage suggestions | Surface potentially useful passages beyond explicit keyword matches. |
| Graph-aware ranking | Give additional weight to results connected to a selected context note. |
| PDF, document and image text search | Search extracted text/OCR; requires extraction dependencies. |
| Structured queries | Query note properties through controlled Dataview or Bases integration. |

References: [istefox](https://github.com/istefox/obsidian-mcp-connector), [allexcd](https://github.com/allexcd/obsidian-mcp), [DalecB](https://github.com/DalecB/obsidian-semantic-mcp), [Archiver-RAG](https://github.com/FernandoJRR/archiver-rag), [Omnisearch with Text Extractor](https://github.com/scambier/obsidian-omnisearch), [Semantic Notes Vault](https://github.com/aaronsb/obsidian-mcp-plugin). These are documented approaches, not verified Scarecrow integrations. Some upstream documentation describes development versions; recheck releases before adoption.

Any future index needs explicit freshness, reset and deletion handling. Check local resource costs, licenses and shared model availability before choosing dependencies. Keep ordinary keyword retrieval usable if semantic retrieval is unavailable.

## Editing possibilities — separate future authorization

- Targeted paragraph or section edits.
- Add source links to existing notes.
- Update properties and tags.
- Create notes.
- Move or rename notes while preserving links.

References: [Cyanheads](https://github.com/cyanheads/obsidian-mcp-server), [MCPVault](https://github.com/bitbonsai/mcpvault), [Archiver-RAG](https://github.com/FernandoJRR/archiver-rag). Scarecrow remains read-only. Before considering writes, decide which files Marionette owns and how edits interact with generated mirror refreshes; add conflict handling and recoverability to the design.

[Engram Vault](https://getengram.app/blog/obsidian-engram-vault) primarily contributed the browsable conversation mirror and linked hub-page pattern already adopted, rather than a distinct new retrieval tool.

## Suggested order to revisit

1. Name and alias resolution.
2. Ranked search.
3. Reading several notes together.
4. Line-range reads.
5. Multi-step link traversal.

This order is a discussion preference, not an approved work queue. Compare additions using the same representative questions and vault, checking retrieval correctness separately from model answer quality. Preserve the existing decision against application-level request/result byte budgets unless explicitly revisited.
