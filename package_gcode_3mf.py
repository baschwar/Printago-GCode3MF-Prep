#!/usr/bin/env python3
"""Package a Bambu CLI plate_1.gcode into a Bambu-style gcode 3MF."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw


REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"


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
    model = files.get("3D/Objects/object_1.model")
    if model is None:
        return 42.0, 42.0, 21.0

    root = ET.fromstring(model)
    ns = {"m": CORE_NS}
    vertices = root.findall(".//m:vertex", ns)
    if not vertices:
        return 42.0, 42.0, 21.0

    xs = [float(vertex.attrib["x"]) for vertex in vertices]
    ys = [float(vertex.attrib["y"]) for vertex in vertices]
    zs = [float(vertex.attrib["z"]) for vertex in vertices]
    return max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)


def parse_build_transform(files: dict[str, bytes]) -> list[float] | None:
    model = files.get("3D/3dmodel.model")
    if model is None:
        return None

    root = ET.fromstring(model)
    build_item = root.find(f".//{{{CORE_NS}}}build/{{{CORE_NS}}}item")
    if build_item is None or "transform" not in build_item.attrib:
        return None

    values = [float(value) for value in build_item.attrib["transform"].split()]
    if len(values) != 12:
        return None
    return values


def transform_point(point: tuple[float, float, float], matrix: list[float] | None) -> tuple[float, float, float]:
    if matrix is None:
        return point
    x, y, z = point
    return (
        matrix[0] * x + matrix[3] * y + matrix[6] * z + matrix[9],
        matrix[1] * x + matrix[4] * y + matrix[7] * z + matrix[10],
        matrix[2] * x + matrix[5] * y + matrix[8] * z + matrix[11],
    )


def project_mesh(files: dict[str, bytes]) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]] | None:
    model = files.get("3D/Objects/object_1.model")
    if model is None:
        return None

    root = ET.fromstring(model)
    vertex_nodes = root.findall(f".//{{{CORE_NS}}}vertex")
    triangle_nodes = root.findall(f".//{{{CORE_NS}}}triangle")
    if not vertex_nodes or not triangle_nodes:
        return None

    matrix = parse_build_transform(files)
    vertices = [
        transform_point(
            (
                float(vertex.attrib["x"]),
                float(vertex.attrib["y"]),
                float(vertex.attrib["z"]),
            ),
            matrix,
        )
        for vertex in vertex_nodes
    ]
    triangles = [
        (
            int(triangle.attrib["v1"]),
            int(triangle.attrib["v2"]),
            int(triangle.attrib["v3"]),
        )
        for triangle in triangle_nodes
    ]
    return vertices, triangles


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


def render_mesh_thumbnail(files: dict[str, bytes], size: int) -> bytes | None:
    mesh = project_mesh(files)
    if mesh is None:
        return None
    vertices, triangles = mesh

    angle = math.radians(-35)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    def view(point: tuple[float, float, float]) -> tuple[float, float, float]:
        x, y, z = point
        xr = x * cos_a - y * sin_a
        yr = x * sin_a + y * cos_a
        return xr, yr - z * 0.82, z + yr * 0.08

    viewed = [view(vertex) for vertex in vertices]
    xs = [point[0] for point in viewed]
    ys = [point[1] for point in viewed]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    margin = size * 0.12
    scale = min((size - margin * 2) / width, (size - margin * 2) / height)

    def screen(point: tuple[float, float, float]) -> tuple[float, float]:
        x, y, _ = point
        return (
            margin + (x - min_x) * scale,
            margin + (y - min_y) * scale,
        )

    faces = []
    light = (0.25, -0.55, 0.8)
    light_len = math.sqrt(sum(component * component for component in light))
    light = tuple(component / light_len for component in light)
    for a, b, c in triangles:
        p1 = vertices[a]
        p2 = vertices[b]
        p3 = vertices[c]
        u = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
        v = (p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2])
        normal = (
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )
        normal_len = math.sqrt(sum(component * component for component in normal)) or 1.0
        normal = tuple(component / normal_len for component in normal)
        brightness = max(0.0, sum(normal[index] * light[index] for index in range(3)))
        shade = int(105 + brightness * 105)
        depth = (viewed[a][2] + viewed[b][2] + viewed[c][2]) / 3.0
        faces.append(
            (
                depth,
                [screen(viewed[a]), screen(viewed[b]), screen(viewed[c])],
                (shade, shade, max(shade - 5, 0), 255),
            )
        )

    image = Image.new("RGBA", (size, size), (243, 246, 250, 255))
    draw = ImageDraw.Draw(image)
    for _, points, fill in sorted(faces, key=lambda face: face[0]):
        polygon(draw, points, fill)

    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def resize_thumbnail(data: bytes, size: int) -> bytes:
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - image.width) // 2
    y = (size - image.height) // 2
    canvas.alpha_composite(image, (x, y))
    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()


def render_thumbnails(files: dict[str, bytes], thumbnail: Path | None = None) -> dict[str, bytes]:
    if thumbnail is not None:
        data = thumbnail.read_bytes()
        image_512 = resize_thumbnail(data, 512)
        image_256 = resize_thumbnail(data, 256)
        image_128 = resize_thumbnail(data, 128)
        return {
            "Metadata/plate_1.png": image_512,
            "Metadata/plate_1_small.png": image_256,
            "Metadata/plate_no_light_1.png": image_512,
            "Metadata/top_1.png": image_256,
            "Metadata/pick_1.png": image_128,
        }

    mesh_512 = render_mesh_thumbnail(files, 512)
    mesh_256 = render_mesh_thumbnail(files, 256)
    mesh_128 = render_mesh_thumbnail(files, 128)
    if mesh_512 is not None and mesh_256 is not None and mesh_128 is not None:
        return {
            "Metadata/plate_1.png": mesh_512,
            "Metadata/plate_1_small.png": mesh_256,
            "Metadata/plate_no_light_1.png": mesh_512,
            "Metadata/top_1.png": mesh_256,
            "Metadata/pick_1.png": mesh_128,
        }

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


def package(
    project: Path,
    gcode: Path,
    result: Path,
    output: Path,
    settings: Path | None,
    thumbnail: Path | None = None,
) -> None:
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
    files.update(render_thumbnails(files, thumbnail))
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
    parser.add_argument("--thumbnail", type=Path, help="PNG preview to embed as package thumbnails.")
    args = parser.parse_args()
    package(args.project, args.gcode, args.result, args.output, args.settings, args.thumbnail)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
