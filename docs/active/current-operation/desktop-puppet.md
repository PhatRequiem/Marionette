# Desktop puppet prototype

A small standalone C++/Qt Quick visual companion using the approved purple puppet design. The current transparent artwork has no strings, wooden crossbar or cyan hat symbol; cyan eyes and joints remain. The app is an optional visual prototype, not a connection to Marionette's conversation engine. Greeting text is scripted. No chat, model, memory, screen-reading, application control or autonomous behavior is enabled.

## Run from this checkout

```bash
./scripts/native-linux/desktop-puppet.sh build
./scripts/native-linux/desktop-puppet.sh background
./scripts/native-linux/desktop-puppet.sh status
./scripts/native-linux/desktop-puppet.sh stop
```

For foreground operation, use `./scripts/native-linux/desktop-puppet.sh start` (Ctrl+C stops it). `preview` opens the same character in an opaque preview window for development. Close exits either mode. The background command creates a transient user systemd service, `marionette-puppet.service`; it does not enable login autostart. View startup errors with `journalctl --user -u marionette-puppet.service`. This is process stderr only, not a conversation/diagnostic recorder. Existing chat launch commands and the RAM recorder policy are unchanged.

Build after changing source or assets; stop a running preview before rebuilding. Background start fails if its service is already running; the app also uses a runtime lock to prevent duplicate desktop instances. Stop/status refer to the one user service, so do not launch separate checkouts under that service name concurrently.

## Interaction

| Action | Result |
|---|---|
| Drag the character | Move within her current monitor |
| Click the character | Play the approved giggle and return to idle, plus a brief scripted greeting |
| Pause / Resume or Space | Freeze/resume poses, head motion, hover and giggle |
| Help or `?` | Toggle shortcut help |
| Close, Q or Escape | Exit the preview |

Keyboard shortcuts apply when the companion has keyboard focus. Idle alternates between one leg down (pose 36) and both legs tucked (pose 24), using the approved aligned transitions. Random holds last 2–7 seconds, with a 65% chance of swapping at each hold boundary; a prolonged hold eventually forces a swap. The smoother blink can run only while her legs are tucked. Gentle head movement pivots at the neck, with continuous vertical bobbing. During both idle poses, her arms lift and settle on a roughly 3.7-second cycle: the elbows lead the wrists, and the two sides are slightly out of phase. The connected artwork bends around the arms while the neck, bodice and legs retain their existing motion. These are drawn sprite poses, not a skeletal rig.

Clicking requests the approved 3.5-second giggle: hands move to her belly as her eyes close and mouth opens, her shoulders bounce, and her feet alternate through the selected 1 → 2 → 4 → 5 → 4 → 2 leg sequence. Her hands and expression then reverse back to rest. If she is tucked up, the current clip finishes and she lowers one leg before giggling. Repeated clicks during a giggle do not restart it. Giggles are click-triggered, not randomly scheduled. Pausing freezes the animation; clicks while paused do not queue a giggle. Position is temporary and resets on launch. The overlay occupies one monitor; dragging between monitors is not implemented.

The transparent Wayland layer uses an input region limited to the character/control rectangle (including space for the help bubble). Outside that rectangle clicks pass through; transparent gaps inside the rectangle still intercept clicks. It does not reserve desktop workspace. Its top layer remains above ordinary windows; fullscreen behavior follows compositor policy. Removing the selected output closes the companion.

## Setup and rebuild

Source: `src/desktop-puppet/`; launcher: `scripts/native-linux/desktop-puppet.sh`; generated objects and executable: ignored `runtime/desktop-puppet/`; UI checks: `tests/desktop-puppet/`. Nothing is installed globally. This follows the repository's run-from-checkout policy rather than distributing an Arch package at this prototype stage.

Requirements are the distribution packages `gcc`, `make`, `qt6-base`, `qt6-declarative`, `qt6-wayland`, and `layer-shell-qt`. On Omarchy, missing packages can be installed with:

```bash
omarchy pkg add gcc make qt6-base qt6-declarative qt6-wayland layer-shell-qt
```

Verified build versions on 2026-11-14: GCC `16.2.1+r23+gd564253eb6c8-1`, Make `4.4.1-3`, Qt Base `6.12.0-3`, Qt Declarative `6.12.0-2`, Qt Wayland `6.12.0-1`, Layer Shell Qt `6.8.1-1`. These are rolling-distribution packages, not a frozen OS image. Rebuild and repeat the checks after Qt/Layer Shell Qt upgrades. There are no model downloads, pip/npm environments, external asset downloads or hosted runtime dependencies. The two PNG atlases and animation code are embedded by Qt's resource compiler; the authoring previews are not required at runtime.

