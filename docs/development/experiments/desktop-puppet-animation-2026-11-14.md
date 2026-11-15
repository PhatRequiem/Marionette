# Desktop puppet animation history and verification — 2026-11-14

This report records the animation work through `807f235e8764e106fe09f3a27e579e1a30dee4da`. It consolidates the design decisions from the authoring session, preserved preview files and Git history. It is historical evidence, not a new runtime configuration or a verbatim conversation transcript. Current commands and behavior belong in the [desktop puppet guide](../../active/current-operation/desktop-puppet.md).

The result is a standalone native Qt Quick/Wayland visual companion. It has randomized idle poses, a blink restricted to the tucked-leg pose, gentle head/body/arm movement, and a click-triggered giggle that returns to idle. It does not connect to Marionette's chat, memories, model or desktop-reading tools. This work changed no model, sampling, memory-storage or diagnostic-retention settings.

## Where the evidence lives

| Material | Location and retention |
|---|---|
| Current source, sprite atlases and tests | `src/desktop-puppet/` and `tests/desktop-puppet/`, committed to Git |
| Current operation and dependencies | [Active guide](../../active/current-operation/desktop-puppet.md) and [licenses](../../active/setup-and-maintenance/licenses.md), committed and mirrored into Obsidian |
| Historical decisions and results | This dated report, committed under Development and excluded from the Obsidian mirror |
| Local visual archive | `visual design/archive/desktop-puppet-animation-2026-11-14/`, excluded from Git |
| Fresh raw test output | `data/conversations/development/desktop-puppet/2026-11-14/archive-verification-qt.log`, private and excluded from Git |

The visual archive contains **689 files, totaling 231,192,404 bytes**, plus its generated index and manifest: 48 authoring previews, 27 imagegen source images, 582 working frames/atlases/sequence lists/authoring helpers, seven user-provided references, and 25 fresh offscreen QA captures. Copies were checked against their sources with SHA-256. Original files were left in place.

Start at the local archive's `archive-index.md`. `manifest.json` gives each retained file's relative path, source, byte count and SHA-256. Its SHA-256 at archival completion is `4354fafdda55d94562039440f7f31e86f494eef2ac56091143cef7069076f2d0`. It also records the verification-log hash. The archive preserves all available files in the inventoried session preview/generation directories and the explicitly selected animation working folders; it is not a claim that every transient render ever produced survived.

The archive includes the supplied movement recording and six image references. Live desktop screenshots, personal application databases, credentials and unrelated visual-design files were excluded. The remote Tenor reference was not downloaded into the archive. Historical authoring helpers were copied as evidence, not executed or promoted to supported setup commands; some still refer to their original temporary paths.

The report and current implementation can be retrieved from Git. Replaying the older visual experiments on another machine also requires transferring the local archive separately. The archive is on the same machine, not an independent backup. Raw logs under `data/conversations/` are subject to the project's memory-reset scope; the dated result summary remains in this report.

## Design and motion decisions

The following stages are ordered by the recorded design decisions. Early preview frame numbers belong to their particular revision and must not be confused with the final native atlas IDs.

