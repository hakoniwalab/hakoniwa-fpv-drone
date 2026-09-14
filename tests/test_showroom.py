import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from fpv_drone_generator.catalog import load_catalogs
from fpv_drone_generator.showroom import generate_catalog_showroom

from .support import CATALOGS


class CatalogShowroomTest(unittest.TestCase):
    def test_generate_all_catalog_components(self):
        catalogs = load_catalogs(CATALOGS)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "showroom.xml"
            result = generate_catalog_showroom(catalogs, output)
            self.assertEqual(output, result)
            root = ET.parse(output).getroot()

        self.assertEqual("hakoniwa_fpv_catalog_showroom", root.attrib["model"])
        body_names = {
            body.attrib["name"]
            for body in root.findall("./worldbody/body")
        }
        self.assertIn("frame__generic_5inch_x", body_names)
        self.assertIn("motor__generic_2207_1850kv", body_names)
        self.assertIn("propeller__generic_5inch_3blade", body_names)
        self.assertIn("battery__generic_6s_1300mah", body_names)
        self.assertIn("camera__generic_fpv_camera", body_names)

        geom_names = [geom.attrib["name"] for geom in root.findall(".//geom")]
        self.assertEqual(len(geom_names), len(set(geom_names)))

    def test_generate_single_propeller_builds_blades_from_catalog_fields(self):
        catalogs = load_catalogs(CATALOGS)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "propeller.xml"
            generate_catalog_showroom(
                catalogs,
                output,
                kind="propeller",
                item_id="generic_5inch_3blade",
            )
            root = ET.parse(output).getroot()

        bodies = root.findall("./worldbody/body")
        self.assertEqual(1, len(bodies))
        self.assertEqual("propeller__generic_5inch_3blade", bodies[0].attrib["name"])
        visual_geoms = [
            geom
            for geom in bodies[0].findall("geom")
            if "__visual_" in geom.attrib["name"]
        ]
        self.assertEqual(4, len(visual_geoms))
        self.assertEqual("cylinder", visual_geoms[0].attrib["type"])
        self.assertEqual(["box", "box", "box"], [geom.attrib["type"] for geom in visual_geoms[1:]])

    def test_generate_kind_filter(self):
        catalogs = load_catalogs(CATALOGS)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "motors.xml"
            generate_catalog_showroom(catalogs, output, kind="motor")
            root = ET.parse(output).getroot()

        body_names = [
            body.attrib["name"]
            for body in root.findall("./worldbody/body")
        ]
        self.assertTrue(body_names)
        self.assertTrue(all(name.startswith("motor__") for name in body_names))


if __name__ == "__main__":
    unittest.main()
