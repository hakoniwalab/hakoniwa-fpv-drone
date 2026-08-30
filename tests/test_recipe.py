import tempfile
import unittest
from pathlib import Path

from fpv_drone_generator.errors import ValidationError
from fpv_drone_generator.recipe import load_recipe

from .support import SAMPLE_RECIPE


UTILITY_RECIPE = SAMPLE_RECIPE.parent / "utility-quad-with-skid.yaml"


class RecipeTest(unittest.TestCase):
    def test_loads_sample_recipe(self):
        recipe = load_recipe(SAMPLE_RECIPE)
        self.assertEqual("quad_x", recipe.vehicle_type)
        self.assertEqual(4, recipe.components.motor_count)
        self.assertEqual("angle", recipe.controller_mode)

    def test_rejects_non_quad_x(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.yaml"
            path.write_text("schema_version: 1\nname: bad\ntype: hex\n", encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "quad_x"):
                load_recipe(path)

    def test_loads_schema_v2_landing_gear_and_attachments(self):
        recipe = load_recipe(UTILITY_RECIPE)
        self.assertEqual(2, recipe.schema_version)
        self.assertEqual("generic_quad_skid", recipe.components.landing_gear)
        self.assertEqual("telemetry_antenna", recipe.attachments[0].name)
        self.assertEqual("frame", recipe.attachments[0].parent)
        self.assertEqual((0.0, 15.0, 0.0), recipe.attachments[0].rpy_deg)
        self.assertEqual((0.0, 0.0, 0.04), recipe.placements.battery.position_m)

    def test_rejects_unsupported_attachment_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad-parent.yaml"
            raw = UTILITY_RECIPE.read_text(encoding="utf-8").replace("parent: frame", "parent: rotor", 1)
            path.write_text(raw, encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "parent must be frame"):
                load_recipe(path)


if __name__ == "__main__":
    unittest.main()
