import dataclasses
import importlib.util
import math
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from fpv_drone_generator.camera_optics import mujoco_xyaxes, uptilt_from_xyaxes, vertical_fov_deg
from fpv_drone_generator.catalog import load_catalogs
from fpv_drone_generator.errors import ValidationError
from fpv_drone_generator.generators.mujoco import generate_mujoco
from fpv_drone_generator.recipe import load_recipe
from fpv_drone_generator.resolver import resolve_vehicle

from .support import CATALOGS, SAMPLE_RECIPE

TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "fpv.py"
SPEC = importlib.util.spec_from_file_location("fpv_tool_optics", TOOL_PATH)
assert SPEC and SPEC.loader
FPV_TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FPV_TOOL)


class CameraOpticsTest(unittest.TestCase):
    def test_a_diagonal_fov_becomes_the_narrower_vertical_one(self):
        # 4:3 sensor: tan(v/2) = tan(d/2) * 3/5.
        self.assertAlmostEqual(vertical_fov_deg(120.0), 2 * math.degrees(math.atan(math.tan(math.radians(60)) * 0.6)))
        self.assertAlmostEqual(vertical_fov_deg(120.0), 92.2, places=1)
        self.assertLess(vertical_fov_deg(155.0), 155.0)
        self.assertEqual(vertical_fov_deg(None), 90.0)

    def test_uptilt_round_trips_through_mujoco_xyaxes(self):
        self.assertEqual(mujoco_xyaxes(0.0), "0 -1 0 0 0 1")
        for tilt in (0.0, 25.0, -10.0):
            with self.subTest(tilt=tilt):
                values = [float(value) for value in mujoco_xyaxes(tilt).split()]
                self.assertAlmostEqual(uptilt_from_xyaxes(values), tilt)
        # A camera turned sideways is not a forward FPV camera.
        self.assertIsNone(uptilt_from_xyaxes([1, 0, 0, 0, 0, 1]))
        self.assertIsNone(uptilt_from_xyaxes([0, -1, 0]))

    def test_the_mujoco_camera_uses_the_vertical_fov_and_the_uptilt(self):
        vehicle = resolve_vehicle(load_recipe(SAMPLE_RECIPE), load_catalogs(CATALOGS))
        camera = dataclasses.replace(vehicle.components.camera, fov_deg=120.0, uptilt_deg=30.0)
        vehicle = dataclasses.replace(vehicle, components=dataclasses.replace(vehicle.components, camera=camera))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "drone.xml"
            generate_mujoco(vehicle, output)
            element = ET.parse(output).getroot().find("./worldbody/body/camera[@name='fpv']")
            self.assertAlmostEqual(float(element.attrib["fovy"]), vertical_fov_deg(120.0))
            xyaxes = [float(value) for value in element.attrib["xyaxes"].split()]
            self.assertAlmostEqual(uptilt_from_xyaxes(xyaxes), 30.0)
            # fpv.py reads it back for the Three.js camera (vertical fov, tilt as a negative ROS pitch).
            parsed = FPV_TOOL.mujoco_fpv_camera(output)
            self.assertAlmostEqual(parsed["fov_deg"], vertical_fov_deg(120.0))
            self.assertAlmostEqual(parsed["uptilt_deg"], 30.0)

    def test_catalog_uptilt_is_optional_and_bounded(self):
        from fpv_drone_generator import catalog as catalog_module

        raw = {"id": "cam", "name": "Cam", "mass_kg": 0.01, "dimensions_m": [0.02, 0.02, 0.02], "fov_deg": 120}
        self.assertEqual(catalog_module._make_camera(raw, "camera").uptilt_deg, 0.0)
        self.assertEqual(catalog_module._make_camera({**raw, "uptilt_deg": 25}, "camera").uptilt_deg, 25.0)
        for bad in ({"uptilt_deg": 90}, {"uptilt_deg": "up"}, {"fov_deg": 180}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                catalog_module._make_camera({**raw, **bad}, "camera")


if __name__ == "__main__":
    unittest.main()
