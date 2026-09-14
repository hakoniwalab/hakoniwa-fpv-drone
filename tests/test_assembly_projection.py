import tempfile
import unittest
from pathlib import Path

import yaml

from fpv_drone_generator.assembly import load_assembly_graph, project_recipe, resolve_assembly
from fpv_drone_generator.catalog import load_catalogs
from fpv_drone_generator.package import generate_package
from fpv_drone_generator.recipe import load_recipe
from fpv_drone_generator.resolver import resolve_vehicle
from fpv_drone_generator.target import bundled_drone_pro_rotor_contract_path, load_drone_pro_rotor_contract

from .support import CATALOGS, ROOT


class AssemblyProjectionTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
