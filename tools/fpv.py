#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import shutil
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECIPE = ROOT / "recipes" / "examples" / "5inch-fpv.yaml"
DEFAULT_OUTPUT = ROOT / "build" / "example-5inch"
DEFAULT_WORLD = ROOT / "recipes" / "environments" / "fpv-training-course.yaml"
DEFAULT_VERIFIED_CONFIG = ROOT / "verified-configs" / "example-5inch-angle" / "drone-config"
DEFAULT_DRONE_CORE = ROOT.parent / "hakoniwa-drone-core"
# The public release archives (mac.zip / lnx.zip / win.zip) extract to a flat
# directory of executables and shared libraries inside the drone-core checkout.
NATIVE_LAYOUTS = {
    "Darwin": ("mac", "mac-", ""),
    "Linux": ("lnx", "linux-", ""),
    "Windows": ("win", "win-", ".exe"),
}
NATIVE_DIRECTORY, NATIVE_PREFIX, EXECUTABLE_SUFFIX = NATIVE_LAYOUTS.get(platform.system(), NATIVE_LAYOUTS["Darwin"])
DEFAULT_DRONE_CORE_BIN = DEFAULT_DRONE_CORE / NATIVE_DIRECTORY
DEFAULT_DRONE_PRO = ROOT.parent / "hakoniwa-drone-pro"
DEFAULT_THREEJS_ROOT = ROOT.parent / "hakoniwa-threejs-drone"
DEFAULT_BUSINESS_PACK_ROOT = ROOT.parent / "hakoniwa-business-pack"


def foundation_python_path(python_root: Path, *, windows: bool | None = None) -> Path:
    """Match Business Pack workspace.py: Scripts/ venv or portable root on Windows."""
    if (os.name == "nt") if windows is None else windows:
        portable = python_root / "python.exe"
        return portable if portable.is_file() else python_root / "Scripts" / "python.exe"
    return python_root / "bin" / "python3"


def workspace_foundation_install(business_pack_root: Path) -> Path:
    """Prefer the install prefix exported by an active Business Pack Workspace.

    The Workspace work directory can be relocated (HAKONIWA_WORK_DIR), so the
    sibling business-pack/work layout is only the fallback outside the Workspace.
    """
    home = os.environ.get("HAKONIWA_HOME")
    if os.environ.get("HAKONIWA_WORKSPACE_ACTIVE") == "1" and home:
        return Path(home)
    return business_pack_root / "work" / "foundation" / "install"


DEFAULT_FOUNDATION_PYTHON = foundation_python_path(
    Path(os.environ["VIRTUAL_ENV"])
    if os.environ.get("HAKONIWA_WORKSPACE_ACTIVE") == "1" and os.environ.get("VIRTUAL_ENV")
    else workspace_foundation_install(DEFAULT_BUSINESS_PACK_ROOT) / "python"
)
BASE_THREEJS_WHEELBASE_M = math.hypot(0.47, 0.38)
FPV_TUNING_INITIAL_ALTITUDE_M = 2.0
FPV_TUNING_MIN_ALTITUDE_M = 0.1
FPV_TUNING_MAX_MOTOR_SATURATION_RATIO = 0.1
FPV_HOVER_ENTRY_MAX_SEC = 5.0
FPV_HOVER_ATTITUDE_BASE = {
    # Flight-proven 5-inch gains are a conservative starting point for the
    # light Master3X plant.  Hover tunes the vertical loop only; Angle owns
    # the attitude-loop search.
    "PID_ROLL_RATE_Kp": 0.15,
    "PID_ROLL_RATE_Ki": 0.08,
    "PID_ROLL_RATE_Kd": 0.005,
    "PID_PITCH_RATE_Kp": 0.15,
    "PID_PITCH_RATE_Ki": 0.08,
    "PID_PITCH_RATE_Kd": 0.005,
    "PID_YAW_RATE_Kp": 0.1,
    "PID_YAW_RATE_Ki": 0.0,
    "PID_YAW_RATE_Kd": 0.0,
    "PID_ROLL_Kp": 6.0,
    "PID_ROLL_Ki": 0.5,
    "PID_ROLL_Kd": 0.75,
    "PID_PITCH_Kp": 6.0,
    "PID_PITCH_Ki": 0.5,
    "PID_PITCH_Kd": 0.75,
    "PID_YAW_Kp": 1.0,
    "PID_YAW_Ki": 0.0,
    "PID_YAW_Kd": 0.0,
}


class RuntimeErrorWithMessage(RuntimeError):
    pass


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def paths(args: argparse.Namespace) -> dict[str, Path]:
    output = args.output.resolve()
    runtime = output / "runtime"
    return {
        "output": output,
        "runtime": runtime,
        "vehicle": runtime / "vehicle",
        "logs": runtime / "logs",
        "launcher": runtime / "launcher.json",
        "session": runtime / "launcher-session.json",
        "viewer": runtime / "threejs",
    }


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise RuntimeErrorWithMessage(f"{label} not found: {path}")
    return path


def generated_wheelbase(report_path: Path) -> float:
    report = json.loads(require_file(report_path, "generated report").read_text(encoding="utf-8"))
    points = report["properties"]["motor_positions_m"]["value"]
    distances = (
        math.dist(first, second)
        for index, first in enumerate(points)
        for second in points[index + 1 :]
    )
    wheelbase = max(distances)
    if not math.isfinite(wheelbase) or wheelbase <= 0:
        raise RuntimeErrorWithMessage(f"invalid generated motor positions: {report_path}")
    return wheelbase


def mujoco_fpv_camera(model_path: Path) -> dict[str, object]:
    root = ET.parse(require_file(model_path, "MuJoCo vehicle model")).getroot()
    camera = root.find("./worldbody/body/camera[@name='fpv']")
    if camera is None:
        raise RuntimeErrorWithMessage(f"MuJoCo FPV camera not found: {model_path}")
    position = [float(value) for value in camera.attrib.get("pos", "").split()]
    if len(position) != 3 or any(not math.isfinite(value) for value in position):
        raise RuntimeErrorWithMessage(f"invalid MuJoCo FPV camera position: {model_path}")
    xyaxes = [float(value) for value in camera.attrib.get("xyaxes", "").split()]
    if xyaxes != [0.0, -1.0, 0.0, 0.0, 0.0, 1.0]:
        raise RuntimeErrorWithMessage(
            "Three.js FPV adapter currently requires the generated forward-facing "
            f"MuJoCo camera xyaxes='0 -1 0 0 0 1': {model_path}"
        )
    fov = float(camera.attrib.get("fovy", "90"))
    if not math.isfinite(fov) or fov <= 0 or fov >= 180:
        raise RuntimeErrorWithMessage(f"invalid MuJoCo FPV camera fovy: {model_path}")
    return {"position_m": position, "fov_deg": fov}


