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


def _default_catalogs() -> Path:
    return Path(__file__).resolve().parents[2] / "catalogs"


def _load(recipe_path: Path, catalog_path: Path):
    catalogs = load_catalogs(catalog_path)
    recipe = load_recipe(recipe_path)
    return resolve_vehicle(recipe, catalogs)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fpv-drone", description="Compile catalog parts and an FPV recipe into a vehicle package.")
    parser.add_argument("--catalogs", type=Path, default=_default_catalogs(), help="catalog directory (default: repository catalogs/)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate and resolve a recipe")
    validate.add_argument("recipe", type=Path)
    bom = subparsers.add_parser("bom", help="print the resolved bill of materials")
    bom.add_argument("recipe", type=Path)
    generate = subparsers.add_parser("generate", help="generate a Hakoniwa/MuJoCo vehicle package")
    generate.add_argument("recipe", type=Path)
    generate.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        vehicle = _load(args.recipe, args.catalogs)
        if args.command == "validate":
            print(f"OK: {vehicle.recipe.name} ({vehicle.recipe.vehicle_type}, {vehicle.total_mass_kg:.3f} kg)")
        elif args.command == "bom":
            print(yaml.safe_dump(build_bom(vehicle), sort_keys=False, allow_unicode=True), end="")
        elif args.command == "generate":
            output = generate_package(vehicle, args.output.resolve())
            print(json.dumps({"ok": True, "vehicle": vehicle.recipe.name, "output": str(output)}, ensure_ascii=False))
        return 0
    except FpvDroneError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
