# Reading the project in Obsidian

Open the existing repository folder as a vault. Documents stay in their original locations; edits are ordinary Git changes. Obsidian is an optional personal editor, not an application dependency. Other Markdown editors remain supported.

## Appearance

In **Settings → Appearance → CSS snippets**, refresh the list and enable **marionette**. The tracked `.obsidian/snippets/marionette.css` provides comfortable line spacing, a bounded reading width, clearer headings, alternating table rows, and file explorer colors for both light and dark themes:

| Color | Meaning |
|---|---|
| Green | Root README and startup guide |
| Blue | Current guides under `docs/` |
| Purple | Discussion-only ideas |
| Amber | Historical experiments |
| Gray | Archived guides |

Folder names remain the authoritative labels; color is an extra navigation cue. Heading colors distinguish heading levels, not document status. Enable **Settings → Editor → Readable line length** to use the snippet's reading width. Disable the snippet to restore the theme's default styling. No community plugin or theme download is required. Personal appearance and workspace settings are ignored by Git; only this shared CSS snippet is tracked.

## Scope and portability

Use ordinary relative Markdown links. Start from [the project overview](../README.md) or [startup instructions](../STARTUP.md). Keep guides, ideas, experiments, and archives in their established folders.

A repository-root vault also includes private files under `data/`. Git ignore rules do not exclude those files from Obsidian. Do not publish or sync the entire vault as public documentation. Application-managed memory stays in place and should be changed through its documented application workflows.

Obsidian 1.14.4 (installed Arch package 1.14.4-2) is proprietary and free to use locally without an account. Sync and Publish are optional paid services; neither is needed here. See [Obsidian's license](https://obsidian.md/license) and [CSS snippet instructions](https://obsidian.md/help/snippets). The project does not install or require Obsidian.
