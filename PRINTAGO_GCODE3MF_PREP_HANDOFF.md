# Handoff: Printago-GCode3MF-Prep

This handoff is intended to seed a new Codex project and GitHub repo for a
generic Printago `.gcode.3mf` preparation tool.

Recommended new project name:

```text
Printago-GCode3MF-Prep
```

Recommended local folder:

```text
/path/to/Printago-GCode3MF-Prep
```

Recommended GitHub repo:

```text
baschwar/Printago-GCode3MF-Prep
```

## Why This Should Be A Separate Repo

`Gridfinity-Bin-Batcher` should stay focused on Gridfinity Extended bins:

- CSV-driven bin dimensions
- OpenSCAD generation
- Gridfinity-specific naming
- known bin libraries
- Bambu/Printago packaging for those generated bins

`Printago-GCode3MF-Prep` should be generic:

- arbitrary source files
- reusable placement policies
- multiple printer profiles
- Printago-compatible `.gcode.3mf` output
- validation and import-readiness checks

Keeping this separate avoids coupling generic Printago prep to Gridfinity bin
geometry, OpenSCAD defaults, and `bin_1x5x6`-style naming.

## Goal

Create a command-line tool that takes print-ready model files and produces
printer-prefixed, Printago-compatible `.gcode.3mf` packages.

Initial target:

```text
input STL/3MF -> Bambu Studio CLI slice -> package .gcode.3mf -> validate
```

The core deliverable is a set of files like:

```text
exports/gcode3mf/x1c/x1c_part-name.gcode.3mf
exports/gcode3mf/p2s/p2s_part-name.gcode.3mf
```

## Proven Source Repo

This work is being spun out from:

```text
baschwar/Gridfinity-Bin-Batcher
```

Useful files to copy first:

- `batch_slice_gcode_3mf.py`
- `package_gcode_3mf.py`
- `requirements.txt`
- profile folder placeholders:
  - `profiles/printer-presets/.gitkeep`
  - `profiles/cli-printer-presets/.gitkeep`

Useful files to reference, but not copy blindly:

- `make_bambu_project_3mf.py`
- `README.md`
- `ROADMAP.md`
- `FUTURE_PRINTAGO_AUTOMATION.md`

## Initial Repo Structure

Suggested starting layout:

```text
Printago-GCode3MF-Prep/
  README.md
  CHANGELOG.md
  ROADMAP.md
  requirements.txt
  .gitignore
  profiles/
    printer-presets/
      .gitkeep
    cli-printer-presets/
      .gitkeep
  src/
    printago_gcode3mf_prep/
      __init__.py
      cli.py
      slicer.py
      packager.py
      profiles.py
      placement.py
      validate.py
      thumbnails.py
  scripts/
    prep_files.py
  tests/
  examples/
    inputs/
    manifests/
```

For the first pass, it is fine to keep scripts at the repo root while the shape
is still moving. Once behavior is proven, move into `src/`.

## Dependencies

Required:

- macOS
- Python 3
- Bambu Studio with CLI access
- user-exported Bambu Studio printer preset JSON files
- `Pillow` for fallback thumbnail generation

Optional:

- CAD Viewer for higher-quality preview thumbnails
- companion part-ejection repo:
  <https://github.com/baschwar/3D-Printed-Part-Ejection-GCode>

Important: this new repo should not ship personal printer preset JSONs. Users
must export their own Bambu Studio printer presets.

## Printer Preset Model

Use the same two-folder model proven in `Gridfinity-Bin-Batcher`:

```text
profiles/printer-presets/
profiles/cli-printer-presets/
```

`profiles/printer-presets/` contains the original Bambu Studio exported preset.
This is used to stamp printer metadata into the final `.gcode.3mf` package.

`profiles/cli-printer-presets/` contains a CLI-safe copy. Bambu Studio CLI needs
the preset JSON to include:

```json
{
  "type": "machine"
}
```

