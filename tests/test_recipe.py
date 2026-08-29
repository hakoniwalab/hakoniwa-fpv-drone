import tempfile
import unittest
from pathlib import Path

from fpv_drone_generator.errors import ValidationError
from fpv_drone_generator.recipe import load_recipe

from .support import SAMPLE_RECIPE


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


if __name__ == "__main__":
    unittest.main()
