import tempfile
import unittest
from pathlib import Path

from fpv_drone_generator.catalog import load_catalogs

from .support import CATALOGS


class CatalogTest(unittest.TestCase):
    def test_loads_typed_catalog_groups(self):
        catalogs = load_catalogs(CATALOGS)
        self.assertEqual(4, len(catalogs.frames.items))
        self.assertEqual("generic_5inch_x", catalogs.frames.get("generic_5inch_x").id)
        self.assertEqual("hakoniwa", catalogs.controllers.get("hakoniwa_default").backend)
        self.assertEqual("capsule", catalogs.landing_gears.get("generic_quad_skid").geometry.visual[0].primitive_type)
        self.assertEqual("visual_only", catalogs.attachments.get("generic_antenna").physical_role)

    def test_composes_partial_private_catalog_root(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory)
            (private / "attachments.yaml").write_text(
                """schema_version: 1
kind: attachment
items:
  - id: private_sensor
    name: Private Sensor
    vendor: null
    description: Test-only private overlay.
    mass_kg: 0.01
    physical_role: physical
    geometry:
      visual:
        - {name: body, type: box, dimensions_m: [0.01, 0.01, 0.01]}
      collision: []
      inertial:
        - {name: mass_proxy, type: box, dimensions_m: [0.01, 0.01, 0.01]}
""",
                encoding="utf-8",
            )
            catalogs = load_catalogs([CATALOGS, private])
            self.assertEqual("private_sensor", catalogs.attachments.get("private_sensor").id)
            self.assertEqual("generic_antenna", catalogs.attachments.get("generic_antenna").id)


if __name__ == "__main__":
    unittest.main()
