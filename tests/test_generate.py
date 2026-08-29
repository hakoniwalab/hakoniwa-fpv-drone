import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

from fpv_drone_generator.catalog import load_catalogs
from fpv_drone_generator.package import generate_package
from fpv_drone_generator.recipe import load_recipe
from fpv_drone_generator.resolver import resolve_vehicle

from .support import CATALOGS, SAMPLE_RECIPE


class GenerateTest(unittest.TestCase):
    def test_generates_complete_vehicle_package(self):
        vehicle = resolve_vehicle(load_recipe(SAMPLE_RECIPE), load_catalogs(CATALOGS))
        with tempfile.TemporaryDirectory() as directory:
            output = generate_package(vehicle, Path(directory) / "vehicle")
            expected = {
                "recipe.yaml", "resolved-components.yaml", "bom.yaml", "drone.xml",
                "drone_config.json", "control-param.json", "control-param.txt", "report.json",
            }
            self.assertEqual(expected, {path.name for path in output.iterdir()})

            root = ET.parse(output / "drone.xml").getroot()
            self.assertEqual("drone_base", root.find("./worldbody/body").attrib["name"])
            self.assertEqual(4, len(root.findall("./worldbody/body/body")))

            drone_config = json.loads((output / "drone_config.json").read_text(encoding="utf-8"))
            self.assertEqual("Drone", drone_config["name"])
            self.assertEqual("MuJoCo", drone_config["components"]["droneDynamics"]["physicsEquation"])
            self.assertEqual("adapter-hakoniwa", drone_config["controller"]["backendType"])
            self.assertEqual("control-param.txt", drone_config["controller"]["paramFilePath"])
            self.assertEqual(
                [0.0, 0.0, -0.25],
                drone_config["components"]["droneDynamics"]["position_meter"],
            )
            mujoco_rotor = root.find("./worldbody/body/body[@name='prop1']")
            self.assertIsNotNone(mujoco_rotor)
            mujoco_position = [float(value) for value in mujoco_rotor.attrib["pos"].split()]
            config_position = drone_config["components"]["thruster"]["rotorPositions"][0]["position"]
            self.assertAlmostEqual(mujoco_position[0], config_position[0])
            self.assertAlmostEqual(-mujoco_position[1], config_position[1])

            control = json.loads((output / "control-param.json").read_text(encoding="utf-8"))
            self.assertEqual(1.0, control["parameters"]["ANGLE_CONTROL_ENABLE"]["value"])
            self.assertEqual("generated_initial", control["parameters"]["MASS"]["origin"])

            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            self.assertEqual("approximation", report["properties"]["inertia_kg_m2"]["status"])
            self.assertEqual("not_calculated", report["properties"]["estimated_flight_time"]["status"])

    def test_mujoco_loads_when_python_binding_is_available(self):
        try:
            import mujoco
        except ImportError:
            self.skipTest("MuJoCo Python binding is not installed in this test interpreter")
        vehicle = resolve_vehicle(load_recipe(SAMPLE_RECIPE), load_catalogs(CATALOGS))
        with tempfile.TemporaryDirectory() as directory:
            output = generate_package(vehicle, Path(directory) / "vehicle")
            model = mujoco.MjModel.from_xml_path(str(output / "drone.xml"))
            self.assertGreater(model.nbody, 1)

    def test_rate_recipe_generates_explicit_rate_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            recipe_path = Path(directory) / "rate.yaml"
            raw = yaml.safe_load(SAMPLE_RECIPE.read_text(encoding="utf-8"))
            raw["controller"]["mode"] = "rate"
            recipe_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
            vehicle = resolve_vehicle(load_recipe(recipe_path), load_catalogs(CATALOGS))
            output = generate_package(vehicle, Path(directory) / "vehicle")
            control = json.loads((output / "control-param.json").read_text(encoding="utf-8"))
            self.assertEqual(0.0, control["parameters"]["ANGLE_CONTROL_ENABLE"]["value"])
            self.assertEqual(1.0, control["parameters"]["ANGLE_RATE_CONTROL_ENABLE"]["value"])


if __name__ == "__main__":
    unittest.main()