Do not commit preset JSONs. Commit only `.gitkeep` files and docs explaining
where the user should place their own presets.

## Part-Ejection Behavior

The prep tool should not generate or invent part-ejection G-code.

Part-ejection behavior should come from the user's selected Bambu printer
preset. If the preset includes tested part-ejection start/end G-code, then the
generated package should inherit it because Bambu Studio CLI embeds that sliced
G-code into `plate_1.gcode`.

Docs should point users to:

```text
https://github.com/baschwar/3D-Printed-Part-Ejection-GCode
```

The tool should make this explicit:

- packages made with ejection presets can be automation-ready
- packages made without ejection presets are normal sliced print files
- ejection G-code is printer-, build-plate-, filament-, and part-specific
- users must test ejection before unattended printing

## Core Pipeline

The first useful version should support this pipeline:

1. Discover input files from a folder or manifest.
2. Optionally wrap source mesh into a Bambu project 3MF if needed.
3. Apply placement policy.
4. Slice with Bambu Studio CLI for one or more printer profiles.
5. Package `plate_1.gcode` and `result.json` into Printago-compatible
   `.gcode.3mf`.
6. Stamp printer metadata from the original exported preset.
7. Generate or inject thumbnails.
8. Validate package structure and plate metadata.

## Inputs

Initial supported inputs:

- `.stl`
- plain `.3mf`
- Bambu project `.3mf`

Later:

- `.obj`
- `.step` only if a mesh conversion path is intentionally added
- batch manifests with per-part metadata

Suggested manifest CSV:

```csv
name,input_path,rotate_z,front_margin,profile_keys
sample_part,inputs/sample_part.stl,90,5,"x1c,p2s"
```

Suggested manifest JSON:

```json
{
  "items": [
    {
      "name": "sample_part",
      "input_path": "inputs/sample_part.stl",
      "rotate_z": 90,
      "front_margin": 5,
      "profile_keys": ["x1c", "p2s"]
    }
  ]
}
```

## Placement Policies

Placement should be explicit and configurable.

Minimum policies:

- `center`: center the part on the plate
- `front`: center X and set front edge to a margin, default 5 mm
- `preserve`: do not alter project placement

Useful options:

```text
--placement front
--front-margin 5
--rotate-z 90
--plate-width 256
--plate-depth 256
```

Important lesson from `Gridfinity-Bin-Batcher`: placement math must use the
rotated footprint. If a model is rotated 90 degrees, compute the front edge from
the post-rotation Y span, not the source mesh Y span.

## Slicing

Start from `batch_slice_gcode_3mf.py`.

Current proven Bambu CLI command shape:

```bash
/Applications/BambuStudio.app/Contents/MacOS/BambuStudio \
  --slice 0 \
  --load-settings profiles/cli-printer-presets/<profile>.json \
  --outputdir work/slicer/<profile>/<part> \
  <project-or-source-file>.3mf
```

Expected Bambu CLI outputs:

```text
work/slicer/<profile>/<part>/plate_1.gcode
work/slicer/<profile>/<part>/result.json
```

Support:

- multiple profiles
- timeout option
- `--continue-on-error`
- `--package-only`
- resumable mode that skips existing final packages unless `--force`

Known warning:

```text
Invalid T command (T65535)
```

This appeared with one P2S preset while Bambu Studio still exited successfully
and wrote valid outputs. Treat as warning unless slicing fails or outputs are
missing.

## Packaging

Start from `package_gcode_3mf.py`.

The packager should:

- read Bambu project/source 3MF content
- embed `Metadata/plate_1.gcode`
- write `Metadata/plate_1.json` from Bambu `result.json`
- write Bambu-style slice metadata
- stamp printer metadata from the selected original preset JSON
- include generated thumbnail PNGs
- preserve enough Bambu package structure for Printago import

Current generated thumbnail approach:

- Pillow-rendered simple previews

Future thumbnail approach:

