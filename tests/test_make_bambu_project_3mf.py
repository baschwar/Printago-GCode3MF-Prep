import tempfile
import unittest
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

from make_bambu_project_3mf import CORE_NS, create_project


class MakeBambuProject3mfTest(unittest.TestCase):
    def test_wraps_stl_in_bambu_project_template_with_real_geometry(self) -> None:
        source = Path("tests/gf-rebuilt-bin-5x2x6-s1x1-Cylinders-55499.stl")
        template = Path("templates/bambu/printago_project_template.3mf")
        self.assertTrue(source.exists())
        self.assertTrue(template.exists())

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "project.3mf"
            stats = create_project(
                template=template,
                source=source,
                output=output,
                placement="front",
                front_margin=5.0,
                plate_width=256.0,
                plate_depth=256.0,
                rotate_z=90,
            )

            self.assertEqual(stats["faces"], 9704)
            self.assertAlmostEqual(stats["span_x"], 83.5)
            self.assertAlmostEqual(stats["span_y"], 209.5)
            self.assertAlmostEqual(stats["span_z"], 42.0)

            with zipfile.ZipFile(output) as archive:
                self.assertIn("3D/3dmodel.model", archive.namelist())
                self.assertIn("3D/_rels/3dmodel.model.rels", archive.namelist())
                self.assertIn("3D/Objects/object_1.model", archive.namelist())
                self.assertIn("Metadata/model_settings.config", archive.namelist())

                object_model = ET.fromstring(archive.read("3D/Objects/object_1.model"))
                vertices = object_model.findall(f".//{{{CORE_NS}}}vertex")
                triangles = object_model.findall(f".//{{{CORE_NS}}}triangle")
                self.assertEqual(len(vertices), 29112)
                self.assertEqual(len(triangles), 9704)

                root_model = ET.fromstring(archive.read("3D/3dmodel.model"))
                build_item = root_model.find(f".//{{{CORE_NS}}}build/{{{CORE_NS}}}item")
                self.assertIsNotNone(build_item)
                self.assertEqual(
                    build_item.attrib["transform"],
                    "0 1 0 -1 0 0 0 0 1 128 46.75 21",
                )


if __name__ == "__main__":
    unittest.main()
