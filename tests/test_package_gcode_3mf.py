import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from package_gcode_3mf import package


MODEL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <resources>
    <object id="1" type="model">
      <mesh>
        <vertices>
          <vertex x="0" y="0" z="0"/>
          <vertex x="20" y="10" z="5"/>
        </vertices>
        <triangles/>
      </mesh>
    </object>
  </resources>
  <build>
    <item objectid="1"/>
  </build>
</model>
"""


class PackageGcode3mfTest(unittest.TestCase):
    def test_packages_gcode_and_metadata_into_project_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project.3mf"
            gcode = root / "plate_1.gcode"
            result = root / "result.json"
            settings = root / "printer.json"
            output = root / "out" / "sample.gcode.3mf"

            with zipfile.ZipFile(project, "w") as archive:
                archive.writestr("3D/Objects/object_1.model", MODEL_XML)
                archive.writestr("Metadata/project_settings.config", "{}")

            gcode_text = "\n".join(
                [
                    "; total layer number: 7",
                    "; CONFIG_BLOCK_START",
                    "; printer_model = X1 Carbon",
                    "; printer_variant = 0.4",
                    "; CONFIG_BLOCK_END",
                    "G1 X0 Y0",
                ]
            )
            gcode.write_text(gcode_text, encoding="utf-8")
            result.write_text(
                json.dumps(
                    {
                        "layer_height": 0.2,
                        "sliced_plates": [
                            {
                                "objects": [
                                    {
                                        "id": 12,
                                        "name": "sample",
                                        "bbox": {
                                            "x": 1,
                                            "y": 2,
                                            "width": 20,
                                            "depth": 10,
                                        },
                                    }
                                ],
                                "feature_type_times": {"Bottom surface": 3},
                                "filaments": [{"total_used_g": 4.2}],
                                "total_predication": 123.4,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            settings.write_text(
                json.dumps(
                    {
                        "name": "Test Printer Preset",
                        "printer_model": "Preset Model",
                        "printable_area": "0x0,256x256",
                    }
                ),
                encoding="utf-8",
            )

            package(project, gcode, result, output, settings)

            with zipfile.ZipFile(output, "r") as archive:
                names = set(archive.namelist())
                self.assertIn("Metadata/plate_1.gcode", names)
                self.assertIn("Metadata/plate_1.gcode.md5", names)
                self.assertIn("Metadata/plate_1.json", names)
                self.assertIn("Metadata/slice_info.config", names)
                self.assertIn("Metadata/plate_1.png", names)
                self.assertEqual(archive.read("Metadata/plate_1.gcode"), gcode_text.encode("utf-8"))
                self.assertEqual(
                    archive.read("Metadata/plate_1.gcode.md5").decode("ascii"),
                    hashlib.md5(gcode_text.encode("utf-8")).hexdigest().upper(),
                )

                plate = json.loads(archive.read("Metadata/plate_1.json").decode("utf-8"))
                self.assertEqual(plate["bbox_all"], [1, 2, 21, 12])
                self.assertEqual(plate["bbox_objects"][0]["name"], "sample")

                slice_info = archive.read("Metadata/slice_info.config").decode("utf-8")
                self.assertIn('prediction" value="123"', slice_info)
                self.assertIn('weight" value="4.20"', slice_info)
                self.assertIn('layer_ranges="0 7"', slice_info)

                project_settings = json.loads(archive.read("Metadata/project_settings.config").decode("utf-8"))
                self.assertEqual(project_settings["printer_settings_id"], "Test Printer Preset")
                self.assertEqual(project_settings["printer_model"], "Preset Model")
                self.assertEqual(project_settings["printable_area"], "0x0,256x256")


if __name__ == "__main__":
    unittest.main()