| Stage | Decision and outcome | Representative archived previews |
|---|---|---|
| Puppet appearance | Keep the purple puppet, cyan eyes and joints; remove strings, the wooden crossbar and cyan/blue hat decoration. | Early prototype preview; original `puppet.png`, subsequently archived as described below |
| Actual limb movement | Replace whole-character swaying with drawn arm and leg changes and a blink. Use the supplied movement recording as front-facing motion reference. | `marionette-puppet-preview.gif` |
| Pose construction | Build two six-frame transitions from the supplied poses, combine them, then introduce bobbing holds. Correct an unwanted reversal. | `marionette-six-frame-transition.gif`, `marionette-next-transition.gif`, `marionette-combined-transition.gif`, `marionette-forward-bob.gif` |
| Longer mapped sequence | Add bobbing and eye opening. Explore arm movement; remove an unwanted lowering/bob addition. Correct frame 30's wrist orientation to match frame 29. | `marionette-24-frame-forward.gif`, `marionette-30-frame-map.png`, `marionette-30-wrists-like29.gif` |
| Return path and alignment | Work backward through the earlier transition with open eyes, extend the return, and correct apparent forward/backward size changes. | `marionette-36-frame-open-eyes.gif`, `marionette-36-aligned.gif`, `marionette-42-aligned.gif` |
| Randomized idle | Alternate between one leg down and both legs tucked, with variable holds rather than a fixed repeating full sequence. Permit blinking only while tucked. | `marionette-random-poses.html` |
| Face and neck continuity | Add intermediate blink frames; stabilize eye placement; introduce small head movement around the neck. A stronger connected-neck revision was rejected. Restore the gentler version and correct the body/collar offset between poses. | `marionette-smooth-blink.html`, `marionette-steady-eyes.html`, `marionette-gentle-head-motion.html`, `marionette-connected-neck.html`, **`marionette-aligned-body-motion.html`** |
| First kick branch | Try a 12-frame add-on restricted to the leg-down pose. Several rigged/warped versions were rejected as sloppy, with the left leg bending the wrong way. Refine the reference to alternating legs, each folding backward in turn. | `marionette-random-flutter.html`, `marionette-pointed-knee-kick.html`, `marionette-reference-knee-kick.html`, direction/fold/alternating variants |
| Kick cleanup and rollback | Inspect individual frames and repair leg artifacts. A redrawn kick was preferred, but the user subsequently returned to the earlier aligned idle baseline. This branch was not installed in the final native player. | `kick-frames-leg-detail.png`, `kick-repaired-frames.png`, `redrawn-kick-frames.png`, `marionette-redrawn-kick.gif` |
| New six-panel leg swap | Keep the upper body in pose 36. Use global poses 34, 32, 24 to bring the left leg up, and 6, 4, 2 to bring the right leg down. Preview forward and reverse. | `baseline-pose-transitions.png`, `six-panel-leg-swap.png`, `six-panel-kick-forward-reverse.gif` |
| Choose the shorter kick | First remove panel 3; then select panels **1 → 2 → 4 → 5**, followed by the reverse path. These are local panel numbers, not global pose IDs. | `kick-without-frame3.gif`, **`kick-1245-forward-reverse.gif`** |
| Hands to belly | Bring the arms inward once, reaching the belly by the later kick poses. Keep the hands there through the kick instead of repeatedly opening them. | `belly-hold-arm-section.png`, `belly-arms-in-only.gif`, `marionette-belly-hold-kick.html` |
| Giggle expression and shoulders | Close the eyes and open the mouth as the hands move in, then add small shoulder pulses. Reverse the hands/expression to return to rest. This was selected as the giggle animation. | `marionette-giggling-kick.html`, `marionette-giggling-shoulders.html`, **`marionette-giggle-and-reset.html`** |
| Native integration | Embed the selected idle and giggle atlases in the desktop player. Click requests the giggle; a tucked pose lowers first. Fix scaling/clipping and shoulder-band rendering seams. | Commit `46549a7`; local `working-files/marionette-native-approved/` |
| Less rigid idle arms | Add continuous arm lift/settle with elbow-to-wrist delay and different left/right phases. Ease the motion out/in around the giggle. Check for folded or disconnected rendering bands and reduce unnecessary drawing subdivisions. | Commit **`807f235`**; `working-files/marionette-arm-motion/` and fresh `qa/native-807f235/` |

The old kick branches are preserved for comparison, not selected behavior. In particular, the final app does not randomly run those 12-frame kicks. The selected short kick is part of the click-triggered giggle.

## Frame-number crosswalk at the archived checkpoint

### Native idle atlas

`assets/puppet-idle.png` has six columns and seven rows of 256-pixel cells, numbered from 1. The current idle player uses only the following groups:

