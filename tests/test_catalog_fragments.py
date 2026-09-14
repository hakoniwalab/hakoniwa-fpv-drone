import tempfile
import unittest
from pathlib import Path

from fpv_drone_generator.catalog import load_catalogs
from fpv_drone_generator.errors import ValidationError

from .support import CATALOGS


class CatalogFragmentTest(unittest.TestCase):
    def test_commercial_products_are_loaded_from_product_fragments(self):
        catalogs = load_catalogs(CATALOGS)
        frame = catalogs.frames.get("speedybee_master5_v2")
        motor = catalogs.motors.get("iflight_xing2_2207_1855kv")
        self.assertEqual("SpeedyBee", frame.vendor)
        self.assertEqual("iFlight", motor.vendor)
        self.assertEqual("HQProp", catalogs.propellers.get("hqprop_5x4_3x3v2s").vendor)
        self.assertEqual("Tattu", catalogs.batteries.get("tattu_rline_v5_1200mah_6s").vendor)
        self.assertEqual("RunCam", catalogs.cameras.get("runcam_phoenix2").vendor)
        master3x = catalogs.frames.get("speedybee_master3x")
        self.assertEqual("SpeedyBee", master3x.vendor)
        self.assertEqual(0.171, master3x.wheelbase_m)
        self.assertEqual("fpv.motor-mount.9x9-or-12x12", master3x.assembly_ports[0].interface)
        master3x_motor = catalogs.motors.get("speedybee_1507_3600kv")
        self.assertEqual(3600, master3x_motor.kv_rpm_per_v)
        self.assertEqual("fpv.motor-mount.9x9-or-12x12", master3x_motor.assembly_ports[0].interface)
        self.assertEqual("HQProp", catalogs.propellers.get("hqprop_t35x25x3_1_5mm").vendor)
        self.assertEqual("sources/frames/speedybee/master5-v2.yaml", frame.metadata["source_ref"])
        self.assertEqual(
            ["https://www.speedybee.com/speedybee-master-5-v2-frame/?setCurrencyId=2"],
            frame.metadata["source_urls"],
        )
        self.assertEqual(
            ["https://shop.iflight.com/index.php?product_id=3371&route=product/product"],
            motor.metadata["source_urls"],
        )
        self.assertEqual(
            "https://www.speedybee.com/speedybee-master3x-frame/",
            master3x.metadata["source_urls"][0],
        )

    def test_generic_catalog_collections_live_under_products(self):
        expected = (
            "frames/hakoniwa.yaml",
            "motors/hakoniwa.yaml",
            "propellers/hakoniwa.yaml",
            "batteries/hakoniwa.yaml",
            "cameras/hakoniwa.yaml",
            "controllers/hakoniwa.yaml",
            "landing-gears/hakoniwa.yaml",
            "attachments/hakoniwa.yaml",
        )
        for filename in expected:
            self.assertTrue((CATALOGS / "products" / filename).is_file())
        self.assertFalse(any((CATALOGS / "products").glob("*.yaml")))
        self.assertFalse(any(CATALOGS.glob("*.yaml")))

        catalogs = load_catalogs(CATALOGS)
        self.assertEqual("Generic 5-inch X Frame", catalogs.frames.get("generic_5inch_x").name)
        self.assertEqual("Hakoniwa FPV Initial Controller", catalogs.controllers.get("hakoniwa_default").name)

    def test_fragment_requires_matching_source_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "products" / "cameras" / "test").mkdir(parents=True)
            (root / "sources" / "cameras" / "test").mkdir(parents=True)
            (root / "sources" / "cameras" / "test" / "camera.yaml").write_text(
                """schema_version: 1
kind: catalog-source
product_id: wrong_id
product_kind: camera
sources:
  - url: https://example.com/camera
    role: manufacturer_product
""",
                encoding="utf-8",
            )
            (root / "products" / "cameras" / "test" / "camera.yaml").write_text(
                """schema_version: 1
kind: camera
source_ref: sources/cameras/test/camera.yaml
item:
  id: private_camera
  name: Private Camera
  vendor: null
  description: Test fragment.
  mass_kg: 0.01
  dimensions_m: [0.02, 0.02, 0.02]
  assembly_ports: []
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValidationError, "product_id must match private_camera"):
                load_catalogs([CATALOGS, root])

    def test_fragment_source_ref_cannot_escape_catalog_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "products" / "cameras" / "test").mkdir(parents=True)
            (root / "products" / "cameras" / "test" / "camera.yaml").write_text(
                """schema_version: 1
kind: camera
source_ref: ../outside.yaml
item:
  id: private_camera
  name: Private Camera
  vendor: null
  description: Test fragment.
  mass_kg: 0.01
  dimensions_m: [0.02, 0.02, 0.02]
  assembly_ports: []
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValidationError, "must stay inside the catalog root"):
                load_catalogs([CATALOGS, root])


if __name__ == "__main__":
    unittest.main()
