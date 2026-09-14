import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "composer" / "app.js"


class BrowserComposerSourceTest(unittest.TestCase):
    def setUp(self):
        self.source = APP_JS.read_text(encoding="utf-8")

    def test_main_camera_uses_z_up(self):
        self.assertIn("camera.up.set(0,0,1)", self.source)

    def test_graph_type_is_derived_from_frame_profile(self):
        self.assertIn('function vehicleType()', self.source)
        self.assertIn('type:vehicleType()', self.source)
        self.assertNotIn('type:"quad_x",controller_mode', self.source)

    def test_node_and_rotor_ids_use_free_slots(self):
        self.assertIn('function nextNodeId(kind)', self.source)
        self.assertIn('function nextRotorIndex()', self.source)
        self.assertIn('id:nextNodeId("motor")', self.source)
        self.assertIn('id:nextNodeId("propeller")', self.source)
        self.assertNotIn('const ordinal=state.nodes.filter', self.source)


if __name__ == "__main__":
    unittest.main()
