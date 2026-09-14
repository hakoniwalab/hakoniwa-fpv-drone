import math
import unittest

from fpv_drone_generator.catalog import _make_primitive
from fpv_drone_generator.geometry_bounds import _primitive_min_z
from fpv_drone_generator.generators.mujoco import _primitive_size, _primitive_volume


class EllipsoidGeometryTest(unittest.TestCase):
    def test_full_dimensions_map_to_mujoco_semiaxes_and_volume(self):
        primitive = _make_primitive({
            'name': 'blade', 'type': 'ellipsoid', 'dimensions_m': [4, 2, 1],
        }, 'test')
        self.assertEqual('2 1 0.5', _primitive_size(primitive))
        self.assertAlmostEqual(4 * math.pi / 3, _primitive_volume(primitive))
        self.assertAlmostEqual(-0.5, _primitive_min_z(primitive, (0,0,0), (0,0,0)))
        self.assertAlmostEqual(-2, _primitive_min_z(primitive, (0,0,0), (0,90,0)))
