#!/usr/bin/env python3
"""Windows portable package tool for the Master3X FPV drone.

Business Pack's tools/package_portable_workspace.py drives this tool through
portable/windows-profile.json:

  collect   source Workspace: gather runtime DLLs that only exist in the
            developer's vcpkg (glfw3.dll for the Drone Core service)
  doctor    source Workspace: fail before packaging when an input is missing
  prepare   package: relocate the Core mmap path and configure the Master3X
            Three.js runtime for the current extraction directory (once per
            extraction directory)
  start     package: prepare, start the simulation, and open the browser viewer
  status    package: show the Launcher and flight state
  stop      package: stop the simulation
"""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT.parent
BUSINESS_PACK = PACKAGE_ROOT / "hakoniwa-business-pack"
FOUNDATION = BUSINESS_PACK / "work" / "foundation"
DRONE_CORE = PACKAGE_ROOT / "hakoniwa-drone-core"
FPV = ROOT / "tools" / "fpv.py"
ASSEMBLY = ROOT / "recipes" / "examples" / "master3x-visual-demo.assembly.json"
VERIFIED_CONFIG = ROOT / "verified-configs" / "master3x-angle"
OUTPUT = ROOT / "build" / "portable-master3x"
STAMP = OUTPUT / "portable-layout.json"
# fpv.py adds this directory to the Launcher library path when it exists.
RUNTIME_BIN = ROOT / "build" / "portable-runtime" / "bin"
# DLLs the Drone Core Windows executables load from the developer's vcpkg.
RUNTIME_DLLS = ("glfw3.dll",)
LAYOUT_VERSION = 1
VIEWER_WAIT_SEC = 60.0


class PortableError(RuntimeError):
    pass


def _fpv(*arguments: str) -> list[str]:
    return [sys.executable, str(FPV), *arguments, "--output", str(OUTPUT), "--foundation-python", sys.executable]


def _run(command: list[str]) -> int:
    print("+", subprocess.list2cmdline(command), flush=True)
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def vcpkg_bin(foundation: Path = FOUNDATION) -> Path:
    toolchain = foundation / "config" / "toolchain.json"
    try:
        root = json.loads(toolchain.read_text(encoding="utf-8")).get("vcpkg_root")
    except (OSError, json.JSONDecodeError) as exc:
        raise PortableError(
            f"cannot read the Foundation toolchain {toolchain}: {exc}; run foundation.py toolchain first"
        ) from exc
    if not root:
        raise PortableError(f"{toolchain} has no vcpkg_root")
    return Path(root) / "installed" / "x64-windows" / "bin"


def collect(source_bin: Path | None = None, destination: Path = RUNTIME_BIN) -> list[Path]:
    source_bin = source_bin or vcpkg_bin()
    destination.mkdir(parents=True, exist_ok=True)
    collected = []
    for name in RUNTIME_DLLS:
        source = source_bin / name
        if not source.is_file():
            raise PortableError(f"runtime DLL not found: {source}")
        shutil.copy2(source, destination / name)
        collected.append(destination / name)
        print(f"Collected {name} from {source_bin}")
    return collected


def required_inputs() -> dict[str, Path]:
    install = FOUNDATION / "install"
    return {
        "Drone Core service": DRONE_CORE / "win" / "win-main_hako_drone_service.exe",
        "Drone Core visual-state publisher": DRONE_CORE / "win" / "win-drone_visual_state_publisher.exe",
        "MuJoCo DLL": DRONE_CORE / "vendor" / "mujoco" / "bin" / "mujoco.dll",
        "Master3X assembly": ASSEMBLY,
        "Master3X verified config": VERIFIED_CONFIG / "drone-config",
        "Foundation hako-cmd": install / "bin" / "hako-cmd.exe",
        "Foundation WebBridge": install / "bin" / "hakoniwa-pdu-web-bridge.exe",
        "Three.js viewer": PACKAGE_ROOT / "hakoniwa-threejs-drone" / "index.html",
        **{f"collected {name}": RUNTIME_BIN / name for name in RUNTIME_DLLS},
    }


def doctor() -> int:
    missing = [f"{label}: {path}" for label, path in required_inputs().items() if not path.exists()]
    for line in missing:
        print(f"MISSING {line}")
    if missing:
        print("Run the Windows FPV Quick Start (recipe.py configure, fpv-drone-core.py prepare) and collect first.")
        return 1
    print("FPV portable inputs: OK")
    return 0


def relocate_core_config(foundation: Path = FOUNDATION) -> Path:
    """Point core_mmap_path at this extraction's Foundation runtime directory."""
    config = foundation / "config" / "cpp_core_config.json"
    try:
        payload = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortableError(f"invalid Foundation Core config {config}: {exc}") from exc
    mmap = (foundation / "runtime" / "mmap").resolve()
    mmap.mkdir(parents=True, exist_ok=True)
    if payload.get("core_mmap_path") != mmap.as_posix():
        payload["core_mmap_path"] = mmap.as_posix()
        config.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return mmap


def layout_is_current(stamp: Path | None = None, package_root: Path | None = None) -> bool:
    stamp = stamp or STAMP
    package_root = package_root or PACKAGE_ROOT
    try:
        state = json.loads(stamp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        state.get("layout_version") == LAYOUT_VERSION
        and state.get("package_root") == str(package_root.resolve())
        and (stamp.parent / "runtime" / "launcher.json").is_file()
    )


def prepare() -> int:
    relocate_core_config()
    if layout_is_current():
        print(f"Portable FPV runtime is current: {OUTPUT}")
        return 0
    # The generated runtime embeds absolute paths; rebuild it for this directory.
    shutil.rmtree(OUTPUT, ignore_errors=True)
    result = _run(_fpv("configure", "--threejs", "--assembly", str(ASSEMBLY)))
    if result != 0:
        return result
    STAMP.write_text(
        json.dumps(
            {"layout_version": LAYOUT_VERSION, "package_root": str(PACKAGE_ROOT.resolve())},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


def http_port(output: Path = OUTPUT) -> int:
    ports = json.loads((output / "runtime" / "threejs" / "ports.json").read_text(encoding="utf-8"))
    return int(ports["http"])


def wait_for_port(port: int, timeout_sec: float = VIEWER_WAIT_SEC) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.5)
    return False


def start() -> int:
    result = prepare()
    if result != 0:
        return result
    result = _run(_fpv("start"))
    if result != 0:
        return result
    port = http_port()
    print(f"Waiting for the viewer HTTP server on port {port} ...", flush=True)
    if not wait_for_port(port):
        print("The viewer HTTP server did not start. Run status-fpv-drone.bat and check the logs.")
        return 1
    return _run(_fpv("open-viewer"))


def control(command: str) -> int:
    if not (OUTPUT / "runtime" / "launcher-session.json").is_file():
        print("The FPV simulation has not been started from this folder.")
        return 0
    return _run(_fpv(command))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    result.add_argument("command", choices=("collect", "doctor", "prepare", "start", "status", "stop"))
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "collect":
        collect()
        return 0
    if args.command == "doctor":
        return doctor()
    if args.command == "prepare":
        return prepare()
    if args.command == "start":
        return start()
    return control(args.command)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError, PortableError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
