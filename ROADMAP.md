# Roadmap

## v0.1.x

- Keep the copied prototype scripts working while extracting generic behavior.
- Add validation commands for generated `.gcode.3mf` package structure.
- Document the manual Bambu Studio preset export process.
- Add small fixtures for package validation tests that do not require personal printer presets.

## v0.2.0

- Provide a real CLI entry point under `src/printago_gcode3mf_prep/`.
- Support explicit input discovery for `.stl`, plain `.3mf`, and Bambu project `.3mf` files.
- Replace hard-coded profile names with configurable printer profile manifests.
- Add placement policies for `center`, `front`, and `preserve`.

## Later

- Add batch manifest support.
- Improve thumbnail generation.
- Explore GitHub Release artifacts once package generation is repeatable.
