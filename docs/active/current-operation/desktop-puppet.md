# Desktop puppet chat

A small C++/Qt Quick desktop chat interface using the approved purple puppet design. Type in green below her and read formatted pink replies in the growing bubble above her. Completed answers reveal quickly, one letter at a time. She keeps her existing idle animation during generation and text reveal; there is no waiting indicator or thinking animation. Only clicking her requests a giggle. The current transparent artwork has no strings, wooden crossbar or cyan hat symbol; cyan eyes and joints remain.

This is a basic interface to the existing local chat engine. Model execution, tools, identity, memory and durable conversations remain in the Python backend. The puppet has no separate model, memory database, screen-reading, application control or autonomous behavior.

## Run from this checkout

Once main chat is ready, the owner can type `/startpuppet` to launch the background 2D interface and `/stoppuppet` to close it without stopping chat. These application commands appear in `/help`; they are local controls, unavailable over Discord. They reuse the launcher below with the current chat's data directory. Build the puppet first, and restart main chat once after adding/updating the command code. Launch acknowledgment means the launcher accepted the request, not that a window has been visually verified; failures point to the existing service status command. `/stoppuppet` controls the background service, not a separately launched foreground preview.

```bash
./scripts/native-linux/chat.sh
# Select a profile and wait for Ready. In another terminal:
./scripts/native-linux/desktop-puppet.sh build
./scripts/native-linux/desktop-puppet.sh background
./scripts/native-linux/desktop-puppet.sh status
./scripts/native-linux/desktop-puppet.sh stop
```

Keep main chat running. Restart it after installing this change so its local connection supports desktop requests. The desktop always resolves the saved owner UUID, even if the main terminal selected another profile. It shares the owner's terminal conversation and contact notes; Discord keeps its separate conversation history. Selecting another terminal profile does not grant that profile the owner's desktop identity.

For foreground operation, use `./scripts/native-linux/desktop-puppet.sh start` (Ctrl+C stops it). `preview` opens the same interface in an opaque preview window for development. Close or `/exit` detaches the puppet and leaves main chat running; `/shutdown` requests the existing orderly backend shutdown. The background command creates a transient user systemd service, `marionette-puppet.service`; it does not enable login autostart. View startup errors with `journalctl --user -u marionette-puppet.service`. Chat payloads are not printed to the puppet's journal; existing backend recorders own them. Existing chat launch commands and the RAM recorder policy are unchanged.

If using `MARIONETTE_DATA_DIR`, pass the same absolute directory to both launchers. Desktop background startup passes it into the service explicitly. The UI reports connection failures; it never starts another model or automatically resends a message. After a disconnect, inspect main chat before retrying because a reply may have been saved even if it was not displayed.

Build after changing source or assets; stop a running preview before rebuilding. Background start fails if its service is already running; the app also uses a runtime lock to prevent duplicate desktop instances. Stop/status refer to the one user service, so do not launch separate checkouts under that service name concurrently.

## Interaction

| Action | Result |
|---|---|
| Drag the character | Move within her current monitor |
| Click the character | Play the approved giggle and return to idle |
| Enter / Send in the input box | Send one message; input and Send remain disabled until the request finishes |
| Shift+Enter | Insert a new line |
| Select / scroll the reply | Copy text or read a long answer; the bubble remains until replaced or dismissed |
| × on the bubble | Dismiss the visible reply, error or help; saved conversations remain |
| Pause / Resume or Space | Freeze/resume poses, head motion, hover and giggle |
| Help or `?` | Toggle shortcut help |
| Close, Q or Escape outside text | Detach the desktop interface |
| Escape while editing/selecting text | Leave text focus without closing |

Keyboard shortcuts apply when the companion has keyboard focus, with Q, Space and ? disabled while text has focus. Replies support Markdown headings, bold, italics, lists, quotes, links and code through Qt's built-in text document. Raw HTML is not interpreted, images become their descriptions, and the renderer does not load message resources or automatically open links. Reply text matches terminal pink (`#FF4FA3`); input text matches terminal green (`#39FF14`). Reasoning remains in the existing diagnostic view.

Each completed answer reveals at roughly 125 letters per second, preserving accents and combined emoji. Formatting is parsed before the reveal so Markdown markers do not flash while typing. This is a local presentation effect after generation completes, not live model-token streaming. The bubble widens for the reply (up to 640 pixels) and grows as text appears (up to 520 pixels and the available space above her). Longer replies scroll; the view follows new lines while revealing and remains selectable/scrollable afterward. Dismissing, resetting or ending the session clears the reveal as well as the reply. The UI retains only the latest bubble and current draft in RAM. A new submission leaves the previous bubble visible until a response arrives. No animation change is triggered by sending, receiving, errors or reset.

