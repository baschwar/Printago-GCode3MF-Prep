#!/usr/bin/env python3
"""Slice all Bambu project 3MF files and package Printago-ready gcode.3mf files."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PROFILES = {
    "x1c": {
        "cli_settings": Path("profiles/cli-printer-presets/x1c_Bambu Lab X1C 0.4 Large Part Cool 30º.json"),
        "metadata_settings": Path("profiles/printer-presets/Bambu Lab X1C 0.4 Large Part Cool 30º.json"),
    },
    "p2s": {
        "cli_settings": Path("profiles/cli-printer-presets/p2s_Bambu Lab P2S 30º Large Part Eject Code.json"),
        "metadata_settings": Path("profiles/printer-presets/Bambu Lab P2S 30º Large Part Eject Code.json"),
    },
}


def run(cmd: list[str], timeout: int | None = None) -> None:
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, timeout=timeout)


def slice_one(
    bambu_studio: Path,
    project: Path,
    profile_key: str,
    profile: dict[str, Path],
    output_root: Path,
    temp_root: Path,
    force: bool,
    slice_timeout: int | None,
    package_only: bool,
) -> Path:
    stem = project.stem
    final_path = output_root / profile_key / f"{profile_key}_{stem}.gcode.3mf"
    if final_path.exists() and not force:
        print(f"skip existing {final_path}", flush=True)
        return final_path

    work_dir = temp_root / profile_key / stem
    work_dir.mkdir(parents=True, exist_ok=True)

    if not package_only:
        run(
            [
                str(bambu_studio),
                "--slice",
                "0",
                "--load-settings",
                str(profile["cli_settings"]),
                "--outputdir",
                str(work_dir),
                str(project),
            ],
            timeout=slice_timeout,
        )

    gcode = work_dir / "plate_1.gcode"
    result = work_dir / "result.json"
    if not gcode.exists() or not result.exists():
        raise FileNotFoundError(f"Missing expected Bambu CLI output in {work_dir}")

    run(
        [
            sys.executable,
            "package_gcode_3mf.py",
            "--project",
            str(project),
            "--gcode",
            str(gcode),
            "--result",
            str(result),
            "--settings",
            str(profile["metadata_settings"]),
            "--output",
            str(final_path),
        ]
    )
    return final_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects-dir", type=Path, default=Path("exports/3mf/bambu"))
    parser.add_argument("--output-dir", type=Path, default=Path("exports/gcode3mf"))
    parser.add_argument("--temp-dir", type=Path, default=Path("work/slicer"))
    parser.add_argument("--bambu-studio", type=Path, default=Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"))
    parser.add_argument("--profile", choices=sorted(PROFILES), action="append")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--clean-temp", action="store_true")
    parser.add_argument("--slice-timeout", type=int, default=180)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--package-only", action="store_true", help="Reuse existing plate_1.gcode and result.json files.")
    args = parser.parse_args()

    projects = sorted(args.projects_dir.glob("bin_*.3mf"))
    if not projects:
        raise FileNotFoundError(f"No bin_*.3mf files found in {args.projects_dir}")

    profile_keys = args.profile or sorted(PROFILES)
    for profile_key in profile_keys:
        profile = PROFILES[profile_key]
        for path in profile.values():
            if not path.exists():
                raise FileNotFoundError(path)
        (args.output_dir / profile_key).mkdir(parents=True, exist_ok=True)

    total = len(projects) * len(profile_keys)
    done = 0
    print(f"found {len(projects)} projects; producing {total} gcode.3mf packages", flush=True)
    written: list[Path] = []
    failures: list[tuple[str, Path, Exception]] = []
    for profile_key in profile_keys:
        for project in projects:
            done += 1
            print(f"[{done}/{total}] {profile_key} {project.name}", flush=True)
            try:
                written.append(
                    slice_one(
                        args.bambu_studio,
                        project,
                        profile_key,
                        PROFILES[profile_key],
                        args.output_dir,
                        args.temp_dir,
                        args.force,
                        args.slice_timeout,
                        args.package_only,
                    )
                )
            except Exception as exc:
                failures.append((profile_key, project, exc))
                print(f"FAILED {profile_key} {project}: {exc}", flush=True)
                if not args.continue_on_error:
                    raise

    if args.clean_temp and args.temp_dir.exists():
        shutil.rmtree(args.temp_dir)

    print(f"wrote {len(written)} packages under {args.output_dir}", flush=True)
    if failures:
        print("failures:", flush=True)
        for profile_key, project, exc in failures:
            print(f"  {profile_key} {project.name}: {exc}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