| Group | IDs and use |
|---|---|
| One leg down | Pose **36** |
| Both legs tucked | Pose **24** |
| Tuck transition | **36 → 35 → 34 → 33 → 32 → 31 → 24**, 140 ms per step |
| Lower transition | Reverse of the tuck path, 140 ms per step |
| Blink | **24 → 37 → 38 → 39 → 40 → 41 → 42 → 41 → 40 → 39 → 38 → 37 → 24**, only when tucked; 35 ms closing and 55 ms reopening steps |

IDs 37–42 in the final atlas are the smoother blink frames. Earlier 42-frame GIF revisions used their own sequence numbering; their tail frames should not be substituted for the final blink group. The archived HTML baseline and current JavaScript resolve this ambiguity.

### Native giggle atlas

`assets/puppet-giggle.png` has four columns and two rows of 512-pixel cells. Seven cells are used, numbered from **0** in the renderer. The eighth cell is unused.

| Atlas cell | Selected local kick panel | Arms and expression |
|---|---|---|
| 0 | 1 | Arms out; eyes open, mouth closed |
| 1 | 2 | Hands moving inward; eyes partway closed, mouth opening |
| 2 | 4 | Hands at belly; giggle expression |
| 3 | 5 | Hands settled at belly; giggle expression |
| 4 | 4 | Hands remain at belly; giggle expression |
| 5 | 2 | Hands remain at belly; giggle expression |
| 6 | 1 | Hands remain at belly; giggle expression |

The 3,500 ms timeline is:

- Cell 0 holds 480 ms; cells 1 and 2 take 120 ms each.
- Kicking starts with cell 3 for 120 ms, followed by cells `4,5,6,5,4,3,4,5,6,5,4,3`, each for 120 ms.
- At 2,280 ms, reset through cell 2 for 160 ms and cell 1 for 160 ms.
- Cell 0 holds for the final 900 ms before idle resumes.

The head/idle-arm movement fades during the opening and final holds. The hands-on-belly portion keeps the approved kick, face and shoulder pulses. This is a drawn-sprite animation with local deformation, not a fully articulated skeletal character or a 3D model.

Four identified imagegen sources in `generated-sources/` are especially useful for tracing the giggle: `exec-f28a84c6-8dd6-420e-8421-cf1c989ace96.png` (six-panel leg swap), `exec-8d4521fd-c3d1-405c-9136-3ded6a4b2af1.png` (arms moving to belly), `exec-b42d4c5a-ed71-4e16-81e4-ef9aa2a3e8db.png` (giggle face states), and `exec-1bccfd3b-b281-4f30-9566-40e0f8c21fa1.png` (the earlier redrawn kick, later superseded). Other generation files retain their original names without inventing a per-image approval status.

## Git checkpoints

| Commit | Local date/time, America/New_York | Recorded change |
|---|---|---|
| `7b31d7b` | 2026-11-14 17:17:46 | Standalone desktop puppet prototype |
| `36ddbc2` | 2026-11-14 17:23:20 | Drawn limbs and blinking |
| `414d77d` | 2026-11-14 17:27:15 | Reference-inspired hover gestures |
| `46549a7` | 2026-11-14 20:40:05 | Approved idle and giggle integrated into native player |
| `807f235` | 2026-11-14 20:53:05 | Continuous idle arm motion |

The latest implementation was pushed and its remote commit verified. Historical source belongs in these commits rather than duplicate old application trees. Inspect with `git show <commit>:<path>`; compare in a separate checkout if needed, preserving later work and private data. `baseline-v4` remains the older application baseline and was not moved by this visual work.

## Verification evidence and limits