def materialize_threejs_viewer(
    resolved: dict[str, Path],
    threejs_root: Path,
    *,
    assembly: Path | None = None,
    catalogs: Path | None = None,
    asset_python: Path | None = None,
    asset_env: dict[str, str] | None = None,
) -> Path:
    require_file(threejs_root / "index.html", "Three.js viewer")
    require_file(resolved["output"] / "fpv-course.json", "generated FPV course")
    viewer = resolved["viewer"]
    viewer.mkdir(parents=True, exist_ok=True)
    shutil.copy2(resolved["output"] / "fpv-course.json", viewer / "fpv-course.json")

    fpv_camera = mujoco_fpv_camera(resolved["vehicle"] / "drone.xml")
    custom_assets = assembly is not None
    if custom_assets:
        asset_dir = viewer / "assets"
        run(
            [
                str(asset_python or Path(sys.executable)),
                str(ROOT / "tools" / "fpv-threejs-assets.py"),
                str(assembly.resolve()),
                "--catalogs", str((catalogs or ROOT / "catalogs").resolve()),
                "--output-dir", str(asset_dir),
            ],
            cwd=ROOT,
            env=asset_env,
        )
        drone_types_path = asset_dir / "drone-types.json"
        drone_types = json.loads(drone_types_path.read_text(encoding="utf-8"))
        type_name = next(iter(drone_types))
        # The Catalog Assembly locates the visible camera housing.  The
        # generated MuJoCo model remains authoritative for the render camera.
        runtime_camera = drone_types[type_name]["cameras"][0]
        runtime_camera.update({
            "pos": fpv_camera["position_m"],
            "hpr": [0.0, 0.0, 0.0],
            "fov": fpv_camera["fov_deg"],
            "near": 0.02,
            "far": 1000,
            "window": {"x": 0.02, "y": 0.72, "width": 0.30, "height": 0.27},
        })
        drone_types_path.write_text(json.dumps(drone_types, indent=2) + "\n", encoding="utf-8")
        scale = 1.0
        camera_position = fpv_camera["position_m"]
        drone_types_reference = "./assets/drone-types.json"
    else:
        require_file(threejs_root / "config" / "drone_types-quadrotor_base.json", "Three.js base drone type")
        wheelbase = generated_wheelbase(resolved["output"] / "report.json")
        scale = wheelbase / BASE_THREEJS_WHEELBASE_M
        camera_position = [value / scale for value in fpv_camera["position_m"]]
        type_name = "quadrotor_base"
        drone_types_reference = "/hakoniwa-threejs-drone/config/drone_types-quadrotor_base.json"
    drone_instance = {
        "name": "Drone",
        "type": type_name,
        "scale": scale,
        "pos": [0.0, 0.0, 0.25],
        "hpr": [0.0, 0.0, 0.0],
    }
    if not custom_assets:
        # The visual root is scaled for legacy generic assets, so store the
        # inverse-scaled offset; its world-space mount matches MuJoCo exactly.
        drone_instance["cameras"] = [{
            "name": "fpv",
            "pos": camera_position,
            "hpr": [0.0, 0.0, 0.0],
            "fov": fpv_camera["fov_deg"],
            "near": 0.02,
            "far": 1000,
            "window": {"x": 0.02, "y": 0.72, "width": 0.30, "height": 0.27},
            "model": {
                "model_path": "/hakoniwa-threejs-drone/assets/models/base-drone-camera.glb",
                "pos": [0.0, 0.0, 0.0],
                "hpr": [0.0, 0.0, 180.0],
            },
        }]
    scene = {
        "version": "1.0",
        "format": "compact",
        "environments": [{
            "name": "fpv-training-course",
            "type": "fpv-course",
            "model": "./fpv-course.json",
        }],
        "main_camera": {
            "fov": 80,
            "near": 0.02,
            "far": 1000,
            "initialMode": "follow",
            "followDistance": 3.0,
            "followLerpPos": 8.0,
            "followLerpTarget": 10.0,
            "followToggleKey": "c",
            "position": [-2.5, -2.0, 1.5],
            "target": "Drone",
        },
        "droneTypesPath": drone_types_reference,
        "drones": [drone_instance],
    }
    viewer_config = {
        "version": "1.0",
        "three": {"sceneConfigPath": "./scene-config.json"},
        "pdu": {
            "pduDefPath": "/hakoniwa-threejs-drone/config/pdudef-fleets.json",
            "wsUri": "ws://127.0.0.1:8765",
            "wireVersion": "v2",
        },
        "ui": {
            "statePanelIntervalMsec": 50,
            "enableAttachedCameras": True,
            "enableMainCameraMouseControl": True,
            "attachedCameraPresentation": "main",
        },
        "stateInput": {
            "mode": "fleets",
            "fleets": {"roleMap": {"visual_state_array": "hako_msgs/DroneVisualStateArray"}},
        },
    }
    (viewer / "scene-config.json").write_text(json.dumps(scene, indent=2) + "\n", encoding="utf-8")
    (viewer / "viewer-config.json").write_text(json.dumps(viewer_config, indent=2) + "\n", encoding="utf-8")
    if custom_assets:
        print(f"Three.js Assembly assets: {viewer / 'assets'}")
        print("Three.js visual scale: 1.000000 (Catalog Assembly GLBs are already in metres)")
    else:
        print(f"Three.js visual scale: {scale:.6f} (generated wheelbase={wheelbase:.3f} m)")
    print(
        "Three.js FPV camera: "
        f"position={fpv_camera['position_m']} m, fov={fpv_camera['fov_deg']:.1f} deg "
        "(MuJoCo runtime model)"
    )
    return viewer / "viewer-config.json"


def viewer_url(resolved: dict[str, Path]) -> str:
    config = require_file(
        resolved["viewer"] / "viewer-config.json",
        "Three.js viewer config (run configure --threejs)",
    )
    try:
        relative = config.relative_to(ROOT.parent)
    except ValueError as exc:
        raise RuntimeErrorWithMessage(
            f"Three.js output must be below {ROOT.parent} for the built-in HTTP server: {config}"
        ) from exc
    return (
        "http://127.0.0.1:8000/hakoniwa-threejs-drone/index.html"
        f"?viewerConfigPath=/{relative.as_posix()}"
    )


def open_viewer(resolved: dict[str, Path]) -> str:
    url = viewer_url(resolved)
    print(f"Opening browser: {url}")
    webbrowser.open(url, new=2)
    return url


def materialize_assembly_recipe(
    assembly: Path,
    catalogs: Path,
    output: Path,
    foundation_python: Path,
    generator_env: dict[str, str],
) -> Path:
    """Project an Assembly Graph once for the existing Python Generator."""
    output.mkdir(parents=True, exist_ok=True)
    recipe_path = output / "assembly-projected-recipe.yaml"
    run(
        [
            str(foundation_python), "-m", "fpv_drone_generator.cli",
            "--catalogs", str(catalogs.resolve()),
            "project-assembly", str(assembly.resolve()), "--output", str(recipe_path),
        ],
        cwd=ROOT,
        env=generator_env,
    )
    return recipe_path


def tuning_input_digest(vehicle_dir: Path) -> str:
    """Identify one frozen vehicle/controller input set for PID tuning."""
    digest = hashlib.sha256()
    for filename in ("drone_config_0.json", "drone.xml", "control-param.txt"):
        path = require_file(vehicle_dir / filename, f"PID tuning input {filename}")
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def tuning_runner(drone_pro: Path) -> Path:
    return drone_pro / "src" / "cmake-build" / "tuning" / "src" / "mujoco_pid_tuning_runner"


def tuning_marker(resolved: dict[str, Path]) -> Path:
    return resolved["runtime"] / "pid-tuning-profile.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_verified_config(source: Path) -> None:
    receipt_path = require_file(source.parent / "receipt.json", "verified FPV config receipt")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    files = receipt.get("files")
    if not isinstance(files, dict):
        raise RuntimeErrorWithMessage(f"verified FPV config receipt has no files: {receipt_path}")
    for filename in ("drone.xml", "drone_config_0.json", "control-param.txt"):
        path = require_file(source / filename, f"verified FPV config {filename}")
        key = f"drone-config/{filename}"
        expected = files.get(key, {}).get("sha256")
        if not isinstance(expected, str) or sha256_file(path) != expected:
            raise RuntimeErrorWithMessage(f"verified FPV config hash mismatch: {path}")


