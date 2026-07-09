# Printago GCode3MF Prep

Generic tooling for preparing Printago-compatible `.gcode.3mf` packages from print-ready source files.

This project is a spin-out from `baschwar/Gridfinity-Bin-Batcher`. It should stay independent from Gridfinity-specific generation and focus on arbitrary STL/plain 3MF/Bambu project 3MF inputs.

## Goal

Take one or more source print files, slice them with Bambu Studio CLI using user-supplied printer presets, package the sliced output as Printago-compatible `.gcode.3mf`, and validate the result.

## Starting Point

Read `PRINTAGO_GCODE3MF_PREP_HANDOFF.md` first. It contains the project brief, first milestone, suggested CLI shape, validation strategy, and known lessons from the Gridfinity bin batcher.

Copied starter scripts:

- `batch_slice_gcode_3mf.py`
- `package_gcode_3mf.py`

These are intentionally rough starting points and still contain assumptions from the source project. Refactor them into generic modules as behavior is proven.

## Proven STL Flow

The first tested path mirrors the working `gridfinity_extended` package flow:

1. Wrap the source STL in a Bambu project 3MF template:

```text
python3 make_bambu_project_3mf.py \
  --source tests/gf-rebuilt-bin-5x2x6-s1x1-Cylinders-55499.stl \
  --output work/e2e-x1c/project-from-stl-front-r90.3mf
```

The default placement is `--rotate-z 90 --placement front --front-margin 5`, matching the Gridfinity Extended placement behavior that keeps long bins forward on the plate.

2. Slice the project with Bambu Studio CLI using a CLI-safe machine preset plus compatible process and filament presets.

3. Export a Bambu-rendered preview PNG when accurate thumbnails matter. Bambu Studio CLI currently writes this most reliably to `/tmp`:

```text
/Applications/BambuStudio.app/Contents/MacOS/BambuStudio \
  --export-png 0 \
  --outputdir /tmp \
  work/e2e-x1c/project-from-stl-front-r90.3mf
```

4. Package the sliced `plate_1.gcode`, `result.json`, source project 3MF, printer metadata preset, and rendered thumbnail:

```text
python3 package_gcode_3mf.py \
  --project work/e2e-x1c/project-from-stl-front-r90.3mf \
  --gcode work/e2e-x1c-front-r90/plate_1.gcode \
  --result work/e2e-x1c-front-r90/result.json \
  --settings "profiles/printer-presets/Bambu Lab X1C 0.4 Large Part Cool 30º.json" \
  --thumbnail /tmp/plate_1_0.png \
  --output exports/gcode3mf/x1c/x1c_part-name.gcode.3mf
```

Use `gridfinity_extended` as the reference implementation for profile naming, front placement, and Bambu project template behavior. Keep the reusable workflow here generic instead of copying Gridfinity-specific naming or generation code.

## Printer Presets

This repo does not include Bambu Studio printer preset JSON files. Users must export their own presets into:

```text
profiles/printer-presets/
profiles/cli-printer-presets/
```

If automated part ejection is desired, the selected printer preset must already contain tested ejection G-code. See:

<https://github.com/baschwar/3D-Printed-Part-Ejection-GCode>

Do not generate part-ejection G-code in this repo. Treat ejection as an opt-in printer preset property, and keep the safety guidance in the part-eject repo authoritative.
