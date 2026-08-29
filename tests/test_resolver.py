import math
import unittest

from fpv_drone_generator.catalog import load_catalogs
from fpv_drone_generator.recipe import load_recipe
from fpv_drone_generator.resolver import resolve_vehicle

from .support import CATALOGS, SAMPLE_RECIPE


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


if __name__ == "__main__":
    unittest.main()
