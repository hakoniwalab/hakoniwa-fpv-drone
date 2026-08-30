import math
import tempfile
import unittest
from pathlib import Path

from fpv_drone_generator.catalog import load_catalogs
from fpv_drone_generator.recipe import load_recipe
from fpv_drone_generator.resolver import resolve_vehicle

from .support import CATALOGS, SAMPLE_RECIPE


UTILITY_RECIPE = SAMPLE_RECIPE.parent / "utility-quad-with-skid.yaml"


class ResolverTest(unittest.TestCase):
    def setUp(self):
        self.vehicle = resolve_vehicle(load_recipe(SAMPLE_RECIPE), load_catalogs(CATALOGS))

    def test_resolves_mass_and_quad_x_positions(self):
        self.assertAlmostEqual(0.541, self.vehicle.total_mass_kg, places=9)
        arm = 0.225 / (2.0 * math.sqrt(2.0))
        self.assertAlmostEqual(arm, self.vehicle.rotors[0].position_m[0])
        self.assertAlmostEqual(-arm, self.vehicle.rotors[0].position_m[1])
        self.assertEqual([-1.0, 1.0, -1.0, 1.0], [rotor.rotation_direction for rotor in self.vehicle.rotors])

    def test_reports_physical_approximations(self):
        self.assertGreater(self.vehicle.thrust_to_weight_ratio, 1.0)
        self.assertTrue(any("frame inertia" in note for note in self.vehicle.approximations))
        self.assertTrue(any("point masses" in note for note in self.vehicle.approximations))

    def test_v2_counts_physical_attachments_but_delegates_inertia(self):
        vehicle = resolve_vehicle(load_recipe(UTILITY_RECIPE), load_catalogs(CATALOGS))
        self.assertAlmostEqual(0.751, vehicle.total_mass_kg, places=9)
        self.assertIsNone(vehicle.center_of_mass_m)
        self.assertIsNone(vehicle.inertia_kg_m2)
        self.assertEqual(2, sum(attachment.component.physical_role == "physical" for attachment in vehicle.attachments))

    def test_resolves_explicit_six_rotor_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "frames.yaml").write_text(
                """schema_version: 1
kind: frame
items:
  - id: test_hexa_frame
    name: Test Hexa Frame
    vendor: null
    description: Test-only explicit rotor geometry.
    mass_kg: 0.3
    dimensions_m: [0.5, 0.5, 0.05]
    wheelbase_m: 0.5
    motor_mount_positions_m:
      - [0.25, 0.0, 0.0]
      - [0.125, 0.216506, 0.0]
      - [-0.125, 0.216506, 0.0]
      - [-0.25, 0.0, 0.0]
      - [-0.125, -0.216506, 0.0]
      - [0.125, -0.216506, 0.0]
    geometry:
      inertial:
        - {name: mass_proxy, type: cylinder, radius_m: 0.24, length_m: 0.06}
""",
                encoding="utf-8",
            )
            recipe_path = root / "hexa.yaml"
            recipe_path.write_text(
                """schema_version: 2
name: test-hexa
type: multirotor
components:
  frame: test_hexa_frame
  motors: {product: generic_2207_1850kv, count: 6}
  propeller: generic_5inch_3blade
  battery: generic_6s_1300mah
  camera: generic_fpv_camera
controller: {product: hakoniwa_default, mode: angle}
rotor_layout:
  contract: hakoniwa-drone-pro/rotor-layout-v1
  rotors:
    - {name: prop1, mujoco_position_flu_m: [0.25, 0.0, 0.0], drone_pro_position_frd_m: [0.25, 0.0, 0.0], rotation_direction: 1}
    - {name: prop2, mujoco_position_flu_m: [0.125, 0.216506, 0.0], drone_pro_position_frd_m: [0.125, -0.216506, 0.0], rotation_direction: -1}
    - {name: prop3, mujoco_position_flu_m: [-0.125, 0.216506, 0.0], drone_pro_position_frd_m: [-0.125, -0.216506, 0.0], rotation_direction: 1}
    - {name: prop4, mujoco_position_flu_m: [-0.25, 0.0, 0.0], drone_pro_position_frd_m: [-0.25, 0.0, 0.0], rotation_direction: -1}
    - {name: prop5, mujoco_position_flu_m: [-0.125, -0.216506, 0.0], drone_pro_position_frd_m: [-0.125, 0.216506, 0.0], rotation_direction: 1}
    - {name: prop6, mujoco_position_flu_m: [0.125, -0.216506, 0.0], drone_pro_position_frd_m: [0.125, 0.216506, 0.0], rotation_direction: -1}
""",
                encoding="utf-8",
            )
            vehicle = resolve_vehicle(load_recipe(recipe_path), load_catalogs([CATALOGS, root]))
            self.assertEqual(6, len(vehicle.rotors))
            self.assertEqual("prop6", vehicle.rotors[-1].name)
            self.assertEqual(-1.0, vehicle.rotors[-1].rotation_direction)


if __name__ == "__main__":
    unittest.main()
