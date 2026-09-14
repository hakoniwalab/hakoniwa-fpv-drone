from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from .catalog import load_catalogs
from .errors import FpvDroneError
from .package import build_bom, generate_package
from .recipe import load_recipe
from .resolver import resolve_vehicle
from .showroom import SHOWROOM_KINDS, generate_catalog_showroom, open_catalog_showroom
from .target import bundled_drone_pro_rotor_contract_path, load_drone_pro_rotor_contract
from .world import load_world


def _default_catalogs() -> Path:
    return Path(__file__).resolve().parents[2] / "catalogs"


def _load(recipe_path: Path, catalog_paths: list[Path]):
    catalogs = load_catalogs(catalog_paths)
    recipe = load_recipe(recipe_path)
    return resolve_vehicle(recipe, catalogs)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fpv-drone", description="Compile catalog parts and an FPV recipe into a vehicle package.")
    parser.add_argument("--catalogs", type=Path, action="append", help="catalog directory; repeat to compose public and private catalogs")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate and resolve a recipe")
    validate.add_argument("recipe", type=Path)
    bom = subparsers.add_parser("bom", help="print the resolved bill of materials")
    bom.add_argument("recipe", type=Path)
    generate = subparsers.add_parser("generate", help="generate a Hakoniwa/MuJoCo vehicle package")
    generate.add_argument("recipe", type=Path)
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--world", type=Path, help="optional MuJoCo world/course YAML")
    generate.add_argument("--drone-pro-rotor-contract", type=Path, help="override the bundled Drone PRO target contract")

    catalog_view = subparsers.add_parser(
        "catalog-view",
        help="render catalog components as a MuJoCo showroom",
    )
    catalog_view.add_argument(
        "kind",
        nargs="?",
        choices=SHOWROOM_KINDS,
        help="optional component kind to show",
    )
    catalog_view.add_argument(
        "item_id",
        nargs="?",
        help="optional catalog item id; requires kind",
    )
    catalog_view.add_argument(
        "--output",
        type=Path,
        default=Path("build/catalog-showroom.xml"),
        help="generated showroom MJCF path",
    )
    catalog_view.add_argument(
        "--no-open",
        action="store_true",
        help="generate MJCF without launching MuJoCo Viewer",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        catalog_paths = args.catalogs or [_default_catalogs()]
        if args.command == "catalog-view":
            catalogs = load_catalogs(catalog_paths)
            output = generate_catalog_showroom(
                catalogs,
                args.output.resolve(),
                args.kind,
                args.item_id,
            )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "output": str(output),
                        "kind": args.kind,
                        "item_id": args.item_id,
                    },
                    ensure_ascii=False,
                )
            )
            if not args.no_open:
                open_catalog_showroom(output)
            return 0

        vehicle = _load(args.recipe, catalog_paths)
        if args.command == "validate":
            print(f"OK: {vehicle.recipe.name} ({vehicle.recipe.vehicle_type}, {vehicle.total_mass_kg:.3f} kg)")
        elif args.command == "bom":
            print(yaml.safe_dump(build_bom(vehicle), sort_keys=False, allow_unicode=True), end="")
        elif args.command == "generate":
            world = load_world(args.world.resolve()) if args.world else None
            contract_path = args.drone_pro_rotor_contract or bundled_drone_pro_rotor_contract_path()
            contract = load_drone_pro_rotor_contract(contract_path)
            output = generate_package(vehicle, args.output.resolve(), world, contract)
            print(json.dumps({"ok": True, "vehicle": vehicle.recipe.name, "output": str(output)}, ensure_ascii=False))
        return 0
    except FpvDroneError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
