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
| Click the character | Replay the arm/leg gesture and blink, plus a brief scripted greeting |
| Pause / Resume or Space | Freeze/resume the current animation frame |
| Help or `?` | Toggle shortcut help |
| Close, Q or Escape | Exit the preview |

Keyboard shortcuts apply when the companion has keyboard focus. Her animation uses six transparent sprite frames: arm/hand poses, knee/foot movement, half-closed eyes and a closed-eye blink. The motion lasts 690 ms followed by a 2.3-second resting pose. The closed-eye frame lasts 110 ms. This is a short frame-based animation, not a skeletal rig; no whole-image sway remains. Clicking replays the gesture when animation is not paused. Position is temporary and resets on launch. The overlay occupies one monitor; dragging between monitors is not implemented.

The transparent Wayland layer uses an input region limited to the character/control rectangle (including space for the help bubble). Outside that rectangle clicks pass through; transparent gaps inside the rectangle still intercept clicks. It does not reserve desktop workspace. Its top layer remains above ordinary windows; fullscreen behavior follows compositor policy. Removing the selected output closes the companion.

## Setup and rebuild

Source: `src/desktop-puppet/`; launcher: `scripts/native-linux/desktop-puppet.sh`; generated objects and executable: ignored `runtime/desktop-puppet/`; UI checks: `tests/desktop-puppet/`. Nothing is installed globally. This follows the repository's run-from-checkout policy rather than distributing an Arch package at this prototype stage.

Requirements are the distribution packages `gcc`, `make`, `qt6-base`, `qt6-declarative`, `qt6-wayland`, and `layer-shell-qt`. On Omarchy, missing packages can be installed with:

```bash
omarchy pkg add gcc make qt6-base qt6-declarative qt6-wayland layer-shell-qt
```

Verified build versions on 2026-11-14: GCC `16.2.1+r23+gd564253eb6c8-1`, Make `4.4.1-3`, Qt Base `6.12.0-3`, Qt Declarative `6.12.0-2`, Qt Wayland `6.12.0-1`, Layer Shell Qt `6.8.1-1`. These are rolling-distribution packages, not a frozen OS image. Rebuild and repeat the checks after Qt/Layer Shell Qt upgrades. There are no model downloads, pip/npm environments, external asset downloads or hosted runtime dependencies. The PNG is embedded by Qt's resource compiler.

Desktop mode requires Wayland with `wlr-layer-shell` and is verified on this Hyprland host. It is not a generic GNOME/X11 implementation. Qt Quick renders the image and controls; Layer Shell Qt handles desktop overlay placement. Theme accent/rounding and language are read from Omarchy without changing desktop configuration. English and Danish strings are provided; other languages fall back to English.

## Checks and remaining limits

```bash
./scripts/native-linux/desktop-puppet.sh test
QT_QPA_PLATFORMTHEME=basic QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  runtime/desktop-puppet/marionette-puppet --preview --smoke /tmp/puppet-preview.png
```

The Qt test loads the actual QML, checks greeting, pause/resume (including frame freeze), gesture progression through the blink back to rest, distinct rendering of all six frames, dragging, input-region bounds, live Danish translation from a synthetic temporary language file, image rendering and window close. The offscreen backend warns that native input masks are unsupported: this checks the requested region, not compositor click-through. Live desktop verification separately confirmed transparent rendering over applications and wallpaper, readable controls and the Help panel. Long-session behavior, other compositors, monitor hotplug and performance under inference load remain unverified.

The companion deliberately has no interface to personal data. A future local event adapter can drive animations without coupling the renderer to conversation storage, but that adapter is not implemented.

## Artwork provenance

`src/desktop-puppet/assets/puppet.png` is a built-in imagegen edit of the puppet concept created in this chat. Final edit prompt: remove all strings and the wooden crossbar, remove cyan/blue hat decoration and loose particles, preserve the face, cyan eyes/joints, purple hair/hat/bow, purple-and-gold outfit and raised-hand pose; restore clothing underneath strings and render a centered full-body transparent cutout. No external character/model assets were downloaded.

SHA-256: `9c94a75f7ebf6f91a06af6b256207f93685bc8739fa8f1a599fd260f4ec9d8f7`.

### Arm, leg and blink animation

`assets/puppet-motion.png` is a built-in imagegen edit derived from `puppet.png`, followed by a transparent-background cleanup pass. Prompt: preserve the plain purple hat, outfit, cyan eyes/joints and character identity; create a three-column/two-row sheet of six equally sized, aligned full-body poses, progressively raising/lowering the hand, bending/straightening the legs, and briefly closing both eyes. Remove all background haze, strings, crossbar, particles and labels. The original concept remains a design reference; runtime displays the new sheet.

The sheet is 1536 × 1024, with six 512 × 512 cells. SHA-256: `a1613dea90d22061ba6600261f37f1a3010a82664d1a2a06e10147d48ae82637`. `PuppetAnimation.qml` owns frame selection and timing; it requires no new dependency or model service. The imagegen tool was used during authoring only.

Animation verification on 2026-11-14: the QML interaction test passed with all six frames rendered and checked for distinct output; pause froze frame selection, resume advanced, and the replay reached the closed-eye frame then returned to rest. Rendered open/closed-eye poses were visually inspected for actual arm/leg changes and clean transparency. Set `PUPPET_TEST_CAPTURES=/tmp/puppet-frames` when running `desktop-puppet.sh test` to retain those synthetic offscreen renders.
