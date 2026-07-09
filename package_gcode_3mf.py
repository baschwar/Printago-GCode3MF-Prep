#!/usr/bin/env python3
"""Package a Bambu CLI plate_1.gcode into a Bambu-style gcode 3MF."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw


REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
 <Default Extension="png" ContentType="image/png"/>
 <Default Extension="gcode" ContentType="text/x.gcode"/>
</Types>
"""


GCODE_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/Metadata/plate_1.gcode" Id="rel-1" Type="http://schemas.bambulab.com/package/2021/gcode"/>
</Relationships>
"""


def read_zip(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def project_mesh_size(files: dict[str, bytes]) -> tuple[float, float, float]:
    import xml.etree.ElementTree as ET

    model = files.get("3D/Objects/object_1.model")
    if model is None:
        return 42.0, 42.0, 21.0

    root = ET.fromstring(model)
    ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    vertices = root.findall(".//m:vertex", ns)
    if not vertices:
        return 42.0, 42.0, 21.0

    xs = [float(vertex.attrib["x"]) for vertex in vertices]
    ys = [float(vertex.attrib["y"]) for vertex in vertices]
    zs = [float(vertex.attrib["z"]) for vertex in vertices]
    return max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)


def iso_point(x: float, y: float, z: float, scale: float, ox: float, oy: float) -> tuple[float, float]:
    return (
        ox + (x - y) * scale * 0.88,
        oy + (x + y) * scale * 0.44 - z * scale,
    )


def polygon(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], fill: str, outline: str | None = None) -> None:
    draw.polygon([(round(x), round(y)) for x, y in points], fill=fill, outline=outline)


def render_bin_thumbnail(width_mm: float, depth_mm: float, height_mm: float, size: int) -> bytes:
    image = Image.new("RGBA", (size, size), (243, 246, 250, 255))
    draw = ImageDraw.Draw(image)

    margin = size * 0.16
    scale_x = (size - margin * 2) / max(width_mm + depth_mm, 1) / 0.88
    scale_y = (size - margin * 2) / max((width_mm + depth_mm) * 0.44 + height_mm, 1)
    scale = min(scale_x, scale_y)
    ox = size / 2
    oy = size * 0.37 + height_mm * scale * 0.45

    w = width_mm / 2
    d = depth_mm / 2
    h = height_mm
    wall = min(max(min(width_mm, depth_mm) * 0.09, 3.0), 12.0)
    iw = max(w - wall, 1)
    id_ = max(d - wall, 1)
    floor_z = h * 0.18

    top_outer = [
        iso_point(-w, -d, h, scale, ox, oy),
        iso_point(w, -d, h, scale, ox, oy),
        iso_point(w, d, h, scale, ox, oy),
        iso_point(-w, d, h, scale, ox, oy),
    ]
    top_inner = [
        iso_point(-iw, -id_, h + 0.5, scale, ox, oy),
        iso_point(iw, -id_, h + 0.5, scale, ox, oy),
        iso_point(iw, id_, h + 0.5, scale, ox, oy),
        iso_point(-iw, id_, h + 0.5, scale, ox, oy),
    ]
    floor = [
        iso_point(-iw, -id_, floor_z, scale, ox, oy),
        iso_point(iw, -id_, floor_z, scale, ox, oy),
        iso_point(iw, id_, floor_z, scale, ox, oy),
        iso_point(-iw, id_, floor_z, scale, ox, oy),
    ]

    left_side = [
        iso_point(-w, -d, 0, scale, ox, oy),
        iso_point(-w, d, 0, scale, ox, oy),
        iso_point(-w, d, h, scale, ox, oy),
        iso_point(-w, -d, h, scale, ox, oy),
    ]
    right_side = [
        iso_point(w, -d, 0, scale, ox, oy),
        iso_point(w, d, 0, scale, ox, oy),
        iso_point(w, d, h, scale, ox, oy),
        iso_point(w, -d, h, scale, ox, oy),
    ]
    front_side = [
        iso_point(-w, d, 0, scale, ox, oy),
        iso_point(w, d, 0, scale, ox, oy),
        iso_point(w, d, h, scale, ox, oy),
        iso_point(-w, d, h, scale, ox, oy),
    ]

    shadow = [(x + size * 0.035, y + size * 0.065) for x, y in top_outer]
    polygon(draw, shadow, (202, 208, 216, 90))
    polygon(draw, left_side, "#8e8e8a")
    polygon(draw, right_side, "#a5a5a0")
    polygon(draw, front_side, "#777772")
    polygon(draw, top_outer, "#b5b5b0", "#8f8f8a")
    polygon(draw, top_inner, "#f3f6fa")
    polygon(draw, floor, "#adadaa", "#9a9a96")

    for points in (top_outer, top_inner):
        draw.line([(round(x), round(y)) for x, y in points + [points[0]]], fill="#7f7f7a", width=max(1, size // 128))

    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def render_thumbnails(files: dict[str, bytes]) -> dict[str, bytes]:
    width, depth, height = project_mesh_size(files)
    return {
        "Metadata/plate_1.png": render_bin_thumbnail(width, depth, height, 512),
        "Metadata/plate_1_small.png": render_bin_thumbnail(width, depth, height, 256),
        "Metadata/plate_no_light_1.png": render_bin_thumbnail(width, depth, height, 512),
        "Metadata/top_1.png": render_bin_thumbnail(width, depth, height, 256),
        "Metadata/pick_1.png": render_bin_thumbnail(width, depth, height, 128),
    }


def plate_json(result: dict, gcode_text: str) -> bytes:
    plate = result["sliced_plates"][0]
    obj = plate["objects"][0]
    bbox = obj["bbox"]
    bbox_all = [
        bbox["x"],
        bbox["y"],
        bbox["x"] + bbox["width"],
        bbox["y"] + bbox["depth"],
    ]
    data = {
        "bbox_all": bbox_all,
        "bbox_objects": [
            {
                "area": bbox["width"] * bbox["depth"],
                "bbox": bbox_all,
                "id": obj.get("id", 1),
                "layer_height": result.get("layer_height", 0.2),
                "name": obj.get("name", "plate_1"),
            }
        ],
        "bed_type": "textured_plate",
        "filament_colors": ["#FFFFFF"],
        "filament_ids": [0],
        "first_extruder": 0,
        "first_layer_time": plate.get("feature_type_times", {}).get("Bottom surface", 0),
        "is_seq_print": False,
        "nozzle_diameter": 0.4,
        "version": 2,
    }
    return json.dumps(data, separators=(",", ":")).encode("utf-8")


def slice_info(result: dict, gcode_text: str) -> bytes:
    plate = result["sliced_plates"][0]
    obj = plate["objects"][0]
    filament = plate.get("filaments", [{}])[0]
    prediction = int(round(plate.get("total_predication", 0)))
    weight = filament.get("total_used_g", 0)
    object_name = obj.get("name", "plate_1")
    object_id = obj.get("id", 1)
    layer_count = "0 0"
    for line in gcode_text.splitlines():
        if line.startswith("; total layer number:"):
            layer_count = "0 " + line.split(":", 1)[1].strip()
            break

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<config>
  <header>
    <header_item key="X-BBL-Client-Type" value="slicer"/>
    <header_item key="X-BBL-Client-Version" value="02.07.01.62"/>
  </header>
  <plate>
    <metadata key="index" value="1"/>
    <metadata key="extruder_type" value="0"/>
    <metadata key="nozzle_volume_type" value="0"/>
    <metadata key="nozzle_diameters" value="0.4"/>
    <metadata key="timelapse_type" value="0"/>
    <metadata key="prediction" value="{prediction}"/>
    <metadata key="weight" value="{weight:.2f}"/>
    <metadata key="outside" value="false"/>
    <metadata key="support_used" value="false"/>
    <metadata key="label_object_enabled" value="false"/>
    <metadata key="enable_filament_dynamic_map" value="false"/>
    <metadata key="has_filament_switcher" value="false"/>
    <metadata key="filament_maps" value="1 1 1 1 1"/>
    <metadata key="limit_filament_maps" value="0 0 0 0 0"/>
    <object identify_id="{object_id}" name="{object_name}" skipped="false" />
    <filament id="1" tray_info_idx="GFA00" type="PLA" color="#FFFFFF" used_g="{weight:.2f}" group_id="0" nozzle_diameter="0.40" volume_type="Standard" used_for_object="true" used_for_support="false"/>
    <nozzle id="0" extruder_id="1" nozzle_diameter="0.4" volume_type="Standard"/>
    <layer_filament_lists>
      <layer_filament_list filament_list="0" layer_ranges="{layer_count}" />
    </layer_filament_lists>
  </plate>
</config>
""".encode("utf-8")


