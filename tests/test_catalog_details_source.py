import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CatalogDetailsSourceTest(unittest.TestCase):
    def test_catalog_schema_declares_product_url_metadata(self):
        schema = json.loads((ROOT / "schemas" / "catalog.schema.json").read_text(encoding="utf-8"))
        metadata = schema["properties"]["items"]["items"]["properties"]["metadata"]
        product_url = metadata["properties"]["product_url"]
        self.assertEqual("string", product_url["type"])
        self.assertEqual("uri", product_url["format"])
        self.assertTrue(metadata["additionalProperties"])

    def test_composer_loads_catalog_details_module(self):
        html = (ROOT / "composer" / "index.html").read_text(encoding="utf-8")
        self.assertIn("catalog-details.js", html)

    def test_catalog_details_shows_specs_and_safe_product_url(self):
        source = (ROOT / "composer" / "catalog-details.js").read_text(encoding="utf-8")
        self.assertIn("Object.entries(item.specs || {})", source)
        self.assertIn("item.metadata?.product_url", source)
        self.assertIn('url.protocol === "http:" || url.protocol === "https:"', source)
        self.assertIn("noopener noreferrer", source)


if __name__ == "__main__":
    unittest.main()
