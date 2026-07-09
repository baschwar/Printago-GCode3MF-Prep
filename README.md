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

## Printer Presets

This repo does not include Bambu Studio printer preset JSON files. Users must export their own presets into:

```text
profiles/printer-presets/
profiles/cli-printer-presets/
```

If automated part ejection is desired, the selected printer preset must already contain tested ejection G-code. See:

<https://github.com/baschwar/3D-Printed-Part-Ejection-GCode>