def read_gcode_config(gcode_text: str) -> dict[str, str]:
    config: dict[str, str] = {}
    in_config = False
    for line in gcode_text.splitlines():
        if line == "; CONFIG_BLOCK_START":
            in_config = True
            continue
        if line == "; CONFIG_BLOCK_END":
            break
        if not in_config or not line.startswith("; ") or " = " not in line:
            continue
        key, value = line[2:].split(" = ", 1)
        config[key] = value
    return config


def update_project_settings(data: bytes, gcode_text: str, settings_path: Path | None) -> bytes:
    try:
        settings = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        return data

    gcode_config = read_gcode_config(gcode_text)
    for key in (
        "default_print_profile",
        "default_filament_profile",
        "printer_model",
        "printer_variant",
        "printer_settings_id",
        "bed_custom_model",
        "bed_custom_texture",
        "bed_exclude_area",
        "printable_area",
        "printable_height",
    ):
        if key in gcode_config:
            settings[key] = gcode_config[key]

    if settings_path is not None:
        preset = json.loads(settings_path.read_text(encoding="utf-8"))
        for key in (
            "name",
            "default_print_profile",
            "default_filament_profile",
            "printer_model",
            "printer_variant",
            "printer_settings_id",
            "bed_custom_model",
            "bed_custom_texture",
            "bed_exclude_area",
            "printable_area",
            "printable_height",
        ):
            if key in preset:
                target_key = "printer_settings_id" if key == "name" else key
                settings[target_key] = preset[key]

    return json.dumps(settings, indent=4, ensure_ascii=False).encode("utf-8")


