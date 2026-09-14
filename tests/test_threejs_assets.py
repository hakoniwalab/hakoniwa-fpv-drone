import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from fpv_drone_generator.assembly import load_assembly_graph, resolve_assembly, resolve_assembly_poses
from fpv_drone_generator.catalog import load_catalogs
from fpv_drone_generator.threejs_assets import export_threejs_assets

from .support import CATALOGS, ROOT


@unittest.skipUnless(importlib.util.find_spec("trimesh"), "trimesh is required")
class ThreeJsAssetsTest(unittest.TestCase):
    def test_master3x_export_has_separate_body_propeller_and_camera(self):
        graph = load_assembly_graph(ROOT / "recipes/examples/master3x-visual-demo.assembly.json")
        resolved = resolve_assembly(graph, load_catalogs(CATALOGS))
        poses = resolve_assembly_poses(resolved)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "assets"
            manifest_path = export_threejs_assets(resolved, output)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("master3x-visual-demo", manifest["drone_type"])
            for artifact in ("body", "propeller", "camera"):
                self.assertEqual(b"glTF", (output / manifest["artifacts"][artifact]).read_bytes()[:4])

            import trimesh
            propeller_scene = trimesh.load(output / "propeller.glb", force="scene")
            propeller_extents = propeller_scene.extents
            # Catalog propellers are horizontal in FLU (thin Z).  Generated
            # GLBs are in the viewer's Three basis, where Y is vertical.
            self.assertLess(propeller_extents[1], propeller_extents[0])
            self.assertLess(propeller_extents[1], propeller_extents[2])

            drone_types = json.loads((output / "drone-types.json").read_text(encoding="utf-8"))
            drone = drone_types["master3x-visual-demo"]
            self.assertEqual("./body.glb", drone["model"]["model_path"])
            self.assertEqual(4, len(drone["rotors"]))
            self.assertEqual([-1, 1, -1, 1], [rotor["spinDirection"] for rotor in drone["rotors"]])
            self.assertEqual(
                list(poses["propeller_1"].position_m),
                drone["rotors"][0]["pos"],
            )
            self.assertEqual(list(poses["camera"].position_m), drone["cameras"][0]["pos"])
            self.assertEqual("./camera.glb", drone["cameras"][0]["model"]["model_path"])

    def test_poses_share_frame_rooted_rigid_transform_contract(self):
        graph = load_assembly_graph(ROOT / "recipes/examples/master3x-visual-demo.assembly.json")
        poses = resolve_assembly_poses(resolve_assembly(graph, load_catalogs(CATALOGS)))
        self.assertEqual((0.0, 0.0, 0.0), poses["frame"].position_m)
        self.assertAlmostEqual(0.067, poses["camera"].position_m[0])
        self.assertAlmostEqual(0.014, poses["camera"].position_m[2])