Idle alternates between one leg down (pose 36) and both legs tucked (pose 24), using the approved aligned transitions. Random holds last 2–7 seconds, with a 65% chance of swapping at each hold boundary; a prolonged hold eventually forces a swap. The smoother blink can run only while her legs are tucked. Gentle head movement pivots at the neck, with continuous vertical bobbing. During both idle poses, her arms lift and settle on a roughly 3.7-second cycle: the elbows lead the wrists, and the two sides are slightly out of phase. The connected artwork bends around the arms while the neck, bodice and legs retain their existing motion. These are drawn sprite poses, not a skeletal rig.

Clicking requests the approved 3.5-second giggle: hands move to her belly as her eyes close and mouth opens, her shoulders bounce, and her feet alternate through the selected 1 → 2 → 4 → 5 → 4 → 2 leg sequence. Her hands and expression then reverse back to rest. If she is tucked up, the current clip finishes and she lowers one leg before giggling. Repeated clicks during a giggle do not restart it. Giggles are click-triggered, not randomly scheduled. Pausing freezes the animation; clicks while paused do not queue a giggle. Position is temporary and resets on launch. The overlay occupies one monitor; dragging between monitors is not implemented.

The transparent Wayland layer uses separate input rectangles for the character/input/controls and the visible bubble. Empty space beside her still passes clicks through when the bubble is wider; transparent gaps inside each rectangle intercept clicks. It does not reserve desktop workspace. Its top layer remains above ordinary windows; fullscreen behavior follows compositor policy. Removing the selected output closes the companion.

## Local connection and reset

`chatclient.cpp` uses Qt Network's asynchronous `QLocalSocket` against `data/session/chat.sock`. The event loop remains responsive during model generation. Requests are newline-delimited JSON with `source: "desktop"`, `session`, `generation`, and `message`. The private socket checks the peer's Linux UID and rejects client-supplied identity fields. Python resolves the owner and queues the request alongside Discord. Desktop messages use the existing `terminal:<owner UUID>` conversation key and are saved with source `terminal`; transport diagnostics label their route `Desktop`. The terminal still owns the processing loop, so it must stay open.

Replies carry only the completed answer, finish status, timings, session and generation. The client bounds request/reply sizes and connection setup time; it does not impose a short generation timeout. It uses no hosted endpoint or new recorder/helper process. `ChatClient` is separate from QML layout and animation, allowing future UI changes without moving conversation ownership. `ReplyPresentation` handles Markdown and the timed Unicode text reveal with existing Qt GUI/Core APIs, without a new dependency.

The client reads only the small session descriptor and incomplete-reset guard, never profiles or the conversation database. It checks them on a 500 ms timer and immediately before accepting a reply. A reset boundary or new/ended backend session clears the bubble and draft. Old-generation replies are discarded; a successful `/resetmemory` response can acknowledge the new generation. An incomplete reset blocks new desktop messages. Closing the puppet disconnects delivery but does not cancel a backend turn already in progress or erase saved history. Use the existing owner `/cancel` from terminal or Discord to interrupt generation.

## Setup and rebuild

Source: `src/desktop-puppet/`; launcher: `scripts/native-linux/desktop-puppet.sh`; generated objects and executable: ignored `runtime/desktop-puppet/`; UI checks: `tests/desktop-puppet/`. Nothing is installed globally. This follows the repository's run-from-checkout policy rather than distributing an Arch package at this prototype stage.

Requirements are the distribution packages `gcc`, `make`, `qt6-base` (including Qt Network), `qt6-declarative`, `qt6-wayland`, and `layer-shell-qt`. On Omarchy, missing packages can be installed with:

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

The Qt tests load the actual QML and check typing/shortcuts, multiline input, final replies, idle during requests, absence of a waiting bubble, reset/restart clearing, stale replies, failure display, pause/resume, complete giggle playback, rendered poses, dragging, input-region bounds, Danish translation from a synthetic language file, and window close. One test connects the actual native client to Python Conversation/LocalConnection and both real recorders, performs a reset, and sends again. Its model replies are synthetic and all profiles live in an empty temporary directory. Core desktop tests separately verify owner authorization and history sharing when another terminal profile is selected. A deterministic animation simulation checks randomized idle states, blink gating, click-requested giggles and return to idle. Arm checks cover wrist movement and unchanged body anchors. Set `PUPPET_TEST_CAPTURES=/tmp/puppet-frames` to retain synthetic offscreen renders.