def package(project: Path, gcode: Path, result: Path, output: Path, settings: Path | None) -> None:
    files = read_zip(project)
    gcode_bytes = gcode.read_bytes()
    gcode_text = gcode_bytes.decode("utf-8", errors="replace")
    result_data = json.loads(result.read_text(encoding="utf-8"))

    files["[Content_Types].xml"] = CONTENT_TYPES.encode("utf-8")
    files["Metadata/plate_1.gcode"] = gcode_bytes
    files["Metadata/plate_1.gcode.md5"] = hashlib.md5(gcode_bytes).hexdigest().upper().encode("ascii")
    files["Metadata/_rels/model_settings.config.rels"] = GCODE_RELS.encode("utf-8")
    files["Metadata/plate_1.json"] = plate_json(result_data, gcode_text)
    files["Metadata/slice_info.config"] = slice_info(result_data, gcode_text)
    files.update(render_thumbnails(files))
    if "Metadata/project_settings.config" in files:
        files["Metadata/project_settings.config"] = update_project_settings(
            files["Metadata/project_settings.config"],
            gcode_text,
            settings,
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--gcode", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--settings", type=Path, help="Printer preset JSON to stamp into project metadata.")
    args = parser.parse_args()
    package(args.project, args.gcode, args.result, args.output, args.settings)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
