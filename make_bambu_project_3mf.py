#!/usr/bin/env python3
"""Wrap a source mesh in a Bambu Studio project 3MF template."""

from __future__ import annotations

import argparse
import copy
import html
import struct
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET


CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
BAMBU_NS = "http://schemas.bambulab.com/package/2021"
PRODUCTION_NS = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
MODEL_SETTINGS = "Metadata/model_settings.config"
ROOT_MODEL = "3D/3dmodel.model"
OBJECT_MODEL = "3D/Objects/object_1.model"

ET.register_namespace("", CORE_NS)
ET.register_namespace("BambuStudio", BAMBU_NS)
ET.register_namespace("p", PRODUCTION_NS)


def fmt(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def read_zip(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def mesh_bbox(root: ET.Element) -> tuple[float, float, float, float, float, float]:
    vertices = root.findall(f".//{{{CORE_NS}}}vertex")
    if not vertices:
        raise ValueError("3MF contains no vertices")
    xs = [float(vertex.attrib["x"]) for vertex in vertices]
    ys = [float(vertex.attrib["y"]) for vertex in vertices]
    zs = [float(vertex.attrib["z"]) for vertex in vertices]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def stl_mesh(source: Path) -> ET.Element:
    data = source.read_bytes()
    if len(data) < 84:
        raise ValueError(f"{source} is too small to be a binary STL")

    triangle_count = struct.unpack("<I", data[80:84])[0]
    expected_size = 84 + triangle_count * 50
    if expected_size != len(data):
        raise ValueError(f"{source} is not a supported binary STL")

    mesh = ET.Element(f"{{{CORE_NS}}}mesh")
    vertices_node = ET.SubElement(mesh, f"{{{CORE_NS}}}vertices")
    triangles_node = ET.SubElement(mesh, f"{{{CORE_NS}}}triangles")

    offset = 84
    vertex_index = 0
    for _ in range(triangle_count):
        offset += 12
        tri_indices = []
        for _ in range(3):
            x, y, z = struct.unpack("<fff", data[offset : offset + 12])
            offset += 12
            ET.SubElement(
                vertices_node,
                f"{{{CORE_NS}}}vertex",
                {"x": fmt(x), "y": fmt(y), "z": fmt(z)},
            )
            tri_indices.append(vertex_index)
            vertex_index += 1
        ET.SubElement(
            triangles_node,
            f"{{{CORE_NS}}}triangle",
            {"v1": str(tri_indices[0]), "v2": str(tri_indices[1]), "v3": str(tri_indices[2])},
        )
        offset += 2

    return mesh


def source_mesh(source: Path) -> ET.Element:
    suffix = source.suffix.lower()
    if suffix == ".stl":
        return stl_mesh(source)
    if suffix == ".3mf":
        files = read_zip(source)
        source_root = ET.fromstring(files[ROOT_MODEL])
        source_object = source_root.find(f".//{{{CORE_NS}}}object")
        if source_object is None:
            raise ValueError(f"No object found in {source}")
        mesh = source_object.find(f"{{{CORE_NS}}}mesh")
        if mesh is None:
            raise ValueError(f"No mesh found in {source}")
        return mesh
    raise ValueError(f"Unsupported source file type: {source.suffix}")


def normalize_mesh(mesh: ET.Element) -> tuple[ET.Element, dict[str, float]]:
    normalized = copy.deepcopy(mesh)
    bbox_root = ET.Element("root")
    bbox_root.append(copy.deepcopy(normalized))
    min_x, max_x, min_y, max_y, min_z, max_z = mesh_bbox(bbox_root)
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    center_z = (min_z + max_z) / 2.0

    for vertex in normalized.findall(f".//{{{CORE_NS}}}vertex"):
        vertex.attrib["x"] = fmt(float(vertex.attrib["x"]) - center_x)
        vertex.attrib["y"] = fmt(float(vertex.attrib["y"]) - center_y)
        vertex.attrib["z"] = fmt(float(vertex.attrib["z"]) - center_z)

    stats = {
        "span_x": max_x - min_x,
        "span_y": max_y - min_y,
        "span_z": max_z - min_z,
        "center_x": center_x,
        "center_y": center_y,
        "center_z": center_z,
        "faces": len(normalized.findall(f".//{{{CORE_NS}}}triangle")),
    }
    return normalized, stats


def set_metadata(parent: ET.Element, key: str, value: str) -> None:
    for metadata in parent.findall("metadata"):
        if metadata.attrib.get("key") == key:
            metadata.attrib["value"] = value
            return
    ET.SubElement(parent, "metadata", {"key": key, "value": value})


def update_model_settings(
    data: bytes,
    output_name: str,
    stats: dict[str, float],
    transform_x: float,
    transform_y: float,
    transform_z: float,
    rotation_matrix: str,
) -> bytes:
    root = ET.fromstring(data)
    object_node = root.find(".//object")
    if object_node is not None:
        set_metadata(object_node, "name", output_name)
        for metadata in object_node.findall("metadata"):
            if "face_count" in metadata.attrib:
                metadata.attrib["face_count"] = str(int(stats["faces"]))

    part = root.find(".//part")
    if part is not None:
        set_metadata(part, "name", output_name)
        set_metadata(part, "source_file", output_name)
        set_metadata(part, "source_offset_x", "128")
        set_metadata(part, "source_offset_y", fmt(transform_y))
        set_metadata(part, "source_offset_z", fmt(transform_z))
        mesh_stat = part.find("mesh_stat")
        if mesh_stat is not None:
            mesh_stat.attrib["face_count"] = str(int(stats["faces"]))

    assemble_item = root.find(".//assemble_item")
    if assemble_item is not None:
        assemble_item.attrib["transform"] = f"{rotation_matrix} {fmt(transform_x)} {fmt(transform_y)} {fmt(transform_z)}"

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def rotation_matrix_z(degrees: int) -> str:
    normalized = degrees % 360
    if normalized == 0:
        return "1 0 0 0 1 0 0 0 1"
    if normalized == 90:
        return "0 1 0 -1 0 0 0 0 1"
    if normalized == 180:
        return "-1 0 0 0 -1 0 0 0 1"
    if normalized == 270:
        return "0 -1 0 1 0 0 0 0 1"
    raise ValueError("--rotate-z must be one of 0, 90, 180, or 270")


def rotated_spans(span_x: float, span_y: float, rotate_z: int) -> tuple[float, float]:
    normalized = rotate_z % 360
    if normalized in (90, 270):
        return span_y, span_x
    return span_x, span_y


def create_project(
    template: Path,
    source: Path,
    output: Path,
    placement: str,
    front_margin: float,
    plate_width: float,
    plate_depth: float,
    rotate_z: int,
) -> dict[str, float]:
    template_files = read_zip(template)
    normalized_mesh, stats = normalize_mesh(source_mesh(source))
    placed_span_x, placed_span_y = rotated_spans(stats["span_x"], stats["span_y"], rotate_z)

    transform_x = plate_width / 2.0
    if placement == "front":
        transform_y = front_margin + placed_span_y / 2.0
    else:
        transform_y = plate_depth / 2.0
    transform_z = stats["span_z"] / 2.0
    rotation_matrix = rotation_matrix_z(rotate_z)

    object_root = ET.fromstring(template_files[OBJECT_MODEL])
    template_object = object_root.find(f".//{{{CORE_NS}}}object")
    if template_object is None:
        raise ValueError(f"No template object found in {template}")
    old_mesh = template_object.find(f"{{{CORE_NS}}}mesh")
    if old_mesh is not None:
        template_object.remove(old_mesh)
    template_object.attrib["name"] = html.escape(source.name, quote=True)
    template_object.append(normalized_mesh)
    template_files[OBJECT_MODEL] = ET.tostring(object_root, encoding="utf-8", xml_declaration=True)

    root_model = ET.fromstring(template_files[ROOT_MODEL])
    build_item = root_model.find(f".//{{{CORE_NS}}}build/{{{CORE_NS}}}item")
    if build_item is None:
        raise ValueError(f"No build item found in {template}")
    build_item.attrib["transform"] = f"{rotation_matrix} {fmt(transform_x)} {fmt(transform_y)} {fmt(transform_z)}"
    template_files[ROOT_MODEL] = ET.tostring(root_model, encoding="utf-8", xml_declaration=True)

    template_files[MODEL_SETTINGS] = update_model_settings(
        template_files[MODEL_SETTINGS],
        output.name,
        stats,
        transform_x,
        transform_y,
        transform_z,
        rotation_matrix,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in template_files.items():
            archive.writestr(name, data)

    return {
        **stats,
        "transform_x": transform_x,
        "transform_y": transform_y,
        "transform_z": transform_z,
        "rotate_z": rotate_z,
        "placed_span_x": placed_span_x,
        "placed_span_y": placed_span_y,
        "front_edge_y": transform_y - placed_span_y / 2.0,
        "back_edge_y": transform_y + placed_span_y / 2.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", default="templates/bambu/printago_project_template.3mf", type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--placement", choices=("center", "front"), default="front")
    parser.add_argument("--front-margin", default=5.0, type=float)
    parser.add_argument("--plate-width", default=256.0, type=float)
    parser.add_argument("--plate-depth", default=256.0, type=float)
    parser.add_argument("--rotate-z", default=90, type=int, choices=(0, 90, 180, 270))
    args = parser.parse_args()

    stats = create_project(
        args.template,
        args.source,
        args.output,
        args.placement,
        args.front_margin,
        args.plate_width,
        args.plate_depth,
        args.rotate_z,
    )
    print(f"wrote {args.output}")
    print(
        "span "
        f"x={fmt(stats['span_x'])} y={fmt(stats['span_y'])} z={fmt(stats['span_z'])}; "
        "build transform "
        f"x={fmt(stats['transform_x'])} y={fmt(stats['transform_y'])} z={fmt(stats['transform_z'])}; "
        f"rotate_z={fmt(stats['rotate_z'])}; "
        f"front edge y={fmt(stats['front_edge_y'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