The offscreen backend warns that native input masks are unsupported: this checks the requested region, not compositor click-through. Earlier live desktop verification covered transparent rendering and placement. The new chat controls passed native Qt/QML tests, but live compositor focus/click-through remains unverified: the GUI driver could not discover the temporary preview window on this host. Long-session behavior, other compositors, monitor hotplug and performance under inference load remain unverified.

The integration tests establish local transport, UI and reset behavior with synthetic replies. Native presentation checks cover formatted text, Unicode reveal, terminal colors, growing/scrolling bubbles, input regions and dismissal/reset during reveal. They do not establish real-model answer quality or long-session reliability. A dedicated thinking animation, live model-token streaming, older-conversation browsing and a combined/headless backend launcher are future work, not implemented features.

Core command tests verify owner-only puppet controls without inference or history changes. `test_puppet_control.py` uses a temporary shell launcher to check start/stop arguments, data-directory propagation and failures without opening a real desktop window.

## Artwork provenance

The active character artwork is `puppet-idle.png` and `puppet-giggle.png`. The earlier single-pose `puppet.png` and six-frame `puppet-hover.png` were moved out of the source assets at the user's request because their design differs from the selected animation. They are preserved unchanged in local `visual design/archive/retired-puppet-artwork-2026-11-14/`, with source paths and checksums in its manifest. They are also recoverable from Git commit `04a375c60f31c3113bc1c8277abaaa40d5c10424`. Neither was embedded or played; archiving them changes no runtime behavior.

### Current idle and giggle assets

The current atlases preserve the approved artwork from the local animation previews, decoded losslessly from their embedded WebP images into PNG so no Qt WebP plugin is needed. They were authored in this chat using imagegen and compositing of the approved poses. The private reference recording and conversation files are not included in the repository. No external character/model assets were downloaded.

| Asset | Layout | SHA-256 |
|---|---|---|
| `assets/puppet-idle.png` | 6 columns × 7 rows, 256-pixel cells; original numbered poses 1–42 | `b645ada0122d0df8b4f9adc9de68670b246d9bb46c7f55ae579f0e70b8cb29bf` |
| `assets/puppet-giggle.png` | 4 columns × 2 rows, 512-pixel cells; seven poses and one unused cell | `71a510ea2ae38b2ad6050bcbe8fa2cfc680c7c4a84f22e7dc9c9c019b95aae11` |

`PuppetMotion.js` owns pose selection and timing; `PuppetAnimation.qml` draws the atlases, neck-pivot head movement and tapered shoulder bounce. Both use one pauseable clock. The shoulder deformation uses shared integer pixel boundaries at source resolution before desktop scaling to avoid seams between bands. The whole canvas carries the continuous hover offset.

Idle uses pose 36, poses 35–31 leading to 24, and the reverse path, at 140 ms per transition frame. The blink uses 24 → 37–42 → 41–37 → 24, with 35 ms closing and 55 ms opening steps. The giggle atlas cells are: 0 arms out; 1 hands moving inward with half-closed eyes; 2 hands at belly; 3–6 settled giggle with the selected leg positions. Its full timing is recorded in `giggleTimeline`; the final two transitional cells reopen the eyes and reset the hands. Head and idle arm motion ease out during the opening hold and resume during the final resting hold; body bobbing continues without resetting its clock. The hands-on-belly part of the giggle keeps its approved timing and shoulder bounce.

Exact exports of the 20 active base poses are in local `visual design/archive/current-animation-frames-2026-11-14/frames/`: 13 idle/transition/blink PNGs at 256 pixels and seven giggle PNGs at 512 pixels. They were extracted without resizing and verified pixel-for-pixel against the current atlas cells. Head/arm motion, shoulder pulses and hover are added by the renderer, so these base poses are not screenshots of every moment in playback. The pack includes matching atlases, renderer files and a manifest. Historical authoring PNGs can differ because they precede alignment, resizing or WebP packing; the historical final WebP atlases decode to the same pixels as the current PNG atlases.

The reference recording's full turns and inverted flourish are not implemented; those require additional side/back views.

The dated [animation development report](../../development/experiments/desktop-puppet-animation-2026-11-14.md) records the design decisions, superseded experiments and verification evidence. It also indexes the local visual archive. Development reports and archived previews stay outside the Obsidian mirror; this guide describes current behavior.
