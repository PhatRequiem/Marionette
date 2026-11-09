# Porcelain marionette: local Blender render

This experiment interprets the user-provided `visual design/character sheet.png`
as a stylized, three-dimensional porcelain doll. It uses Blender geometry,
materials, lights and cameras entirely locally. No image-to-3D service, credits,
external asset, model weights or Blender add-on is used.

## Rebuild and open

Run from the checkout with Blender installed:

```bash
blender -b --factory-startup --python scripts/visual-design/render-marionette.py
blender data/visual-design/porcelain-marionette.blend
```

The default output is a compressed `.blend` scene and a 1400 × 1680 PNG under
`data/visual-design/`, which is ignored by Git. The script is the versioned source;
generated scenes, previews and Blender backups stay local. The reference images
are existing user inputs and are not added by this experiment. Rebuilding uses
the procedural interpretation encoded in the script, without reading the images.

For a quick inspection:

```bash
blender -b --factory-startup --python scripts/visual-design/render-marionette.py -- --preview
```

`--preview` saves the full-resolution scene, then renders a 45% preview with 16
samples. `--output DIRECTORY`, `--resolution PIXELS` (width), and `--samples N`
can be passed after `--`. The default final render uses 64 Cycles samples and
denoising. Rendering is CPU-based; a GPU runtime is not required. The script uses
a fixed random seed for repeatable curl placement. Run it in a new output
directory to preserve a manually edited scene: rebuilding replaces its outputs.

The delivered hero image uses 1800 × 2160 pixels and 96 samples:

```bash
blender -b --factory-startup --python scripts/visual-design/render-marionette.py -- --resolution 1800 --samples 96
```

## Scene contents and limits

- Named collections separate porcelain parts, facial details, hair and ribbons,
  clothing, and the studio.
- Glazed porcelain material, visible joint seams, individual fingers and toes,
  olive irises, pink manicure, chestnut/raspberry ringlets, satin bows, corset
  piping and clasps, rear cross-lacing, and two scalloped lace skirt layers.
- A hero camera, front and back inspection cameras, and a face detail camera.
  Change the active camera in Blender to inspect other views.
- All curves, meshes, materials and lighting are editable. This is a procedural
  interpretation, not an exact reconstruction of the sheet. The painted face,
  hair silhouette and lace are simplified.
- There is no armature, animation, skinning, production retopology, physical joint
  mechanism or verified printable mesh. Separate parts do not imply rigging.
- This does not integrate an avatar into terminal chat or add an application
  dependency.

## Environment and validation

Built with the installed Blender 5.2.2 LTS (build `d13f752e3b9c`), bundled Python,
and CPU Cycles on the AMD Ryzen 7 7700X. Blender is free/open-source software;
the installed Arch package reports GPL-2.0-or-later/GPL-3.0-or-later and bundled
component licenses including Apache-2.0, BSD, LGPL, MIT, MPL-2.0, and Zlib
(`pacman -Qi blender`). No software was installed for this experiment. Blender is
an optional experiment tool, so it is excluded from the active application
dependency inventory in `docs/licenses.md`.

Validation: Python compilation, successful scene creation and Cycles rendering,
visual inspection, and reopening the saved scene and rendering its detail camera.
The saved scene has four cameras and no external image-texture dependencies.
