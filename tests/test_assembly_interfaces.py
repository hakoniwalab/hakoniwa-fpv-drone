import unittest

from fpv_drone_generator.catalog import load_catalogs
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

        catalogs = load_catalogs(CATALOGS)
        groups = (
            catalogs.frames,
            catalogs.motors,
            catalogs.propellers,
            catalogs.batteries,
            catalogs.cameras,
            catalogs.controllers,
            catalogs.landing_gears,
            catalogs.attachments,
        )
        for group in groups:
            for component in group.items.values():
                ports = component.assembly_ports
                self.assertTrue(ports, f"{group.kind}:{component.id}")
                self.assertEqual(len({port.id for port in ports}), len(ports))
                self.assertTrue(all(port.interface in variant_ids for port in ports))
                self.assertTrue(all(port.role in ("provider", "consumer") for port in ports))


if __name__ == "__main__":
    unittest.main()
