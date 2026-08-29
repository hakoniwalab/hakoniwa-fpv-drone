#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECIPE = ROOT / "recipes" / "examples" / "5inch-fpv.yaml"
DEFAULT_OUTPUT = ROOT / "build" / "example-5inch"
DEFAULT_DRONE_PRO = ROOT.parent / "hakoniwa-drone-pro"
DEFAULT_FOUNDATION_PYTHON = ROOT.parent / "hakoniwa-business-pack" / "work" / "foundation" / "install" / "python" / "bin" / "python3"


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
    }


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise RuntimeErrorWithMessage(f"{label} not found: {path}")
    return path


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
    source_digest = tuning_input_digest(vehicle_dir)
    tuning_inputs = materialize_tuning_inputs(
        vehicle_dir, resolved["runtime"] / "pid-tuning-input"
    )
    profile_digest = tuning_input_digest(tuning_inputs)
    profile = drone_pro / "work" / "pid-tuning" / f"fpv-{resolved['output'].name}-{profile_digest[:12]}"
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
    marker = {
        "schema_version": 1,
        "adapter": "hakoniwa",
        "source_input_sha256": source_digest,
        "profile_input_sha256": profile_digest,
        "profile_dir": str(profile),
        "profile_env": str(profile / "profile.env"),
        "hover_manifest": str(profile / "manifests" / "01-hover.json"),
        "angle_manifest": str(profile / "manifests" / "02-angle.json"),
        "policy": "Run hover and review it before running angle.",
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
    print(f"{phase.capitalize()} tuning finished. Review: {profile / 'results' / 'autotune'}")
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
    final_params_path = require_file(profile / "final-params.json", "tuned parameter set")
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


def configure(args: argparse.Namespace) -> int:
    resolved = paths(args)
    drone_pro = args.drone_pro_root.resolve()
    # Keep the Foundation interpreter path itself. Resolving its symlink would
    # bypass the virtual environment and lose Foundation-installed packages.
    foundation_python = require_file(args.foundation_python.absolute(), "Foundation Python")
    service = require_file(drone_pro / ".hako" / "install" / "bin" / "mac-main_hako_drone_service", "Drone PRO service")
    pdudef = require_file(drone_pro / "config" / "pdudef" / "drone-pdudef-1.json", "Drone PDU definition")
    rc_config = require_file(args.rc_config.resolve(), "RC config")
    require_file(drone_pro / "drone_api" / "rc" / "rc-custom.py", "RC client")

    generator_env = os.environ.copy()
    existing_pythonpath = generator_env.get("PYTHONPATH")
    generator_env["PYTHONPATH"] = str(ROOT / "src") + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )
    run(
        [
            str(foundation_python), "-m", "fpv_drone_generator.cli",
            "generate", str(args.recipe.resolve()), "--output", str(resolved["output"]),
        ],
        cwd=ROOT,
        env=generator_env,
    )
    resolved["vehicle"].mkdir(parents=True, exist_ok=True)
    resolved["logs"].mkdir(parents=True, exist_ok=True)
    for filename in ("drone.xml", "control-param.json", "control-param.txt", "report.json", "bom.yaml", "resolved-components.yaml", "recipe.yaml"):
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

    launcher = {
        "version": "0.1",
        "defaults": {
            "cwd": str(ROOT),
            "stdout": str(resolved["logs"] / "${asset}.out"),
            "stderr": str(resolved["logs"] / "${asset}.err"),
            "env": {"prepend": {"lib_path": ["/usr/local/hakoniwa/lib"], "PATH": ["/usr/local/hakoniwa/bin"]}},
            "start_grace_sec": 1,
            "delay_sec": 2,
        },
        "assets": [
            {
                "name": "fpv-drone-service",
                "activation_timing": "before_start",
                "command": str(service),
                "args": [str(resolved["vehicle"]), str(pdudef), "--mujoco-viewer", "--real-sleep-msec", "1"],
                "cwd": str(drone_pro),
                "delay_sec": 2,
            },
            {
                "name": "fpv-remote-controller",
                "activation_timing": "after_start",
                "command": str(foundation_python),
                # Unbuffered output keeps joystick discovery and button-event
                # diagnostics visible in the Launcher log.
                "args": ["-u", "-m", "rc-custom", str(pdudef), str(rc_config)],
                "cwd": str(drone_pro / "drone_api" / "rc"),
                "depends_on": ["fpv-drone-service"],
            },
        ],
    }
    resolved["launcher"].write_text(json.dumps(launcher, indent=2) + "\n", encoding="utf-8")
    print(f"Configured Angle FPV runtime: {resolved['runtime']}")
    print(f"Launcher: {resolved['launcher']}")
    return 0


def launcher_command(args: argparse.Namespace, action: str) -> int:
    resolved = paths(args)
    foundation_python = require_file(args.foundation_python.absolute(), "Foundation Python")
    require_file(resolved["launcher"], "FPV launcher (run configure first)")
    if action == "start":
        run([
            str(foundation_python), "-m", "hakoniwa_pdu.apps.launcher.hako_launcher",
            str(resolved["launcher"]), "--background", str(resolved["session"]),
        ], cwd=ROOT)
        print("FPV runtime started in background.")
        print(f"Session: {resolved['session']}")
        print(f"Logs: {resolved['logs']}")
        return 0
    require_file(resolved["session"], "Launcher session")
    run([
        str(foundation_python), "-m", "hakoniwa_pdu.apps.launcher.hako_launcher_ctl",
        "status" if action == "status" else "terminate", str(resolved["session"]),
    ], cwd=ROOT)
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Configure and run the generated FPV vehicle with Hakoniwa Drone PRO.")
    result.add_argument(
        "command",
        choices=(
            "configure", "start", "status", "stop",
            "tune-build", "tune-prepare", "tune-hover", "tune-angle", "tune-apply",
        ),
    )
    result.add_argument("--recipe", type=Path, default=DEFAULT_RECIPE)
    result.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    result.add_argument("--drone-pro-root", type=Path, default=DEFAULT_DRONE_PRO)
    result.add_argument("--foundation-python", type=Path, default=DEFAULT_FOUNDATION_PYTHON)
    result.add_argument("--rc-config", type=Path, default=DEFAULT_DRONE_PRO / "drone_api" / "rc" / "rc_config" / "ps4-control.json")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "configure":
            return configure(args)
        if args.command == "tune-build":
            return tune_build(args)
        if args.command == "tune-prepare":
            return tune_prepare(args)
        if args.command == "tune-hover":
            return tune_phase(args, "hover")
        if args.command == "tune-angle":
            return tune_phase(args, "angle")
        if args.command == "tune-apply":
            return tune_apply(args)
        return launcher_command(args, args.command)
    except (RuntimeErrorWithMessage, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
