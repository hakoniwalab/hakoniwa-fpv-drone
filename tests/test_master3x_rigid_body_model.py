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

    def test_evidence_constrains_vertical_stack(self):
        catalogs = load_catalogs(CATALOGS)
        frame = catalogs.frames.get("speedybee_master3x")
        primitives = {primitive.name: primitive for primitive in frame.geometry.visual}

        middle = primitives["middle_plate"]
        top = primitives["top_plate"]
        self.assertEqual((0.086, 0.034, 0.002), middle.dimensions_m)
        self.assertEqual((0.091, 0.030, 0.002), top.dimensions_m)

        middle_top = middle.center_m[2] + middle.dimensions_m[2] / 2.0
        top_bottom = top.center_m[2] - top.dimensions_m[2] / 2.0
        self.assertAlmostEqual(0.011, top_bottom - middle_top, places=9)

        for name in (
            "standoff_rear_right",
            "standoff_rear_left",
            "standoff_front_right",
            "standoff_front_left",
        ):
            self.assertAlmostEqual(0.011, primitives[name].length_m, places=9)

    def test_front_support_opening_uses_camera_compatibility_width(self):
        catalogs = load_catalogs(CATALOGS)
        frame = catalogs.frames.get("speedybee_master3x")
        primitives = {primitive.name: primitive for primitive in frame.geometry.visual}
        right = primitives["front_support_right"]
        left = primitives["front_support_left"]

        right_inner_face = right.center_m[1] + right.dimensions_m[1] / 2.0
        left_inner_face = left.center_m[1] - left.dimensions_m[1] / 2.0
        self.assertAlmostEqual(0.020, left_inner_face - right_inner_face, places=9)

    def test_mount_planes_follow_evidence_backed_plates(self):
        catalogs = load_catalogs(CATALOGS)
        frame = catalogs.frames.get("speedybee_master3x")
        primitives = {primitive.name: primitive for primitive in frame.geometry.visual}
        ports = {port.id: port for port in frame.assembly_ports}

        middle = primitives["middle_plate"]
        middle_top = middle.center_m[2] + middle.dimensions_m[2] / 2.0
        self.assertAlmostEqual(middle_top, ports["electronics_mount"].position_m[2], places=9)

        top = primitives["top_plate"]
        pad = primitives["battery_pad_front"]
        top_surface = top.center_m[2] + top.dimensions_m[2] / 2.0
        self.assertGreaterEqual(pad.center_m[2] - pad.dimensions_m[2] / 2.0, top_surface)
        pad_top = pad.center_m[2] + pad.dimensions_m[2] / 2.0
        self.assertAlmostEqual(pad_top, ports["battery_mount"].position_m[2], places=9)


if __name__ == "__main__":
    unittest.main()
