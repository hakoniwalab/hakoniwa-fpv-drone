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
from fpv_drone_generator.target import load_drone_pro_rotor_contract
from fpv_drone_generator.world import load_world

from .support import CATALOGS, SAMPLE_RECIPE, SAMPLE_WORLD


UTILITY_RECIPE = SAMPLE_RECIPE.parent / "utility-quad-with-skid.yaml"
HEXA_RECIPE = SAMPLE_RECIPE.parent / "utility-hexa.yaml"
ROTOR_CONTRACT = Path(__file__).parent / "fixtures" / "drone-pro-rotor-layout-v1.json"


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

    def test_world_course_is_independent_and_generated_into_mujoco(self):
        vehicle = resolve_vehicle(load_recipe(SAMPLE_RECIPE), load_catalogs(CATALOGS))
        world = load_world(SAMPLE_WORLD)
        with tempfile.TemporaryDirectory() as directory:
            output = generate_package(vehicle, Path(directory) / "vehicle", world)
            root = ET.parse(output / "drone.xml").getroot()
            self.assertTrue((output / "world.yaml").is_file())
            course = json.loads((output / "fpv-course.json").read_text(encoding="utf-8"))
            self.assertEqual("hakoniwa-fpv-course", course["kind"])
            self.assertEqual(len(world.obstacles), len(course["obstacles"]))
            self.assertEqual(10, len(world.obstacles))
            self.assertIsNotNone(root.find("./asset/texture[@type='skybox']"))
            self.assertIsNotNone(root.find("./worldbody/body[@name='course_start-gate']"))
            self.assertEqual(
                4,
                len(root.findall("./worldbody/body[@name='course_start-gate']/geom")),
            )
            frame = root.find("./worldbody/body[@name='drone_base']/geom[@name='frame']")
            gate = root.find("./worldbody/body[@name='course_start-gate']/geom")
            ground = root.find("./worldbody/geom[@name='ground']")
            self.assertEqual("0.15 0.002 0.0001", frame.attrib["friction"])
            self.assertEqual("0.15 0.002 0.0001", gate.attrib["friction"])
            self.assertEqual("3", gate.attrib["condim"])
            self.assertEqual("0.8 0.02 0.001", ground.attrib["friction"])
            self.assertIsNone(root.find("./worldbody/body[@name='course_start-gate']/geom[@name='start-gate_center']"))
            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(10, report["world"]["obstacle_count"])

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

    def test_schema_v2_generates_deterministic_assemblies(self):
        vehicle = resolve_vehicle(load_recipe(UTILITY_RECIPE), load_catalogs(CATALOGS))
        contract = load_drone_pro_rotor_contract(ROTOR_CONTRACT)
        with tempfile.TemporaryDirectory() as directory:
            first = generate_package(vehicle, Path(directory) / "first", rotor_contract=contract)
            second = generate_package(vehicle, Path(directory) / "second", rotor_contract=contract)
            self.assertEqual(
                (first / "drone.xml").read_bytes(),
                (second / "drone.xml").read_bytes(),
            )
            xml_text = (first / "drone.xml").read_text(encoding="utf-8")
            self.assertNotIn(str(Path.home()), xml_text)
            self.assertNotIn("timestamp", xml_text.lower())
            root = ET.parse(first / "drone.xml").getroot()
            body = root.find("./worldbody/body[@name='drone_base']")
            self.assertIsNotNone(body.find("./geom[@name='frame_center_plate']"))
            self.assertIsNotNone(body.find("./geom[@name='landing_gear_left_skid_contact']"))
            self.assertIsNotNone(body.find("./geom[@name='attachment_telemetry_antenna_antenna']"))
            contact = body.find("./geom[@name='landing_gear_left_skid_contact']")
            self.assertEqual("1", contact.attrib["contype"])
            self.assertEqual("0 0 0 0", contact.attrib["rgba"])
            self.assertEqual(4, len(vehicle.rotors))
            self.assertEqual((0.1768, -0.1768, 0.02), vehicle.rotors[0].position_m)
            self.assertIsNone(body.find("./inertial"))
            compiler = root.find("./compiler")
            self.assertEqual("true", compiler.attrib["inertiafromgeom"])
            self.assertEqual("5 5", compiler.attrib["inertiagrouprange"])
            inertial_geoms = body.findall("./geom[@group='5']")
            self.assertGreater(len(inertial_geoms), 0)
            self.assertTrue(all("density" in geom.attrib for geom in inertial_geoms))
            report = json.loads((first / "report.json").read_text(encoding="utf-8"))
            self.assertEqual("delegated", report["properties"]["inertia_kg_m2"]["status"])
            bom = yaml.safe_load((first / "bom.yaml").read_text(encoding="utf-8"))
            payload = next(item for item in bom["items"] if item.get("catalog_id") == "generic_payload_box")
            self.assertEqual(2, payload["quantity"])
            self.assertEqual(["payload_left", "payload_right"], payload["instance_names"])

            try:
                import mujoco
            except ImportError:
                return
            model = mujoco.MjModel.from_xml_path(str(first / "drone.xml"))
            body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "drone_base")
            self.assertAlmostEqual(vehicle.total_mass_kg, model.body_subtreemass[body_id], places=9)

    def test_six_rotors_follow_the_drone_pro_owned_layout_contract(self):
        vehicle = resolve_vehicle(load_recipe(HEXA_RECIPE), load_catalogs(CATALOGS))
        contract = load_drone_pro_rotor_contract(ROTOR_CONTRACT)
        with tempfile.TemporaryDirectory() as directory:
            output = generate_package(vehicle, Path(directory) / "hexa", rotor_contract=contract)
            root = ET.parse(output / "drone.xml").getroot()
            config = json.loads((output / "drone_config.json").read_text(encoding="utf-8"))
            self.assertEqual(6, len(root.findall("./worldbody/body/body")))
            self.assertEqual([f"prop{index}" for index in range(1, 7)], config["components"]["droneDynamics"]["mujoco"]["propNames"])
            self.assertEqual(6, len(config["components"]["thruster"]["rotorPositions"]))
            self.assertEqual(
                [0.125, 0.216506, 0.0],
                config["components"]["thruster"]["rotorPositions"][5]["position"],
            )
            self.assertEqual(-1.0, config["components"]["thruster"]["rotorPositions"][5]["rotationDirection"])


if __name__ == "__main__":
    unittest.main()