def materialize_verified_config(source: Path, vehicle_dir: Path) -> None:
    source = source.resolve()
    validate_verified_config(source)
    vehicle_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source / "drone.xml", vehicle_dir / "drone.xml")
    shutil.copy2(source / "control-param.txt", vehicle_dir / "control-param.txt")
    config = json.loads((source / "drone_config_0.json").read_text(encoding="utf-8"))
    config["components"]["droneDynamics"]["mujoco"]["modelPath"] = str(
        vehicle_dir / "drone.xml"
    )
    (vehicle_dir / "drone_config_0.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )


def discover_verified_config(recipe: Path, world: Path, assembly: Path | None = None) -> Path | None:
    """Find the reviewed config for a Recipe, or for the Recipe projected from an Assembly."""
    recipe = recipe.resolve()
    world = world.resolve()
    matches: list[Path] = []
    for receipt_path in sorted((ROOT / "verified-configs").glob("*/receipt.json")):
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        source_recipe = receipt.get("source_recipe")
        source_world = receipt.get("source_world")
        inputs = receipt.get("inputs", {})
        if not isinstance(source_recipe, str) or not isinstance(source_world, str):
            continue
        if assembly is None:
            if (ROOT / source_recipe).resolve() != recipe:
                continue
        else:
            # A projected Recipe lives in the build output, so identify it by
            # its source Assembly; the SHA-256 check below still pins content.
            source_assembly = receipt.get("source_assembly")
            if not isinstance(source_assembly, str) or (ROOT / source_assembly).resolve() != assembly.resolve():
                continue
        if (ROOT / source_world).resolve() != world:
            continue
        if inputs.get("recipe_sha256") != sha256_file(recipe):
            continue
        if inputs.get("world_sha256") != sha256_file(world):
            continue
        matches.append(receipt_path.parent / "drone-config")
    if len(matches) > 1:
        raise RuntimeErrorWithMessage(
            f"multiple verified FPV configs match recipe/world: {', '.join(map(str, matches))}"
        )
    return matches[0] if matches else None


def restore_verified_config(args: argparse.Namespace) -> int:
    """Restore one reviewed vehicle/controller snapshot into a runtime package."""
    resolved = paths(args)
    source = args.verified_config.resolve()
    materialize_verified_config(source, resolved["vehicle"])
    print(f"Restored verified FPV drone config: {source}")
    print(f"Runtime vehicle directory: {resolved['vehicle']}")
    return 0


def materialize_tuning_inputs(vehicle_dir: Path, output_dir: Path) -> Path:
    """Create ignored, CSV-enabled inputs expected by Drone PRO evaluators."""
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(require_file(vehicle_dir / "drone.xml", "generated drone.xml"), output_dir / "drone.xml")
    shutil.copy2(
        require_file(vehicle_dir / "control-param.txt", "generated control-param.txt"),
        output_dir / "control-param.txt",
    )
    config = json.loads(
        require_file(vehicle_dir / "drone_config_0.json", "generated drone_config_0.json")
        .read_text(encoding="utf-8")
    )
    config["simulation"]["logging"] = {"mode": "csv"}
    config["simulation"]["logOutputDirectory"] = "."
    config["simulation"].setdefault("logOutput", {"sensors": {}, "mavlink": {}})
    config["components"]["droneDynamics"]["mujoco"]["modelPath"] = "drone.xml"
    # Hover/Angle tuning starts in free flight.  The Drone PRO angle tuning
    # path controls vertical speed and does not consume the scenario's
    # prepare.target_altitude_m as a takeoff command.
    position = config["components"]["droneDynamics"].setdefault(
        "position_meter", [0.0, 0.0, 0.0]
    )
    if len(position) != 3:
        raise RuntimeErrorWithMessage("droneDynamics.position_meter must have 3 elements")
    position[2] = -FPV_TUNING_INITIAL_ALTITUDE_M
    # The offline tuning runner drives the built-in TuningController, not the
    # interactive RadioController used by PS5 flight. This adaptation exists
    # only in the ignored tuning input copy.
    config["controller"] = {
        "moduleDirectory": "../drone_control/cmake-build/workspace/TuningController",
        "moduleName": "TuningController",
        "paramText": "",
        "paramFilePath": "control-param.txt",
        "backendType": "adapter-hakoniwa",
        "direct_rotor_control": False,
        "mixer": {
            "enable": True,
            "vendor": "None",
            "enableDebugLog": False,
            "enableErrorLog": False,
        },
    }
    (output_dir / "drone_config_0.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    return output_dir


def tuning_audit(args: argparse.Namespace) -> int:
    """Record and validate the frozen plant/controller contract before tuning."""
    resolved = paths(args)
    foundation_python = require_file(args.foundation_python.absolute(), "Foundation Python")
    output = resolved["vehicle"] / "tuning-input-audit.json"
    run(
        [
            str(foundation_python), str(ROOT / "tools" / "fpv-tuning-audit.py"),
            str(resolved["vehicle"]), "--output", str(output),
        ],
        cwd=ROOT,
    )
    print(f"Tuning inputs are internally consistent: {output}")
    return 0


def configure_fpv_hover_profile(profile: Path, hover_trials: int) -> None:
    """Apply the conservative FPV hover seed after Drone PRO creates a profile.

    The canonical X500 template intentionally fixes the vertical-speed D term
    to zero.  That is too restrictive for a light, low-inertia FPV vehicle,
    so retain the same TuningController pipeline while making D searchable.
    """
    if hover_trials <= 0:
        raise RuntimeErrorWithMessage("--hover-trials must be positive")
    seed = {
        **FPV_HOVER_ATTITUDE_BASE,
        "PID_ALT_Kp": 4.0,
        "PID_ALT_Kd": 2.0,
        "PID_ALT_SPD_Kp": 5.0,
        "PID_ALT_SPD_Ki": 0.0,
        "PID_ALT_SPD_Kd": 0.0,
    }
    controller_path = require_file(
        profile / "controller" / "controller-params.txt",
        "PID tuning profile controller parameters",
    )
    controller_path.write_text(
        apply_parameter_overrides(controller_path.read_text(encoding="utf-8"), seed),
        encoding="utf-8",
    )
    base_overrides_path = require_file(
        profile / "param-sets" / "base-overrides.json",
        "PID tuning profile base overrides",
    )
    base_overrides = json.loads(base_overrides_path.read_text(encoding="utf-8"))
    base_overrides.update(FPV_HOVER_ATTITUDE_BASE)
    base_overrides_path.write_text(
        json.dumps(base_overrides, indent=2) + "\n", encoding="utf-8"
    )
    search_path = require_file(
        profile / "search-space" / "hover-optuna.json",
        "PID tuning hover search space",
    )
    search = json.loads(search_path.read_text(encoding="utf-8"))
    parameters = search["parameters"]
    parameters["PID_ROLL_Kp"] = {"value": FPV_HOVER_ATTITUDE_BASE["PID_ROLL_Kp"]}
    parameters["PID_ROLL_Ki"] = {"value": FPV_HOVER_ATTITUDE_BASE["PID_ROLL_Ki"]}
    parameters["PID_ROLL_Kd"] = {"value": FPV_HOVER_ATTITUDE_BASE["PID_ROLL_Kd"]}
    parameters["PID_PITCH_Kp"] = {"mirror_of": "PID_ROLL_Kp"}
    parameters["PID_PITCH_Ki"] = {"mirror_of": "PID_ROLL_Ki"}
    parameters["PID_PITCH_Kd"] = {"mirror_of": "PID_ROLL_Kd"}
    parameters["PID_ALT_SPD_Kp"] = {"min": 3.0, "max": 8.0, "step": 0.5}
    parameters["PID_ALT_SPD_Ki"] = {"value": 0.0}
    parameters["PID_ALT_SPD_Kd"] = {"min": 0.0, "max": 2.0, "step": 0.25}
    search["description"] = (
        "FPV staged hover search: hold the flight-proven attitude loops fixed "
        "and explore only vertical-speed proportional and derivative gains."
    )
    search_path.write_text(json.dumps(search, indent=2) + "\n", encoding="utf-8")
    score_path = require_file(
        profile / "score" / "hover-score.json", "PID tuning hover score configuration"
    )
    score = json.loads(score_path.read_text(encoding="utf-8"))
    entry_gate = next(
        (gate for gate in score.get("hard_gates", []) if gate.get("id") == "hover_entry_time"),
        None,
    )
    if entry_gate is None:
        raise RuntimeErrorWithMessage(f"hover_entry_time hard gate is absent: {score_path}")
    entry_gate["value"] = FPV_HOVER_ENTRY_MAX_SEC
    entry_term = next(
        (term for term in score.get("score_terms", []) if term.get("id") == "hover_entry_time"),
        None,
    )
    if entry_term is not None:
        entry_term["worst"] = FPV_HOVER_ENTRY_MAX_SEC
    score_path.write_text(json.dumps(score, indent=2) + "\n", encoding="utf-8")
    manifest_path = require_file(profile / "manifests" / "01-hover.json", "PID tuning hover manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    hover_phase = next(
        (phase for phase in manifest["phases"] if phase.get("name") == "hover"), None
    )
    if hover_phase is None:
        raise RuntimeErrorWithMessage(f"hover phase is absent from tuning manifest: {manifest_path}")
    hover_phase.setdefault("args", {})["trials"] = hover_trials
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def configure_fpv_angle_profile(profile: Path, angle_trials: int, *, refine: bool = False) -> None:
    """Configure the Angle trial count and optional FPV refinement search."""
    if angle_trials <= 0:
        raise RuntimeErrorWithMessage("--angle-trials must be positive")
    if refine:
        search_path = require_file(
            profile / "search-space" / "angle-optuna.json",
            "PID tuning angle search space",
        )
        search = json.loads(search_path.read_text(encoding="utf-8"))
        parameters = search["parameters"]
        parameters["PID_ROLL_RATE_Kp"] = {"min": 0.1, "max": 0.6, "step": 0.05}
        parameters["PID_ROLL_RATE_Ki"] = {"min": 0.0, "max": 0.2, "step": 0.02}
        parameters["PID_ROLL_RATE_Kd"] = {"min": 0.0, "max": 0.03, "step": 0.005}
        parameters["PID_ROLL_Kp"] = {"min": 3.0, "max": 10.0, "step": 1.0}
        parameters["PID_ROLL_Ki"] = {"min": 0.0, "max": 1.0, "step": 0.25}
        parameters["PID_ROLL_Kd"] = {"min": 0.0, "max": 1.5, "step": 0.25}
        search["description"] = (
            "FPV Angle safe search including the flight-proven 5-inch gain region; "
            "candidate acceptance also requires the FPV flight-envelope gate."
        )
        search_path.write_text(json.dumps(search, indent=2) + "\n", encoding="utf-8")
    manifest_path = require_file(profile / "manifests" / "02-angle.json", "PID tuning angle manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    angle_phase = next(
        (phase for phase in manifest["phases"] if phase.get("name") == "angle_roll"), None
    )
    if angle_phase is None:
        raise RuntimeErrorWithMessage(f"angle_roll phase is absent from tuning manifest: {manifest_path}")
    angle_phase.setdefault("args", {})["trials"] = angle_trials
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _read_csv_window(path: Path, start_sec: float) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = [
            row for row in csv.DictReader(stream)
            if row.get("timestamp")
            and all(value not in (None, "") for value in row.values())
            and float(row["timestamp"]) / 1e6 >= start_sec
        ]
    if not rows:
        raise RuntimeErrorWithMessage(f"no tuning samples after {start_sec}s: {path}")
    return rows


def evaluate_fpv_trial_flight_gate(trial_dir: Path, drone_pro: Path) -> dict[str, object]:
    """Validate that a Drone PRO trial ran airborne without actuator saturation."""
    scenarios = sorted((trial_dir / "suite" / "generated_scenarios").glob("*.json"))
    if not scenarios:
        raise RuntimeErrorWithMessage(f"generated tuning scenarios not found: {trial_dir}")

    results: list[dict[str, object]] = []
    for scenario_path in scenarios:
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        output_value = scenario.get("logging", {}).get("output_dir")
        if not output_value:
            continue
        output_dir = Path(output_value)
        if not output_dir.is_absolute():
            output_dir = drone_pro / output_dir
        start_sec = float(scenario.get("prepare", {}).get("settle_time_sec", 0.0))
        dynamics_path = require_file(output_dir / "drone_log0" / "drone_dynamics.csv", "tuning dynamics CSV")
        dynamics = _read_csv_window(dynamics_path, start_sec)
        altitudes = [-float(row["Z"]) for row in dynamics]
        collision_counts = [int(float(row.get("collided_counts", "0"))) for row in dynamics]

        motor_rows = 0
        saturated_rows = 0
        rotor_paths = sorted((output_dir / "drone_log0").glob("log_rotor_*.csv"))
        if not rotor_paths:
            raise RuntimeErrorWithMessage(f"tuning rotor CSVs not found: {output_dir}")
        for rotor_path in rotor_paths:
            for row in _read_csv_window(rotor_path, start_sec):
                duty = float(row["Duty"])
                motor_rows += 1
                if duty <= 1e-6 or duty >= 1.0 - 1e-6:
                    saturated_rows += 1
        saturation_ratio = saturated_rows / motor_rows
        collision_delta = max(collision_counts) - min(collision_counts)
        minimum_altitude = min(altitudes)
        passed = (
            minimum_altitude >= FPV_TUNING_MIN_ALTITUDE_M
            and collision_delta == 0
            and saturation_ratio <= FPV_TUNING_MAX_MOTOR_SATURATION_RATIO
        )
        results.append({
            "scenario": scenario_path.name,
            "minimum_altitude_m": minimum_altitude,
            "maximum_altitude_m": max(altitudes),
            "collision_count_delta": collision_delta,
            "motor_saturation_ratio": saturation_ratio,
            "saturated_motor_samples": saturated_rows,
            "motor_samples": motor_rows,
            "passed": passed,
        })

    if not results:
        raise RuntimeErrorWithMessage(f"no logged tuning scenarios found: {trial_dir}")
    return {
        "passed": all(bool(result["passed"]) for result in results),
        "limits": {
            "minimum_altitude_m": FPV_TUNING_MIN_ALTITUDE_M,
            "maximum_motor_saturation_ratio": FPV_TUNING_MAX_MOTOR_SATURATION_RATIO,
            "maximum_collision_count_delta": 0,
        },
        "scenarios": results,
    }


def select_fpv_tuning_candidate(
    profile: Path, phase: str, drone_pro: Path, runtime_dir: Path
) -> Path:
    phase_dir = profile / "results" / "autotune" / (
        "hover" if phase == "hover" else "angle_roll/roll"
    )
    candidates: list[tuple[float, dict[str, object], Path, dict[str, object]]] = []
    trial_reports: list[dict[str, object]] = []
    for breakdown_path in sorted(phase_dir.glob("trial_*/score-breakdown.json")):
        breakdown = json.loads(breakdown_path.read_text(encoding="utf-8"))
        existing_gate = bool(breakdown.get("details", {}).get("hard_gate_passed", False))
        flight_gate = evaluate_fpv_trial_flight_gate(breakdown_path.parent, drone_pro)
        report = {
            "trial": breakdown_path.parent.name,
            "score": float(breakdown["score"]),
            "drone_pro_hard_gate_passed": existing_gate,
            "fpv_flight_gate": flight_gate,
        }
        trial_reports.append(report)
        if existing_gate and flight_gate["passed"]:
            candidates.append((float(breakdown["score"]), breakdown, breakdown_path.parent, flight_gate))

    report_path = runtime_dir / f"pid-tuning-{phase}-flight-gate.json"
    selection_report: dict[str, object] = {
        "schema_version": 1,
        "phase": phase,
        "trials": trial_reports,
    }
    if not candidates:
        selection_report["status"] = "failed"
        report_path.write_text(json.dumps(selection_report, indent=2) + "\n", encoding="utf-8")
        raise RuntimeErrorWithMessage(
            f"{phase} tuning produced no airborne, unsaturated candidate; review {report_path}"
        )

    score, breakdown, trial_dir, flight_gate = max(candidates, key=lambda item: item[0])
    selected_path = runtime_dir / f"pid-tuning-{phase}-selected-params.json"
    selected_path.write_text(json.dumps(breakdown["overrides"], indent=2) + "\n", encoding="utf-8")
    selection_report.update({
        "status": "passed",
        "selected_trial": trial_dir.name,
        "selected_score": score,
        "selected_params": str(selected_path),
        "selected_flight_gate": flight_gate,
    })
    report_path.write_text(json.dumps(selection_report, indent=2) + "\n", encoding="utf-8")
    return selected_path


def run_post_angle_hover_validation(
    profile: Path,
    selected_params: Path,
    drone_pro: Path,
    foundation_python: Path,
    runtime_dir: Path,
) -> Path:
    """Run a sustained free-flight hover after Angle candidate selection."""
    suite_runner = require_file(
        drone_pro / "tuning" / "tools" / "suites" / "run_hover_sanity.py",
        "Drone PRO hover sanity suite",
    )
    source_phase = require_file(profile / "phases" / "hover.json", "PID tuning hover phase")
    phase_payload = json.loads(source_phase.read_text(encoding="utf-8"))
    phase_payload.setdefault("simulation_model_overrides", {})["remove_floor"] = False
    phase = runtime_dir / "pid-tuning-post-angle-hover-phase.json"
    phase.write_text(json.dumps(phase_payload, indent=2) + "\n", encoding="utf-8")
    trial_dir = profile / "results" / "autotune" / "fpv-post-angle-hover" / "trial_0000"
    suite_dir = trial_dir / "suite"

    run(
        [
            str(foundation_python),
            str(suite_runner),
            "--phase", os.path.relpath(phase, drone_pro),
            "--param-overrides-json", os.path.relpath(selected_params, drone_pro),
            "--work-dir", os.path.relpath(suite_dir, drone_pro),
            "--duration-sec", "15",
            "--settle-time-sec", "2",
            "--target-altitude-m", str(FPV_TUNING_INITIAL_ALTITUDE_M),
            "--eval-start-time-sec", "2",
            "--eval-sustain-sec", "10",
            "--vz-threshold", "0.15",
            "--roll-threshold-deg", "2",
            "--pitch-threshold-deg", "2",
            "--no-plot",
        ],
        cwd=drone_pro,
    )
    hover_evaluation_path = require_file(
        suite_dir / "hover-sanity-eval.json", "post-Angle hover evaluation"
    )
    hover_evaluation = json.loads(hover_evaluation_path.read_text(encoding="utf-8"))
    flight_gate = evaluate_fpv_trial_flight_gate(trial_dir, drone_pro)
    passed = hover_evaluation.get("status") == "PASS" and bool(flight_gate["passed"])
    report_path = runtime_dir / "pid-tuning-post-angle-hover.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "passed" if passed else "failed",
                "selected_params": str(selected_params),
                "hover_evaluation": hover_evaluation,
                "fpv_flight_gate": flight_gate,
                "requirements": {
                    "duration_sec": 15,
                    "evaluation_start_sec": 2,
                    "sustain_sec": 10,
                    "maximum_abs_vertical_speed_m_s": 0.15,
                    "maximum_abs_roll_deg": 2,
                    "maximum_abs_pitch_deg": 2,
                },
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    if not passed:
        raise RuntimeErrorWithMessage(
            f"Angle candidate failed the sustained post-Angle hover validation; review {report_path}"
        )
    return report_path


def tune_build(args: argparse.Namespace) -> int:
    print("NOTICE: PID auto-tuning requires a valid Hakoniwa Drone PRO license.")
    drone_pro = args.drone_pro_root.resolve()
    foundation_python = require_file(args.foundation_python.absolute(), "Foundation Python")
    build_config = require_file(
        drone_pro / "config" / "build" / "hakoniwa-build-pid-tuning.yaml",
        "Drone PRO PID tuning build config",
    )
    run(
        [str(foundation_python), "tools/hako.py", "doctor", "--config", str(build_config)],
        cwd=drone_pro,
    )
    run(
        [str(foundation_python), "tools/hako.py", "build", "--config", str(build_config)],
        cwd=drone_pro,
    )
    if sys.platform == "darwin":
        run(
            [
                "bash", "tools/link-mujoco-mac.bash", "src/cmake-build/tuning/src",
                "--lib-dir", str(drone_pro / "vendor" / "mujoco" / "lib"),
            ],
            cwd=drone_pro,
        )
    require_file(tuning_runner(drone_pro), "Drone PRO PID tuning runner")
    print(f"PID tuning runner is ready: {tuning_runner(drone_pro)}")
    return 0


def tune_prepare(args: argparse.Namespace) -> int:
    print("NOTICE: PID auto-tuning requires a valid Hakoniwa Drone PRO license.")
    resolved = paths(args)
    drone_pro = args.drone_pro_root.resolve()
    foundation_python = require_file(args.foundation_python.absolute(), "Foundation Python")
    require_file(tuning_runner(drone_pro), "Drone PRO PID tuning runner (run tune-build first)")

    vehicle_dir = resolved["vehicle"]
    tuning_audit(args)
    source_digest = tuning_input_digest(vehicle_dir)
    tuning_inputs = materialize_tuning_inputs(
        vehicle_dir, resolved["runtime"] / "pid-tuning-input"
    )
    profile_digest = tuning_input_digest(tuning_inputs)
    # The suffix separates the FPV-specific hover tuning policy from the
    # unmodified canonical template, and prevents stale Optuna trials from a
    # previous policy contaminating this run.
    profile = drone_pro / "work" / "pid-tuning" / f"fpv-{resolved['output'].name}-{profile_digest[:12]}-flight-gate-v5"
    creator = require_file(
        drone_pro / "tuning" / "tools" / "create_pid_tuning_profile.py",
        "Drone PRO PID tuning profile creator",
    )
    run(
        [
            str(foundation_python), str(creator), str(drone_pro), "hakoniwa", str(profile),
            "--drone-config", str(tuning_inputs / "drone_config_0.json"),
            "--controller-param-base", str(tuning_inputs / "control-param.txt"),
        ],
        cwd=drone_pro,
    )
    configure_fpv_hover_profile(profile, args.hover_trials)
    configure_fpv_angle_profile(profile, args.angle_trials, refine=args.angle_refine)
    marker = {
        "schema_version": 2,
        "adapter": "hakoniwa",
        "source_input_sha256": source_digest,
        "profile_input_sha256": profile_digest,
        "profile_dir": str(profile),
        "profile_env": str(profile / "profile.env"),
        "hover_manifest": str(profile / "manifests" / "01-hover.json"),
        "angle_manifest": str(profile / "manifests" / "02-angle.json"),
        "hover_trials": args.hover_trials,
        "angle_trials": args.angle_trials,
        "hover_policy": "fpv-flight-gate-v5: fixed proven attitude baseline, 5s airborne entry gate, collision and motor-saturation rejection",
        "policy": "Only FPV flight-gate-approved candidates may advance or be applied.",
    }
    tuning_marker(resolved).write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared frozen FPV PID tuning profile: {profile}")
    print("Next: python3.12 tools/fpv.py tune-hover")
    return 0


def tune_phase(args: argparse.Namespace, phase: str) -> int:
    print("NOTICE: PID auto-tuning requires a valid Hakoniwa Drone PRO license.")
    resolved = paths(args)
    drone_pro = args.drone_pro_root.resolve()
    foundation_python = require_file(args.foundation_python.absolute(), "Foundation Python")
    require_file(tuning_runner(drone_pro), "Drone PRO PID tuning runner")
    marker_path = require_file(tuning_marker(resolved), "FPV PID tuning profile (run tune-prepare first)")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    current_digest = tuning_input_digest(resolved["vehicle"])
    if current_digest != marker["source_input_sha256"]:
        raise RuntimeErrorWithMessage(
            "generated vehicle changed after tune-prepare; create a new frozen tuning profile"
        )
    if phase == "angle":
        configure_fpv_angle_profile(
            Path(marker["profile_dir"]), args.angle_trials, refine=args.angle_refine
        )
    manifest = require_file(Path(marker[f"{phase}_manifest"]), f"{phase} tuning manifest")
    pipeline = require_file(
        drone_pro / "tuning" / "tools" / "autotune" / "run_autotune_pipeline.py",
        "Drone PRO autotune pipeline",
    )
    env = os.environ.copy()
    mpl_dir = resolved["runtime"] / "matplotlib"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    env["MPLCONFIGDIR"] = str(mpl_dir)
    run(
        [str(foundation_python), str(pipeline), "--manifest", str(manifest)],
        cwd=drone_pro,
        env=env,
    )
    profile = Path(marker["profile_dir"])
    report_path = profile / "results" / "autotune" / "pipeline-report.json"
    report = json.loads(require_file(report_path, "PID tuning pipeline report").read_text(encoding="utf-8"))
    if report.get("status") not in ("completed", "completed_with_warnings"):
        failed_phase = report.get("failed_phase") or phase
        raise RuntimeErrorWithMessage(
            f"{phase} tuning did not produce an accepted candidate "
            f"(status={report.get('status')}, failed_phase={failed_phase}); review {report_path}"
        )
    selected_params = select_fpv_tuning_candidate(profile, phase, drone_pro, resolved["runtime"])
    if phase == "angle":
        hover_report = run_post_angle_hover_validation(
            profile, selected_params, drone_pro, foundation_python, resolved["runtime"]
        )
        marker["post_angle_hover_report"] = str(hover_report)
    # The next Drone PRO phase inherits final-params.json. Promote only the
    # candidate accepted by the FPV-side flight envelope gate.
    selected_overrides = json.loads(selected_params.read_text(encoding="utf-8"))
    (profile / "final-params.json").write_text(
        json.dumps(selected_overrides, indent=2) + "\n", encoding="utf-8"
    )
    marker[f"{phase}_selected_params"] = str(selected_params)
    marker_path.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    print(f"{phase.capitalize()} tuning finished. Review: {profile / 'results' / 'autotune'}")
    print(f"FPV flight-gate-approved parameters: {selected_params}")
    if phase == "hover":
        print("Only after reviewing the hover gates and plots: python3.12 tools/fpv.py tune-angle")
    return 0


def apply_parameter_overrides(text: str, overrides: dict[str, float]) -> str:
    remaining = dict(overrides)
    output: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            output.append(line)
            continue
        key = stripped.split(maxsplit=1)[0]
        if key in remaining:
            output.append(f"{key:<44} {remaining.pop(key):.12g}")
        else:
            output.append(line)
    for key in sorted(remaining):
        output.append(f"{key:<44} {remaining[key]:.12g}")
    return "\n".join(output) + "\n"


def tune_apply(args: argparse.Namespace) -> int:
    print("NOTICE: PID auto-tuning requires a valid Hakoniwa Drone PRO license.")
    resolved = paths(args)
    marker_path = require_file(tuning_marker(resolved), "FPV PID tuning profile")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    profile = Path(marker["profile_dir"])
    report_path = require_file(
        profile / "results" / "autotune" / "pipeline-report.json",
        "PID tuning pipeline report",
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("status") not in ("completed", "completed_with_warnings"):
        raise RuntimeErrorWithMessage(f"latest PID phase is not accepted: {report_path}")
    selected_value = marker.get("angle_selected_params")
    if not selected_value:
        raise RuntimeErrorWithMessage(
            "FPV Angle flight-gate-approved parameters are absent; run tune-angle first"
        )
    final_params_path = require_file(Path(selected_value), "FPV flight-gate-approved parameter set")
    overrides = json.loads(final_params_path.read_text(encoding="utf-8"))
    runtime_param = require_file(
        resolved["vehicle"] / "control-param.txt", "FPV runtime controller parameters"
    )
    runtime_param.write_text(
        apply_parameter_overrides(runtime_param.read_text(encoding="utf-8"), overrides),
        encoding="utf-8",
    )
    receipt = {
        "schema_version": 1,
        "profile_dir": str(profile),
        "pipeline_report": str(report_path),
        "source_final_params": str(final_params_path),
        "applied_parameter_count": len(overrides),
        "scope": "build runtime only; configure restores generated initial values",
    }
    (resolved["runtime"] / "pid-tuning-applied.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Applied {len(overrides)} tuned parameters to: {runtime_param}")
    print("Run PS5 validation with: python3.12 tools/fpv.py start")
    print("Restore generated defaults with: python3.12 tools/fpv.py configure")
    return 0


def native_library_paths(
    install_prefix: Path, drone_core: Path, drone_core_bin: Path, *, windows: bool | None = None
) -> list[Path]:
    """Library search paths for the Launcher's lib_path (PATH on Windows)."""
    if not ((os.name == "nt") if windows is None else windows):
        return [install_prefix / "lib", drone_core_bin]
    # Windows resolves DLLs through PATH: Foundation DLLs install to bin/,
    # MuJoCo ships mujoco.dll in vendor/mujoco/bin, and glfw3.dll comes from
    # the vcpkg root registered with foundation.py toolchain.
    paths = [install_prefix / "bin", install_prefix / "lib", drone_core_bin, drone_core / "vendor" / "mujoco" / "bin"]
    toolchain = install_prefix.parent / "config" / "toolchain.json"
    if toolchain.is_file():
        vcpkg_root = json.loads(toolchain.read_text(encoding="utf-8")).get("vcpkg_root")
        if vcpkg_root:
            paths.append(Path(vcpkg_root) / "installed" / "x64-windows" / "bin")
    return paths


def configure(args: argparse.Namespace) -> int:
    resolved = paths(args)
    drone_core = args.drone_core_root.resolve()
    drone_core_bin = args.drone_core_bin.resolve()
    # Keep the Foundation interpreter path itself. Resolving its symlink would
    # bypass the virtual environment and lose Foundation-installed packages.
    foundation_python = require_file(args.foundation_python.absolute(), "Foundation Python")
    service = require_file(
        drone_core_bin / f"{NATIVE_PREFIX}main_hako_drone_service{EXECUTABLE_SUFFIX}",
        "Drone Core service (run tools/fpv-drone-core.py prepare; see --drone-core-bin)",
    )
    pdudef = require_file(drone_core / "config" / "pdudef" / "drone-pdudef-1.json", "Drone PDU definition")
    rc_config = require_file(args.rc_config.resolve(), "RC config")
    require_file(drone_core / "drone_api" / "rc" / "rc-custom.py", "RC client")
    rc_bootstrap = require_file(ROOT / "tools" / "fpv_rc_bootstrap.py", "FPV RC bootstrap")
    threejs_root = args.threejs_root.resolve()
    business_pack_root = args.business_pack_root.resolve()
    assembly = args.assembly.resolve() if args.assembly is not None else None
    catalogs = args.catalogs.resolve()
    if assembly is not None and not args.threejs:
        raise RuntimeErrorWithMessage("--assembly requires --threejs so its Catalog visual assets are materialized")

    generator_env = os.environ.copy()
    existing_pythonpath = generator_env.get("PYTHONPATH")
    generator_env["PYTHONPATH"] = str(ROOT / "src") + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )
    effective_recipe = (
        materialize_assembly_recipe(
            assembly, catalogs, resolved["output"], foundation_python, generator_env,
        )
        if assembly is not None
        else args.recipe.resolve()
    )
    run(
        [
            str(foundation_python), "-m", "fpv_drone_generator.cli",
            "generate", str(effective_recipe), "--output", str(resolved["output"]),
            "--world", str(args.world.resolve()),
        ],
        cwd=ROOT,
        env=generator_env,
    )
    resolved["vehicle"].mkdir(parents=True, exist_ok=True)
    resolved["logs"].mkdir(parents=True, exist_ok=True)
    for filename in ("drone.xml", "control-param.json", "control-param.txt", "report.json", "bom.yaml", "resolved-components.yaml", "recipe.yaml", "world.yaml", "fpv-course.json"):
        shutil.copy2(resolved["output"] / filename, resolved["vehicle"] / filename)
    runtime_config_path = resolved["vehicle"] / "drone_config_0.json"
    runtime_config = json.loads((resolved["output"] / "drone_config.json").read_text(encoding="utf-8"))
    # Drone PRO currently resolves modelPath from the service process cwd, not
    # from the directory containing drone_config_0.json. Keep the generated
    # package portable, and adapt only the materialized runtime copy.
    runtime_config["components"]["droneDynamics"]["mujoco"]["modelPath"] = str(
        resolved["vehicle"] / "drone.xml"
    )
    runtime_config_path.write_text(json.dumps(runtime_config, indent=2) + "\n", encoding="utf-8")

    if not args.generated_defaults:
        verified_config = discover_verified_config(effective_recipe, args.world, assembly)
        if verified_config is not None:
            materialize_verified_config(verified_config, resolved["vehicle"])
            print(f"Applied verified FPV config automatically: {verified_config}")
        else:
            print("No verified FPV config matches this Recipe and World; using generated defaults.")
    else:
        print("Using generated controller defaults (--generated-defaults).")

    if args.threejs:
        materialize_threejs_viewer(
            resolved,
            threejs_root,
            assembly=assembly,
            catalogs=catalogs,
            asset_python=foundation_python,
            asset_env=generator_env,
        )

    install_prefix = workspace_foundation_install(business_pack_root)
    require_file(install_prefix / "bin" / f"hako-cmd{EXECUTABLE_SUFFIX}", "Foundation hako-cmd (run recipe.py configure)")
    launcher = {
        "version": "0.1",
        "defaults": {
            "cwd": str(ROOT),
            "stdout": str(resolved["logs"] / "${asset}.out"),
            "stderr": str(resolved["logs"] / "${asset}.err"),
            # Resolve Hakoniwa Core libraries and hako-cmd from the Foundation
            # only; a system /usr/local/hakoniwa install has incompatible ABIs.
            # mac.zip ships libhako_service_c.dylib next to its executables.
            "env": {
                "prepend": {
                    "lib_path": [str(path) for path in native_library_paths(install_prefix, drone_core, drone_core_bin)],
                    "PATH": [str(install_prefix / "bin"), str(foundation_python.parent)],
                }
            },
            "start_grace_sec": 1,
            "delay_sec": 2,
        },
        "assets": [
            {
                "name": "fpv-drone-service",
                "activation_timing": "before_start",
                "command": str(service),
                "args": [
                    str(resolved["vehicle"]), str(pdudef),
                    *(["--mujoco-viewer", "--mujoco-fpv-pip"] if args.mujoco_viewer or not args.threejs else []),
                    "--real-sleep-msec", "1",
                ],
                "cwd": str(drone_core),
                "delay_sec": 2,
            },
            {
                "name": "fpv-remote-controller",
                "activation_timing": "after_start",
                "command": str(foundation_python),
                # Materialize a neutral GameControllerOperation before handing
                # control to Drone PRO's unmodified stock RC client.
                "args": [
                    "-u", str(rc_bootstrap), str(pdudef), str(rc_config),
                    "--rc-root", str(drone_core / "drone_api" / "rc"),
                ],
                "cwd": str(ROOT),
                "depends_on": ["fpv-drone-service"],
            },
        ],
    }
    if args.threejs:
        visual_state_publisher = require_file(
            drone_core_bin / f"{NATIVE_PREFIX}drone_visual_state_publisher{EXECUTABLE_SUFFIX}",
            "Drone Core visual-state publisher (run tools/fpv-drone-core.py prepare; see --drone-core-bin)",
        )
        visual_state_config = require_file(
            drone_core / "config" / "assets" / "visual_state_publisher" / "visual_state_publisher-1.json",
            "single-drone visual-state publisher config",
        )
        web_bridge = require_file(install_prefix / "bin" / f"hakoniwa-pdu-web-bridge{EXECUTABLE_SUFFIX}", "WebBridge")
        web_bridge_config = install_prefix / "share" / "hakoniwa-pdu-bridge" / "config" / "web_bridge_fleets"
        require_file(web_bridge_config / "bridge" / "bridge.json", "WebBridge fleet config")
        assets = launcher["assets"]
        assets.insert(1, {
            "name": "fpv-visual-state-publisher",
            "activation_timing": "before_start",
            "command": str(visual_state_publisher),
            "args": [str(visual_state_config)],
            "cwd": str(drone_core),
            "depends_on": ["fpv-drone-service"],
            "delay_sec": 1,
        })
        assets.insert(2, {
            "name": "fpv-threejs-web-bridge",
            "activation_timing": "before_start",
            "command": str(web_bridge),
            "args": [
                "--config-root", str(web_bridge_config),
                "--node-name", "web_bridge_fleets_node1",
                "--delta-time-step-usec", "20000",
                "--enable-ondemand",
            ],
            "cwd": str(ROOT),
            "depends_on": ["fpv-visual-state-publisher"],
        })
        assets.append({
            "name": "fpv-threejs-http-server",
            "activation_timing": "after_start",
            "command": str(foundation_python),
            "args": ["-m", "http.server", "8000", "--bind", "127.0.0.1"],
            "cwd": str(ROOT.parent),
            "depends_on": ["fpv-threejs-web-bridge"],
        })
    resolved["launcher"].write_text(json.dumps(launcher, indent=2) + "\n", encoding="utf-8")
    print(f"Configured Angle FPV runtime: {resolved['runtime']}")
    print(f"Launcher: {resolved['launcher']}")
    if args.threejs:
        print(f"Three.js: {viewer_url(resolved)}")
    return 0


THREEJS_PORTS = {"fpv-threejs-http-server": 8000, "fpv-threejs-web-bridge": 8765}


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("0.0.0.0", port))
        except OSError:
            return True
    return False


def port_owner(port: int) -> str:
    if shutil.which("lsof") is None:
        return "unknown process"
    result = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"], capture_output=True, text=True, check=False
    )
    rows = result.stdout.splitlines()[1:]
    return ", ".join(f"{row.split()[0]} (pid {row.split()[1]})" for row in rows) or "unknown process"


