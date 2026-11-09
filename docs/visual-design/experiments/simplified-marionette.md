# Simplified porcelain marionette: Blender model and renders

This separate experiment interprets `visual design/simple character sheet.png`
as editable three-dimensional geometry. The simplified sheet is the reference:
six broad pigtail clumps with brown-to-pink tips, a smooth scalp and six fringe
panels, simple bows, a three-button corset, and two clean skirt tiers. Hands have
continuous fingers instead of separate knuckle joints. The original detailed
[marionette experiment](porcelain-marionette.md) and its outputs remain separate.

## Rebuild and open

Use the existing system Blender installation from the checkout root:

```bash
ALSOFT_DRIVERS=null blender -b -noaudio --factory-startup -t 12 \
  --python scripts/visual-design/render-simplified-marionette.py -- --views
blender data/visual-design/simplified-marionette/simplified-marionette.blend
```

No add-ons, downloaded assets, hosted services or new packages are required.
The interpretation is encoded in the script; rebuilding does not read the
reference image. The reference remains an existing, untracked user input.
All colors and markings use Blender materials or geometry, with no external
texture dependencies.

Outputs under the Git-ignored `data/visual-design/simplified-marionette/`:

- `simplified-marionette.blend`: editable scene, with the hero camera active.
- `simplified-marionette.png`: 1600 × 2000 hero render.
- `simplified-marionette-front.png`, `-side.png`, `-back.png`: matching
  orthographic inspection renders, created by `--views`.

The scene includes five cameras: Hero, Front, Side, Back and Face detail.
Named collections separate the body, face, hair, clothes and studio. Hair
clumps retain subdivision control meshes; hands and feet are unified meshes.
The default render uses CPU Cycles, 64 samples and denoising. `ALSOFT_DRIVERS=null` and `-noaudio`
avoid desktop audio connections and shutdown hangs during headless rendering.

For a quick preview:

```bash
ALSOFT_DRIVERS=null blender -b -noaudio --factory-startup -t 12 \
  --python scripts/visual-design/render-simplified-marionette.py -- --preview
```

`--preview` saves the scene at final settings, then renders at 40% resolution
with 16 samples. It can be combined with `--views`. `--resolution N` sets
portrait width; height is 1.25 times width. `--samples N` changes final samples.
`--output DIRECTORY` chooses another output folder. Rebuilding replaces files
with the same names; choose a new output directory to preserve manual edits.
Generated scenes, renders, logs and Blender backups stay local. The script and
this guide are the versioned, reproducible deliverables.

To save a build log, first create the output directory, then redirect output:

```bash
mkdir -p data/visual-design/simplified-marionette
ALSOFT_DRIVERS=null blender -b -noaudio --factory-startup -t 12 \
  --python scripts/visual-design/render-simplified-marionette.py -- --views \
  > data/visual-design/simplified-marionette/build.log 2>&1
```

## Scope and validation

This is a static, stylized interpretation, not an exact reconstruction of the
sheet. It has no armature, animation, skinning, production retopology,
engineered joint mechanisms or printability validation. The visible ball joints
describe the design; they are not verified physical mechanisms. It does not
integrate an avatar into terminal chat.

Built with the installed Blender 5.2.2 LTS (`d13f752e3b9c`), bundled Python and
CPU Cycles. The installed package's license inventory includes GPL-2.0-or-later,
GPL-3.0-or-later and bundled component licenses; see the environment discussion
in the [original experiment](porcelain-marionette.md#environment-and-validation).
Blender remains an optional experiment tool, not an active application dependency.

Validation includes Python compilation, building the saved scene, rendering and
visually inspecting the hero/front/side/back images, and reopening the saved
scene to render the face-detail camera. No real profiles, memories or
conversations are used.
