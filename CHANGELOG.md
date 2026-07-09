# Changelog

All notable changes to this project will be documented in this file.

## [0.1.1] - 2026-07-09

Adds the first Printago-accepted STL workflow.

### Added

- `make_bambu_project_3mf.py` to wrap binary STL and 3MF meshes in a Bambu project template.
- Bambu project template copied from the proven Gridfinity Extended workflow.
- Default `90` degree rotation plus front placement with a 5 mm front margin.
- Optional `--thumbnail` injection for Bambu-rendered package previews.
- Regression tests for STL project wrapping and package metadata.

### Changed

- Package thumbnails now prefer real mesh rendering and can be replaced with Bambu Studio CLI preview PNGs.

## [0.1.0] - 2026-07-09

Initial scaffold for the generic Printago `.gcode.3mf` preparation tool.

### Added

- Project README and handoff brief for the spin-out from `Gridfinity-Bin-Batcher`.
- Starter Bambu slicing and Printago `.gcode.3mf` packaging scripts.
- Placeholder package structure under `src/printago_gcode3mf_prep/`.
- Placeholder directories for user-supplied Bambu Studio printer presets.
- Initial roadmap for turning the copied prototype scripts into a generic CLI.
