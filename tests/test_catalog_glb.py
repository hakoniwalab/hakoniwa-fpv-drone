import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from fpv_drone_generator.catalog import load_catalogs
from fpv_drone_generator.catalog_glb import export_catalog_glb

from .support import CATALOGS


TRIMESH_AVAILABLE = importlib.util.find_spec("trimesh") is not None


@unittest.skipUnless(TRIMESH_AVAILABLE, "trimesh is an optional showroom dependency")
class CatalogGlbTest(unittest.TestCase):
    def test_export_single_propeller_and_manifest(self):
        import trimesh

        catalogs = load_catalogs(CATALOGS)
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "glb"
            manifest_path = export_catalog_glb(
                catalogs,
                output_dir,
                kind="propeller",
                item_id="generic_5inch_3blade",
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(1, len(manifest["items"]))
            item = manifest["items"][0]
            self.assertEqual("propeller", item["kind"])
            self.assertEqual("generic_5inch_3blade", item["id"])
            self.assertEqual(3, item["specs"]["blade_count"])
            asset = output_dir / item["asset"]
            self.assertTrue(asset.is_file())
            self.assertEqual(b"glTF", asset.read_bytes()[:4])
            scene = trimesh.load(asset, force="scene")
            self.assertTrue(scene.geometry)

    def test_export_all_catalog_items(self):
        catalogs = load_catalogs(CATALOGS)
        expected = sum(
            len(group.items)
            for group in (
                catalogs.frames,
                catalogs.motors,
                catalogs.propellers,
                catalogs.batteries,
                catalogs.cameras,
                catalogs.controllers,
                catalogs.landing_gears,
                catalogs.attachments,
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "glb"
            manifest_path = export_catalog_glb(catalogs, output_dir)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(expected, len(manifest["items"]))
            self.assertTrue(
                all((output_dir / item["asset"]).is_file() for item in manifest["items"])
            )


if __name__ == "__main__":
    unittest.main()