def require_free_ports(launcher_path: Path) -> None:
    """Fail before launching when the Three.js HTTP or WebSocket port is taken.

    Otherwise WebBridge fails to bind and the browser shows no vehicle state.
    """
    launcher = json.loads(launcher_path.read_text(encoding="utf-8"))
    names = {asset.get("name") for asset in launcher.get("assets", [])}
    busy = [
        f"port {port} ({name}) is in use by {port_owner(port)}"
        for name, port in THREEJS_PORTS.items()
        if name in names and port_in_use(port)
    ]
    if busy:
        raise RuntimeErrorWithMessage("; ".join(busy) + ". Stop that process and run start again.")


FLIGHT_STATES = ("TakeOff", "Hovering", "Landing")


def read_parameter(path: Path, name: str) -> float | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] == name:
            return float(fields[1])
    return None


def runtime_state(resolved: dict[str, Path]) -> dict[str, str]:
    """Reconstruct the operator-visible Radio Control state from the runtime logs.

    Cross and Triangle are toggles with no on-screen feedback, so the service
    log is the only record of the current Radio Control, mode, and flight state.
    """
    start_in_hovering = read_parameter(resolved["vehicle"] / "control-param.txt", "CTRLMODE_START_IN_HOVERING")
    state = {
        "simulation": "not started",
        "radio_control": "OFF",
        "mode": "GPS",
        "flight_state": "Hovering" if start_in_hovering else "TakeOff",
        "controller": "unknown",
    }
    service_log = resolved["logs"] / "fpv-drone-service.out"
    if service_log.is_file():
        for line in service_log.read_text(encoding="utf-8", errors="replace").splitlines():
            if "start simulation" in line:
                state["simulation"] = "running"
            elif line.startswith("radio_control:"):
                state["radio_control"] = "ON" if line.split(":", 1)[1].strip() == "1" else "OFF"
            elif "Control mode changed to " in line:
                state["mode"] = line.rsplit("Control mode changed to ", 1)[1].strip()
            elif line.startswith("[STATE] ") and " -> " in line:
                target = line.rsplit(" -> ", 1)[1].strip()
                if target in FLIGHT_STATES:
                    state["flight_state"] = target
    rc_log = resolved["logs"] / "fpv-remote-controller.out"
    if rc_log.is_file():
        for line in rc_log.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("ジョイスティックの名前:"):
                state["controller"] = line.split(":", 1)[1].strip()
            elif "ジョイスティックが接続されていません" in line:
                state["controller"] = "not connected"
    return state


