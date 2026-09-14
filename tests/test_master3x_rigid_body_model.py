import unittest

from fpv_drone_generator.catalog import load_catalogs

from .support import CATALOGS


class Master3XRigidBodyModelTest(unittest.TestCase):
    def test_frame_owns_structural_head_and_plate_stack(self):
        catalogs = load_catalogs(CATALOGS)
        frame = catalogs.frames.get("speedybee_master3x")
        self.assertIsNotNone(frame.geometry)
        names = {primitive.name for primitive in frame.geometry.visual}
        self.assertTrue(
            {
                "bottom_plate",
                "middle_plate",
                "top_plate",
                "front_support_left",
                "front_support_right",
                "front_support_top",
                "side_plate_left",
                "side_plate_right",
            }.issubset(names)
        )

    def test_camera_is_reduced_to_camera_side_geometry(self):
        catalogs = load_catalogs(CATALOGS)
        camera = catalogs.cameras.get("master3x_demo_camera_head")
        self.assertIsNotNone(camera.geometry)
        names = {primitive.name for primitive in camera.geometry.visual}
        self.assertIn("camera_case", names)
        self.assertIn("lens_ring", names)
        self.assertNotIn("head_top", names)
        self.assertNotIn("head_bottom", names)
        self.assertNotIn("transmitter", names)
        self.assertNotIn("antenna_stem_left", names)
        self.assertNotIn("antenna_stem_right", names)

    def test_interfaces_and_motor_mount_positions_are_preserved(self):
        catalogs = load_catalogs(CATALOGS)
        frame = catalogs.frames.get("speedybee_master3x")
        self.assertEqual(
            (
                (0.06046, -0.06046, 0.0),
                (0.06046, 0.06046, 0.0),
                (-0.06046, 0.06046, 0.0),
                (-0.06046, -0.06046, 0.0),
            ),
            frame.motor_mount_positions_m,
        )
        port_interfaces = {port.id: port.interface for port in frame.assembly_ports}
        for index in range(1, 5):
            self.assertEqual(
                "fpv.motor-mount.9x9-or-12x12",
                port_interfaces[f"motor_mount_{index}"],
            )
        self.assertEqual("hakoniwa.generic.camera-mount", port_interfaces["camera_mount"])


if __name__ == "__main__":
    unittest.main()