The archived implementation was built with the documented Qt 6.12/GCC 16/Layer Shell Qt environment. No additional runtime dependency was introduced. The two embedded sprite hashes match the [Active guide](../../active/current-operation/desktop-puppet.md#current-idle-and-giggle-assets).

Earlier native checks and live desktop captures established that the overlay displayed the intended transparent character on this Hyprland host. Offscreen captures were inspected for body/neck continuity, the giggle/reset poses, shoulder seams, and both ends of the idle arm movement. This records those observations, not proof of perfect animation quality.

During archival, `desktop-puppet.sh test` was run again against the unchanged implementation, with captures written directly into the archive. Qt Test reported **5 passed, 0 failed** in 6,087 ms: three test methods plus initialization and cleanup. The three methods cover idle-arm deformation bounds and visible wrist displacement; randomized pose/blink/giggle state rules; and real-QML interactions, pause/resume, sprite rendering, dragging, input regions, synthetic Danish translation and window close. Twenty-five offscreen PNG captures and the complete console output were retained in the locations above.

Offscreen Qt warns that native window masks are unsupported. Those tests validate the requested input region, not compositor click-through. The archive run did not restart the desktop puppet, change main chat/Discord, or generate model responses. No long-session reliability test, other-compositor test, controlled performance benchmark, or animation test under sustained inference load is claimed. The user may still refine the visual motion.

## Documentation mirror completion

The supported `scripts/native-linux/sync-conversation-vault.sh` command completed successfully. All **24 Active documentation files** in the resulting mirror matched their source bytes, including the puppet guide. The Current operation index contains the puppet-guide link. The Development report and visual archive were verified absent from the mirror, and existing Annotations and Obsidian settings/plugin files retained their hashes.

The private receipt is `data/conversations/development/desktop-puppet/2026-11-14/archive-and-mirror-verification.json`; it also records the successful archive checksum audit and raw-test-log hash. The mirror is a generated view, not another authoritative copy or backup; current procedures remain in the [vault guide](../../active/setup-and-maintenance/conversation-vault.md).

## Later asset retirement and frame audit

The user chose to keep the selected animation after an attempted original-doll redraw. The redraws and expression experiment were not installed; the idle/giggle atlases, QML renderer and motion code remain unchanged from the selected implementation.

The user then identified `src/desktop-puppet/assets/puppet.png` and `puppet-hover.png` as older artwork that no longer matches the current character and requested archival. Both were moved unchanged into local `visual design/archive/retired-puppet-artwork-2026-11-14/`, with a README and manifest. Their original paths remain recoverable from Git commit `04a375c60f31c3113bc1c8277abaaa40d5c10424`. Neither file was referenced by Qt resources or the renderer. The build passed after their removal, and the two active atlas hashes still match the Active guide.

| Retired file | SHA-256 |
|---|---|
| `puppet.png` | `9c94a75f7ebf6f91a06af6b256207f93685bc8739fa8f1a599fd260f4ec9d8f7` |
| `puppet-hover.png` | `f447aa9aacf712d9e75dfa074cbd08196c3bba405bcf1d7558aa2f7dc4e8b72b` |

The historical archive and its existing `~/Marionette Archives/animation-raw-backup-2026-11-14_21-43-29/` tar backup were each checked against all 689 original manifest entries: no checksum mismatches. Historical single frames include earlier revisions and higher-resolution authoring PNGs, so faithful backup does not imply every single frame matches the current runtime pose. The final archived `marionette-body-aligned/atlas.webp` and `marionette-giggle/atlas.webp` were decoded and compared with the native PNG assets: both had identical RGBA pixel hashes.

To make the current set unambiguous, local `visual design/archive/current-animation-frames-2026-11-14/` contains the exact two runtime atlases, matching renderer/motion files, and 20 individual active-pose PNGs. All 13 idle/transition/blink exports and seven giggle exports were verified pixel-for-pixel against their atlas cell rectangles. No resizing or new artwork was applied. Runtime deformation is separate from these raw base poses; the README and manifest explain the numbering and source sizes. The original 691-file historical archive was not modified.

Both new local archive folders were backed up to `~/Marionette Archives/animation-assets-backup-2026-11-14_22-13/retired-art-and-current-frames.tar.gz`. A temporary-directory restore verified all **31 files** against their source hashes. Tar SHA-256: `075fec4640cfde3c2c062f42b2d5e7bba924db0b0670deb87fde0941c141bd9c`. `verification.json` and `SHA256SUMS` sit beside it. This is a same-drive backup, not protection from drive failure. The maintained Active guide was updated and its Obsidian mirror refreshed; no personal-data or animation behavior change was made.
