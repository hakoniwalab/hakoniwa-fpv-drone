import tempfile
import unittest
from pathlib import Path

import yaml

from fpv_drone_generator.assembly import (
    AssemblyConnection,
    _component_pose,
    load_assembly_graph,
    project_recipe,
    resolve_assembly,
)
from fpv_drone_generator.catalog import AssemblyPort, load_catalogs
from fpv_drone_generator.package import generate_package
from fpv_drone_generator.recipe import load_recipe
from fpv_drone_generator.resolver import resolve_vehicle
from fpv_drone_generator.target import bundled_drone_pro_rotor_contract_path, load_drone_pro_rotor_contract

from .support import CATALOGS, ROOT


class AssemblyProjectionTest(unittest.TestCase):
    def test_master3x_demo_mounts_battery_above_deck_and_camera_at_front(self):
        catalogs = load_catalogs(CATALOGS)
        graph = load_assembly_graph(ROOT / 'recipes/examples/master3x-visual-demo.assembly.json')
        projected = project_recipe(resolve_assembly(graph, catalogs))
        self.assertEqual(4, len(projected['rotor_layout']['rotors']))
        self.assertEqual([0.06046, -0.06046, 0.0], projected['rotor_layout']['rotors'][0]['motor_position_flu_m'])
        self.assertEqual([0.06046, -0.06046, 0.008], projected['rotor_layout']['rotors'][0]['position_flu_m'])
        battery_position = projected['placements']['battery']['position_m']
        self.assertAlmostEqual(0.0375, battery_position[2])
        battery = catalogs.batteries.get('generic_4s_850mah')
        self.assertGreaterEqual(battery_position[2] - battery.dimensions_m[2] / 2, 0.016)
        self.assertEqual([0.067, 0.0, 0.014], projected['placements']['camera']['position_m'])

    def test_component_pose_composes_provider_adjustment_and_consumer_inverse(self):
        provider = AssemblyPort("mount", "provider", "test", (1.0, 2.0, 3.0), (0.0, 0.0, 90.0), 1)
        consumer = AssemblyPort("mount", "consumer", "test", (0.2, 0.0, 0.0), (0.0, 0.0, 90.0), 1)
        connection = AssemblyConnection("frame", "mount", "camera", "mount", (1.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        position, rpy_deg = _component_pose(provider, consumer, connection)
        self.assertAlmostEqual(0.8, position[0])
        self.assertAlmostEqual(3.0, position[1])
        self.assertAlmostEqual(3.0, position[2])
        self.assertAlmostEqual(0.0, rpy_deg[0])
        self.assertAlmostEqual(0.0, rpy_deg[1])
        self.assertAlmostEqual(0.0, rpy_deg[2])

    def test_complete_assembly_projects_to_loadable_mjcf(self):
        graph = load_assembly_graph(ROOT / "recipes" / "examples" / "utility-quad-with-skid.assembly.yaml")
        resolved_assembly = resolve_assembly(graph, load_catalogs(CATALOGS))
        projected = project_recipe(resolved_assembly)

        self.assertEqual(2, projected["schema_version"])
        self.assertEqual(
            [0.1768, -0.1768, 0.02],
            projected["rotor_layout"]["rotors"][0]["position_flu_m"],
        )
        self.assertEqual([0.0, 0.0, 0.04], projected["placements"]["battery"]["position_m"])
        self.assertEqual([-0.06, 0.04, 0.03], projected["attachments"][0]["position_m"])

        with tempfile.TemporaryDirectory() as directory:
            recipe_path = Path(directory) / "projected.yaml"
            recipe_path.write_text(yaml.safe_dump(projected, sort_keys=False), encoding="utf-8")
            vehicle = resolve_vehicle(load_recipe(recipe_path), load_catalogs(CATALOGS))
            output = generate_package(
                vehicle,
                Path(directory) / "package",
                rotor_contract=load_drone_pro_rotor_contract(bundled_drone_pro_rotor_contract_path()),
            )
            self.assertTrue((output / "drone.xml").is_file())
            self.assertTrue((output / "drone_config.json").is_file())
            try:
                import mujoco
            except ImportError:
                self.skipTest("MuJoCo Python binding is unavailable")
            model = mujoco.MjModel.from_xml_path(str(output / "drone.xml"))
            self.assertGreater(model.ngeom, 0)

    def test_hexa_projection_uses_explicit_rotor_assignments(self):
        graph = load_assembly_graph(ROOT / "recipes" / "examples" / "utility-hexa.assembly.yaml")
        projected = project_recipe(resolve_assembly(graph, load_catalogs(CATALOGS)))
        self.assertEqual("multirotor", projected["type"])
        self.assertEqual(6, len(projected["rotor_layout"]["rotors"]))
        self.assertEqual(["prop1", "prop2", "prop3", "prop4", "prop5", "prop6"], [entry["name"] for entry in projected["rotor_layout"]["rotors"]])
        self.assertEqual([1, -1, 1, -1, 1, -1], [entry["rotation_direction"] for entry in projected["rotor_layout"]["rotors"]])

    def test_commercial_5inch_assembly_uses_dimensional_interfaces(self):
        catalogs = load_catalogs(CATALOGS)
        graph = load_assembly_graph(ROOT / "recipes" / "examples" / "speedybee-master5-commercial.assembly.yaml")
        projected = project_recipe(resolve_assembly(graph, catalogs))

        self.assertEqual("speedybee_master5_v2", projected["components"]["frame"])
        self.assertEqual("iflight_xing2_2207_1855kv", projected["components"]["motors"]["product"])
        self.assertEqual("hqprop_5x4_3x3v2s", projected["components"]["propeller"])
        self.assertEqual("tattu_rline_v5_1200mah_6s", projected["components"]["battery"])
        self.assertEqual("runcam_phoenix2", projected["components"]["camera"])
        self.assertEqual(4, len(projected["rotor_layout"]["rotors"]))
        self.assertAlmostEqual(0.0191, projected["rotor_layout"]["rotors"][0]["position_flu_m"][2])
        self.assertAlmostEqual(20.0, projected["placements"]["camera"]["rpy_deg"][1])


if __name__ == "__main__":
    unittest.main()
