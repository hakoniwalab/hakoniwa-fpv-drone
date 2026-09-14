#!/usr/bin/env python3
"""Create Three.js body, propeller, and camera GLBs from an Assembly Graph."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("assembly", type=Path, help="Assembly Graph YAML or JSON")
    result.add_argument("--catalogs", type=Path, default=ROOT / "catalogs", help="Catalog root")
    result.add_argument("--output-dir", type=Path, required=True, help="directory for generated GLBs and drone-types.json")
    result.add_argument("--type-name", help="optional Three.js drone-type name")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        from fpv_drone_generator.assembly import load_assembly_graph, resolve_assembly
        from fpv_drone_generator.catalog import load_catalogs
        from fpv_drone_generator.errors import FpvDroneError
        from fpv_drone_generator.threejs_assets import export_threejs_assets

        graph = load_assembly_graph(args.assembly.resolve())
        resolved = resolve_assembly(graph, load_catalogs(args.catalogs.resolve()))
        manifest = export_threejs_assets(resolved, args.output_dir.resolve(), type_name=args.type_name)
    except (FpvDroneError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Three.js assets: {manifest.parent}")
    print(f"Manifest: {manifest}")
    print(f"Drone types: {manifest.parent / 'drone-types.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
