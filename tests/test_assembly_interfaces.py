import unittest

from fpv_drone_generator.yaml_io import load_yaml

from .support import CATALOGS, ROOT


INTERFACES = ROOT / "assembly-interfaces"


class AssemblyInterfaceCatalogTest(unittest.TestCase):
    def test_every_catalog_component_maps_to_at_least_one_variant_port(self):
        definitions = load_yaml(INTERFACES / "definitions.yaml")
        variants = load_yaml(INTERFACES / "variants.yaml")
        rules = load_yaml(INTERFACES / "connection-rules.yaml")

        definition_ids = {entry["id"] for entry in definitions["items"]}
        variant_ids = {entry["id"] for entry in variants["items"]}
        self.assertTrue(definition_ids)
        self.assertTrue(variant_ids)
        self.assertTrue(all(entry["interface"] in definition_ids for entry in variants["items"]))
        self.assertTrue(
            all(
                rule["provider_interface"] in variant_ids
                and rule["consumer_interface"] in variant_ids
                for rule in rules["items"]
            )
        )

        for catalog_path in CATALOGS.glob("*.yaml"):
            catalog = load_yaml(catalog_path)
            for component in catalog["items"]:
                ports = component.get("assembly_ports")
                self.assertIsInstance(ports, list, f"{catalog_path}:{component['id']}")
                self.assertTrue(ports, f"{catalog_path}:{component['id']}")
                self.assertEqual(len({port["id"] for port in ports}), len(ports))
                self.assertTrue(all(port["interface"] in variant_ids for port in ports))
                self.assertTrue(all(port["role"] in ("provider", "consumer") for port in ports))


if __name__ == "__main__":
    unittest.main()