- CAD Viewer-rendered previews
- still keep Pillow fallback for headless/no-browser runs

## Output Layout

Suggested:

```text
exports/
  source/
  bambu-projects/
  gcode3mf/
    x1c/
    p2s/
work/
  slicer/
  thumbnails/
```

Do not commit `exports/` or `work/`.

## Validation

The new project should include a real validation script early.

Validation should check:

- ZIP opens cleanly
- `Metadata/plate_1.gcode` exists
- `Metadata/plate_1.json` exists
- `Metadata/project_settings.config` exists
- printer metadata matches selected profile
- bbox is on the plate
- optional front-placement check if placement policy is `front`
- package imports into Printago without errors, where manual testing is still
  required

Useful bbox audit pattern from `Gridfinity-Bin-Batcher`:

```python
import json
import zipfile
from pathlib import Path

bad = []
checked = 0
for path in sorted(Path("exports/gcode3mf").glob("*/*.gcode.3mf")):
    with zipfile.ZipFile(path) as archive:
        data = json.loads(archive.read("Metadata/plate_1.json"))
    y = data["bbox_all"][1]
    checked += 1
    if abs(y - 5.0) > 0.02:
        bad.append((str(path), y, data["bbox_all"]))

print("checked", checked)
print("bad", len(bad))
for item in bad:
    print(item)
```

Generalize this into:

```bash
python3 scripts/validate_packages.py exports/gcode3mf --front-margin 5
```

## CLI Sketch

Target command:

```bash
python3 scripts/prep_files.py \
  --input-dir inputs \
  --profile x1c \
  --profile p2s \
  --placement front \
  --front-margin 5 \
  --rotate-z 90 \
  --force \
  --continue-on-error
```

Manifest mode:

```bash
python3 scripts/prep_files.py \
  --manifest examples/manifests/parts.csv \
  --force \
  --continue-on-error
```

Package-only mode:

```bash
python3 scripts/prep_files.py \
  --manifest examples/manifests/parts.csv \
  --package-only \
  --force
```

## First Milestone

Version `v0.1.0` should prove:

- one STL input
- one Bambu project 3MF input
- two printer profiles
- front placement with 5 mm margin
- optional 90 degree Z rotation
- successful Bambu CLI slice
- successful `.gcode.3mf` packaging
- validation script passes
- at least one manual Printago import test passes

## Suggested README Warnings

Include these warnings prominently:

- This project does not ship printer presets.
- Users must export their own Bambu Studio printer preset JSONs.
- Part ejection only exists if the selected printer preset contains tested
  part-ejection G-code.
- Generated `.gcode.3mf` packages should be manually tested before production.
- The Bambu Studio CLI and package internals may change over time.

## Suggested `.gitignore`

```gitignore
.DS_Store
__pycache__/
*.pyc

exports/
work/
inputs/

profiles/**/*.json
```

## Open Questions For The New Project

- Should STL inputs be sliced directly, or always wrapped into a Bambu project
  3MF first?
- How should arbitrary STL orientation be inferred or left alone?
- Should placement policy be per-file, per-run, or both?
- Should profile definitions live in code, JSON config, or manifest files?
- Should generated release artifacts be uploaded to GitHub Releases?
- Should CAD Viewer thumbnail rendering be a first-class dependency or optional
  enhancement?

## Starting Prompt For A New Codex Thread

Use something like this in the new project folder:

```text
We are starting Printago-GCode3MF-Prep, a generic spin-out from
Gridfinity-Bin-Batcher. Build a CLI that accepts STL/plain 3MF/Bambu project 3MF
inputs, slices them with Bambu Studio CLI using user-supplied printer preset
JSONs, packages Printago-compatible .gcode.3mf files, and validates the package
structure and plate bbox. Use PRINTAGO_GCODE3MF_PREP_HANDOFF.md as the project
brief. Keep this repo independent from Gridfinity-specific generation.
```
