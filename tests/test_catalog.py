import unittest

from fpv_drone_generator.catalog import load_catalogs

from .support import CATALOGS


class CatalogTest(unittest.TestCase):
    def test_loads_typed_catalog_groups(self):
        catalogs = load_catalogs(CATALOGS)
        self.assertEqual(2, len(catalogs.frames.items))
        self.assertEqual("generic_5inch_x", catalogs.frames.get("generic_5inch_x").id)
        self.assertEqual("hakoniwa", catalogs.controllers.get("hakoniwa_default").backend)


if __name__ == "__main__":
    unittest.main()