Desktop mode requires Wayland with `wlr-layer-shell` and is verified on this Hyprland host. It is not a generic GNOME/X11 implementation. Qt Quick renders the image and controls; Layer Shell Qt handles desktop overlay placement. Theme accent/rounding and language are read from Omarchy without changing desktop configuration. English and Danish strings are provided; other languages fall back to English.

## Checks and remaining limits

```bash
./scripts/native-linux/desktop-puppet.sh test
QT_QPA_PLATFORMTHEME=basic QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  runtime/desktop-puppet/marionette-puppet --preview --smoke /tmp/puppet-preview.png
```

The Qt tests load the actual QML and check greeting, pause/resume, complete giggle/reset playback, distinct rendering of the active idle/blink poses and seven giggle poses, dragging, input-region bounds, live Danish translation from a synthetic temporary language file, and window close. A deterministic animation simulation checks randomized idle states, blink gating, queued giggles during a blink, lowering before a giggle, and return to idle after repeated clicks. Arm deformation checks cover visible wrist movement, unchanged neck/body/leg anchors, and positive strip heights across multiple motion cycles. The optional captures include both ends of the arm wave in each idle pose. Set `PUPPET_TEST_CAPTURES=/tmp/puppet-frames` when running the test command to retain synthetic offscreen renders.

The offscreen backend warns that native input masks are unsupported: this checks the requested region, not compositor click-through. Live desktop verification separately checks transparent rendering and placement. Long-session behavior, other compositors, monitor hotplug and performance under inference load remain unverified.

The companion deliberately has no interface to personal data. A future local event adapter can drive animations without coupling the renderer to conversation storage, but that adapter is not implemented.

## Artwork provenance

`src/desktop-puppet/assets/puppet.png` is a built-in imagegen edit of the puppet concept created in this chat. Final edit prompt: remove all strings and the wooden crossbar, remove cyan/blue hat decoration and loose particles, preserve the face, cyan eyes/joints, purple hair/hat/bow, purple-and-gold outfit and raised-hand pose; restore clothing underneath strings and render a centered full-body transparent cutout. No external character/model assets were downloaded.

SHA-256: `9c94a75f7ebf6f91a06af6b256207f93685bc8739fa8f1a599fd260f4ec9d8f7`.

### Current idle and giggle assets

The current atlases preserve the approved artwork from the local animation previews, decoded losslessly from their embedded WebP images into PNG so no Qt WebP plugin is needed. They were authored in this chat using imagegen and compositing of the approved poses. The private reference recording and conversation files are not included in the repository. No external character/model assets were downloaded.

| Asset | Layout | SHA-256 |
|---|---|---|
| `assets/puppet-idle.png` | 6 columns × 7 rows, 256-pixel cells; original numbered poses 1–42 | `b645ada0122d0df8b4f9adc9de68670b246d9bb46c7f55ae579f0e70b8cb29bf` |
| `assets/puppet-giggle.png` | 4 columns × 2 rows, 512-pixel cells; seven poses and one unused cell | `71a510ea2ae38b2ad6050bcbe8fa2cfc680c7c4a84f22e7dc9c9c019b95aae11` |

`PuppetMotion.js` owns pose selection and timing; `PuppetAnimation.qml` draws the atlases, neck-pivot head movement and tapered shoulder bounce. Both use one pauseable clock. The shoulder deformation uses shared integer pixel boundaries at source resolution before desktop scaling to avoid seams between bands. The whole canvas carries the continuous hover offset.

Idle uses pose 36, poses 35–31 leading to 24, and the reverse path, at 140 ms per transition frame. The blink uses 24 → 37–42 → 41–37 → 24, with 35 ms closing and 55 ms opening steps. The giggle atlas cells are: 0 arms out; 1 hands moving inward with half-closed eyes; 2 hands at belly; 3–6 settled giggle with the selected leg positions. Its full timing is recorded in `giggleTimeline`; the final two transitional cells reopen the eyes and reset the hands. Head and idle arm motion ease out during the opening hold and resume during the final resting hold; body bobbing continues without resetting its clock. The hands-on-belly part of the giggle keeps its approved timing and shoulder bounce.

`assets/puppet-hover.png` remains as the earlier six-frame design reference and is no longer embedded or played. The reference recording's full turns and inverted flourish are not implemented; those require additional side/back views.

The dated [animation development report](../../development/experiments/desktop-puppet-animation-2026-11-14.md) records the design decisions, superseded experiments and verification evidence. It also indexes the local visual archive. Development reports and archived previews stay outside the Obsidian mirror; this guide describes current behavior.
