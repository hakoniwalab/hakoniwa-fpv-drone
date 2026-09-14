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

    def test_batch_mounts_use_interface_definition_not_variant_spelling(self):
        self.assertIn('function interfaceDefinition(variantId)', self.source)
        self.assertIn('interfaceDefinition(provider.interface)==="motor-mount"', self.source)
        self.assertIn('interfaceDefinition(provider.interface)==="propeller-shaft"', self.source)
        self.assertNotIn('provider.interface.endsWith(".motor-mount")', self.source)

    def test_propeller_visual_docking_accounts_for_shaft_pose(self):
        self.assertIn('const shaftHeight=port(providerNode,connection.provider.port,"provider")?.pose.position_m[2];', self.source)
        self.assertIn('motorTop-shaftHeight-propellerBottom', self.source)


if __name__ == "__main__":
    unittest.main()
