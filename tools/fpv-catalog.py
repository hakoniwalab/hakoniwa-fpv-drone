#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORK_DIR = ROOT / "build" / "catalog-showroom"
DEFAULT_CATALOGS = ROOT / "catalogs"
MANAGED_ENV_FLAG = "HAKONIWA_FPV_CATALOG_MANAGED"
SHOWROOM_KINDS = (
    "frame",
    "motor",
    "propeller",
    "battery",
    "camera",
    "controller",
    "landing_gear",
    "attachment",
)


class CatalogToolError(RuntimeError):
    pass


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def managed_python(work_dir: Path) -> Path:
    venv = work_dir.resolve() / ".venv"
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise CatalogToolError(f"{label} not found: {path}")
    return path


def catalog_paths(args: argparse.Namespace) -> list[Path]:
    return [path.resolve() for path in (args.catalogs or [DEFAULT_CATALOGS])]


def prepare(args: argparse.Namespace) -> int:
    work_dir = args.work_dir.resolve()
    venv_dir = work_dir / ".venv"
    if args.recreate and venv_dir.exists():
        shutil.rmtree(venv_dir)

    python = managed_python(work_dir)
    if not python.is_file():
        work_dir.mkdir(parents=True, exist_ok=True)
        run([sys.executable, "-m", "venv", str(venv_dir)], cwd=ROOT)

    python = require_file(managed_python(work_dir), "catalog showroom Python")
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "-e",
            f"{ROOT}[showroom]",
        ],
        cwd=ROOT,
    )
    print(f"Catalog showroom environment is ready: {venv_dir}")
    print("Next: python3 tools/fpv-catalog.py doctor")
    return 0


def doctor(args: argparse.Namespace) -> int:
    try:
        import mujoco
        import yaml  # noqa: F401
        from fpv_drone_generator.catalog import load_catalogs
        from fpv_drone_generator.showroom import generate_catalog_showroom
    except ImportError as exc:
        raise CatalogToolError(
            "catalog showroom dependencies are incomplete; run prepare first"
        ) from exc

    catalogs = load_catalogs(catalog_paths(args))
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
    component_count = sum(len(group.items) for group in groups)

    output = args.work_dir.resolve() / "doctor-showroom.xml"
    generate_catalog_showroom(catalogs, output)
    model = mujoco.MjModel.from_xml_path(str(output))

    print(f"[OK] managed Python: {sys.executable}")
    print(f"[OK] MuJoCo Python: {getattr(mujoco, '__version__', 'unknown')}")
    print(f"[OK] catalog components: {component_count}")
    print(f"[OK] showroom MJCF: {output}")
    print(f"[OK] MuJoCo model geoms: {model.ngeom}")
    print("Catalog showroom doctor passed.")
    return 0


def open_viewer(args: argparse.Namespace) -> int:
    try:
        from fpv_drone_generator.catalog import load_catalogs
        from fpv_drone_generator.showroom import (
            generate_catalog_showroom,
            open_catalog_showroom,
        )
    except ImportError as exc:
        raise CatalogToolError(
            "catalog showroom dependencies are incomplete; run prepare first"
        ) from exc

    catalogs = load_catalogs(catalog_paths(args))
    output = (
        args.output.resolve()
        if args.output is not None
        else args.work_dir.resolve() / "catalog-showroom.xml"
    )
    generate_catalog_showroom(
        catalogs,
        output,
        kind=args.kind,
        item_id=args.item_id,
    )
    selection = "all components"
    if args.kind is not None:
        selection = args.kind if args.item_id is None else f"{args.kind}/{args.item_id}"
    print(f"Opening Catalog Showroom: {selection}")
    print(f"MJCF: {output}")
    open_catalog_showroom(output)
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Prepare, diagnose, and open the FPV component Catalog Showroom."
    )
    subparsers = result.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="create a local showroom Python environment and install dependencies",
    )
    prepare_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    prepare_parser.add_argument(
        "--recreate",
        action="store_true",
        help="recreate the managed virtual environment before installing",
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="validate Catalog loading, showroom generation, and MuJoCo loading",
    )
    doctor_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    doctor_parser.add_argument(
        "--catalogs",
        type=Path,
        action="append",
        help="catalog directory; repeat to compose public and private catalogs",
    )

    viewer_parser = subparsers.add_parser(
        "open-viewer",
        help="generate the selected Catalog showroom and open MuJoCo Viewer",
    )
    viewer_parser.add_argument(
        "kind",
        nargs="?",
        choices=SHOWROOM_KINDS,
        help="optional component kind to show",
    )
    viewer_parser.add_argument(
        "item_id",
        nargs="?",
        help="optional catalog item id; requires kind",
    )
    viewer_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    viewer_parser.add_argument(
        "--catalogs",
        type=Path,
        action="append",
        help="catalog directory; repeat to compose public and private catalogs",
    )
    viewer_parser.add_argument(
        "--output",
        type=Path,
        help="override generated showroom MJCF path",
    )
    return result


def _delegate_to_managed_python(raw_argv: list[str], work_dir: Path) -> int:
    python = require_file(
        managed_python(work_dir),
        "catalog showroom Python (run prepare first)",
    )
    env = os.environ.copy()
    env[MANAGED_ENV_FLAG] = "1"
    print(f"+ {python} {Path(__file__).resolve()} {' '.join(raw_argv)}", flush=True)
    completed = subprocess.run(
        [str(python), str(Path(__file__).resolve()), *raw_argv],
        cwd=ROOT,
        env=env,
        check=False,
    )
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(raw_argv)
    try:
        if args.command == "prepare":
            return prepare(args)
        if os.environ.get(MANAGED_ENV_FLAG) != "1":
            return _delegate_to_managed_python(raw_argv, args.work_dir)
        if args.command == "doctor":
            return doctor(args)
        return open_viewer(args)
    except (CatalogToolError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