def print_runtime_state(resolved: dict[str, Path], launcher_state: str | None) -> None:
    state = runtime_state(resolved)
    if launcher_state != "RUNNING":
        state["simulation"] = f"stopped (launcher {launcher_state or 'unknown'})"
    print(f"Simulation    : {state['simulation']}")
    print(f"Controller    : {state['controller']}")
    print(f"Radio Control : {state['radio_control']}")
    print(f"Mode          : {state['mode']}")
    print(f"Flight state  : {state['flight_state']}")
    if state["simulation"] != "running":
        return
    if state["controller"] == "not connected":
        print("Next: connect the PS5 controller and run start again.")
    elif state["radio_control"] == "OFF":
        print("Next: press and release Cross to enable Radio Control.")
    elif state["mode"] != "ATTI":
        print("Next: press and release Triangle to switch to ATTI.")
    elif state["flight_state"] == "Landing":
        print("Landing: wait until it lands, then raise the left stick to take off again.")
    else:
        print("Ready: raise the left stick to lift off.")


def launcher_command(args: argparse.Namespace, action: str) -> int:
    resolved = paths(args)
    foundation_python = require_file(args.foundation_python.absolute(), "Foundation Python")
    require_file(resolved["launcher"], "FPV launcher (run configure first)")
    if action == "start":
        require_free_ports(resolved["launcher"])
        run([
            str(foundation_python), "-m", "hakoniwa_pdu.apps.launcher.hako_launcher",
            str(resolved["launcher"]), "--background", str(resolved["session"]),
        ], cwd=ROOT)
        print("FPV runtime started in background.")
        print(f"Session: {resolved['session']}")
        print(f"Logs: {resolved['logs']}")
        return 0
    require_file(resolved["session"], "Launcher session")
    command = [
        str(foundation_python), "-m", "hakoniwa_pdu.apps.launcher.hako_launcher_ctl",
        "status" if action == "status" else "terminate", str(resolved["session"]),
    ]
    if action != "status":
        run(command, cwd=ROOT)
        return 0
    print("+", " ".join(command), flush=True)
    result = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    print(result.stdout, end="")
    try:
        launcher_state = json.loads(result.stdout.strip().splitlines()[-1]).get("state")
    except (ValueError, IndexError, AttributeError):
        launcher_state = None
    print_runtime_state(resolved, launcher_state)
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=(
            "Configure and run the generated FPV vehicle with Hakoniwa Drone Core. "
            "PID auto-tuning (tune-*) additionally requires a licensed Hakoniwa Drone PRO checkout."
        )
    )
    result.add_argument(
        "command",
        choices=(
            "configure", "restore-verified-config", "start", "status", "stop", "open-viewer",
            "tune-build", "tune-audit", "tune-prepare", "tune-hover", "tune-angle", "tune-apply",
        ),
    )
    result.add_argument("--recipe", type=Path, default=DEFAULT_RECIPE)
    result.add_argument(
        "--assembly",
        type=Path,
        help="Assembly Graph to project and use for a Catalog-derived Three.js vehicle (requires --threejs)",
    )
    result.add_argument("--catalogs", type=Path, default=ROOT / "catalogs", help="Catalog root for --assembly")
    result.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    result.add_argument("--world", type=Path, default=DEFAULT_WORLD)
    result.add_argument("--verified-config", type=Path, default=DEFAULT_VERIFIED_CONFIG)
    result.add_argument(
        "--generated-defaults",
        action="store_true",
        help="Do not auto-apply a verified config after generation.",
    )
    result.add_argument(
        "--drone-core-root", type=Path, default=DEFAULT_DRONE_CORE,
        help="Hakoniwa Drone Core checkout (config/, drone_api/) used for configure/start/status/stop/open-viewer.",
    )
    result.add_argument(
        "--drone-core-bin", type=Path, default=DEFAULT_DRONE_CORE_BIN,
        help=(
            "Directory holding the extracted mac.zip release binaries "
            "(e.g. mac/mac-main_hako_drone_service, win/win-main_hako_drone_service.exe). "
            "Defaults to <drone-core-root>/mac."
        ),
    )
    result.add_argument(
        "--drone-pro-root", type=Path, default=DEFAULT_DRONE_PRO,
        help="Hakoniwa Drone PRO checkout used only by tune-* commands (PID auto-tuning requires a PRO license).",
    )
    result.add_argument("--threejs", action="store_true", help="Add the optional Three.js viewer runtime.")
    result.add_argument(
        "--mujoco-viewer", action="store_true",
        help="Also open the native MuJoCo Viewer with --threejs (it opens by default without --threejs).",
    )
    result.add_argument("--threejs-root", type=Path, default=DEFAULT_THREEJS_ROOT)
    result.add_argument("--business-pack-root", type=Path, default=DEFAULT_BUSINESS_PACK_ROOT)
    result.add_argument("--foundation-python", type=Path, default=DEFAULT_FOUNDATION_PYTHON)
    result.add_argument("--rc-config", type=Path, default=DEFAULT_DRONE_CORE / "drone_api" / "rc" / "rc_config" / "ps4-control.json")
    result.add_argument(
        "--hover-trials", type=int, default=40,
        help="Number of Hover trials in the FPV tuning profile (default: 40)",
    )
    result.add_argument(
        "--angle-trials", type=int, default=60,
        help="Number of Angle trials for tune-angle (default: 60)",
    )
    result.add_argument(
        "--angle-refine", action="store_true",
        help="Use the focused FPV Angle search around the best broad-search candidate",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "configure":
            return configure(args)
        if args.command == "restore-verified-config":
            return restore_verified_config(args)
        if args.command == "tune-build":
            return tune_build(args)
        if args.command == "tune-audit":
            return tuning_audit(args)
        if args.command == "tune-prepare":
            return tune_prepare(args)
        if args.command == "tune-hover":
            return tune_phase(args, "hover")
        if args.command == "tune-angle":
            return tune_phase(args, "angle")
        if args.command == "tune-apply":
            return tune_apply(args)
        if args.command == "open-viewer":
            open_viewer(paths(args))
            return 0
        return launcher_command(args, args.command)
    except (RuntimeErrorWithMessage, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
