#!/usr/bin/env python3
"""Prepare the public Hakoniwa Drone Core release binaries for this checkout.

Business Pack recipe.py clones hakoniwa-drone-core; this tool adds what it
cannot: the OS-specific release archive, the MuJoCo runtime, and the link step.
"""
from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DRONE_CORE = ROOT.parent / "hakoniwa-drone-core"
DRONE_CORE_RELEASE = "v4.1.1"
DRONE_CORE_RELEASE_BASE = "https://github.com/toppers/hakoniwa-drone-core/releases/download"
MUJOCO_RELEASE_BASE = "https://github.com/google-deepmind/mujoco/releases/download"


@dataclass(frozen=True)
class Distribution:
    archive: str
    sha256: str
    directory: str
    binary_prefix: str
    executable_suffix: str


# SHA-256 values match the published v4.1.1 release assets.
DISTRIBUTIONS = {
    "Darwin": Distribution(
        "mac.zip", "9f604b4ce8f5d083ce0eacad72b04dd433a6fb4664e3883e808eec30ffc43530", "mac", "mac-", ""
    ),
    "Linux": Distribution(
        "lnx.zip", "dfc5a264370c284598f677d261e5c180ede567b1cbce90092e974f88fa438da8", "lnx", "linux-", ""
    ),
    "Windows": Distribution(
        "win.zip", "b1fd838918e3c035551ac111d722a011a7f0e8351e483ed61544b851791feb1f", "win", "win-", ".exe"
    ),
}
REQUIRED_EXECUTABLES = ("main_hako_drone_service", "drone_visual_state_publisher")


class PrepareError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        with urllib.request.urlopen(url) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output, 1024 * 1024)
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def verified_download(url: str, destination: Path, expected_sha256: str) -> str:
    if destination.is_file() and sha256_file(destination) == expected_sha256:
        return "verified cache"
    print(f"Downloading: {url}", flush=True)
    download(url, destination)
    actual = sha256_file(destination)
    if actual != expected_sha256:
        destination.unlink(missing_ok=True)
        raise PrepareError(f"SHA-256 mismatch for {url}: expected {expected_sha256}, got {actual}")
    return "downloaded"


def safe_extract_zip(archive: Path, destination: Path) -> None:
    destination = destination.resolve()
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            target = (destination / member.filename).resolve()
            if target != destination and destination not in target.parents:
                raise PrepareError(f"archive contains an unsafe path: {member.filename}")
        package.extractall(destination)
        # zipfile drops Unix permissions; restore them like unzip does.
        for member in package.infolist():
            mode = (member.external_attr >> 16) & 0o777
            if mode and not member.is_dir():
                (destination / member.filename).chmod(mode)


def mujoco_asset(version: str, system: str, machine: str) -> str:
    machine = machine.lower()
    if system == "Darwin":
        return f"mujoco-{version}-macos-universal2.dmg"
    if system == "Linux":
        architecture = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}.get(machine)
        if architecture is None:
            raise PrepareError(f"unsupported Linux architecture for MuJoCo: {machine}")
        return f"mujoco-{version}-linux-{architecture}.tar.gz"
    if system == "Windows":
        if machine not in {"x86_64", "amd64"}:
            raise PrepareError(f"unsupported Windows architecture for MuJoCo: {machine}")
        return f"mujoco-{version}-windows-x86_64.zip"
    raise PrepareError(f"unsupported operating system: {system}")


def read_checksum(path: Path, asset: str) -> str:
    fields = path.read_text(encoding="utf-8").strip().split()
    if not fields or len(fields[0]) != 64:
        raise PrepareError(f"invalid MuJoCo checksum file: {path}")
    if len(fields) > 1 and Path(fields[-1].lstrip("*")).name != asset:
        raise PrepareError(f"MuJoCo checksum names an unexpected asset: {fields[-1]}")
    return fields[0].lower()


def run_checked(command: list[str], cwd: Path) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def copy_extracted_mujoco(extraction_root: Path, drone_core: Path, version: str) -> None:
    source = extraction_root / f"mujoco-{version}"
    if not source.is_dir() and ((extraction_root / "bin").is_dir() or (extraction_root / "lib").is_dir()):
        # The Windows archive has bin/, include/, lib/ at its root instead of
        # a single mujoco-<version>/ directory.
        source = extraction_root
    if not source.is_dir():
        directories = [path for path in extraction_root.iterdir() if path.is_dir()]
        if len(directories) != 1:
            raise PrepareError(f"MuJoCo archive has an unexpected layout in {extraction_root}")
        source = directories[0]
    shutil.copytree(source, drone_core / "vendor" / "mujoco", dirs_exist_ok=True)


def install_mujoco(drone_core: Path, distribution: Distribution, system: str, archive: Path, version: str) -> Path:
    if system == "Darwin":
        library = drone_core / "vendor" / "mujoco" / "lib" / f"libmujoco.{version}.dylib"
        if not library.is_file():
            # install-mujoco-mac.bash reuses vendor/downloads/<asset> when present,
            # so it installs the archive verified above instead of downloading again.
            run_checked(["bash", str(drone_core / "tools" / "install-mujoco-mac.bash"), str(drone_core)], drone_core)
        # The released binaries carry the build machine's RPATH; add this
        # checkout's library directory after every extraction.
        run_checked(
            [
                "bash", str(drone_core / "tools" / "link-mujoco-mac.bash"),
                str(drone_core / distribution.directory), "--lib-dir", str(library.parent),
            ],
            drone_core,
        )
        return library
    with tempfile.TemporaryDirectory(prefix="hakoniwa-mujoco-") as temporary:
        extraction_root = Path(temporary)
        if system == "Linux":
            with tarfile.open(archive, "r:gz") as package:
                package.extractall(extraction_root, filter="data")
            library = drone_core / "vendor" / "mujoco" / "lib" / f"libmujoco.so.{version}"
        else:
            safe_extract_zip(archive, extraction_root)
            library = drone_core / "vendor" / "mujoco" / "bin" / "mujoco.dll"
        copy_extracted_mujoco(extraction_root, drone_core, version)
    return library


def prepare(drone_core: Path, system: str, machine: str) -> int:
    distribution = DISTRIBUTIONS.get(system)
    if distribution is None:
        raise PrepareError(f"unsupported operating system: {system}")
    if not (drone_core / "MUJOCO_VERSION.txt").is_file():
        raise PrepareError(
            f"hakoniwa-drone-core checkout not found: {drone_core} "
            "(run Business Pack recipe.py configure first)"
        )
    downloads = drone_core / "vendor" / "downloads"

    archive = downloads / DRONE_CORE_RELEASE / distribution.archive
    mode = verified_download(
        f"{DRONE_CORE_RELEASE_BASE}/{DRONE_CORE_RELEASE}/{distribution.archive}", archive, distribution.sha256
    )
    safe_extract_zip(archive, drone_core)
    executables = [
        drone_core / distribution.directory / f"{distribution.binary_prefix}{name}{distribution.executable_suffix}"
        for name in REQUIRED_EXECUTABLES
    ]
    for executable in executables:
        if not executable.is_file():
            raise PrepareError(f"release archive did not provide {executable}")
        executable.chmod(executable.stat().st_mode | 0o111)
    print(f"[OK] Drone Core {DRONE_CORE_RELEASE} {distribution.archive} ({mode}) -> {drone_core / distribution.directory}")

    version = (drone_core / "MUJOCO_VERSION.txt").read_text(encoding="utf-8").strip()
    asset = mujoco_asset(version, system, machine)
    checksum_path = downloads / f"{asset}.sha256"
    if not checksum_path.is_file():
        print(f"Downloading: {MUJOCO_RELEASE_BASE}/{version}/{asset}.sha256", flush=True)
        download(f"{MUJOCO_RELEASE_BASE}/{version}/{asset}.sha256", checksum_path)
    mujoco_archive = downloads / asset
    mujoco_mode = verified_download(
        f"{MUJOCO_RELEASE_BASE}/{version}/{asset}", mujoco_archive, read_checksum(checksum_path, asset)
    )
    library = install_mujoco(drone_core, distribution, system, mujoco_archive, version)
    if not library.is_file():
        raise PrepareError(f"MuJoCo runtime library is missing after install: {library}")
    print(f"[OK] MuJoCo {version} ({mujoco_mode}) -> {library}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    result.add_argument("command", choices=("prepare",))
    result.add_argument("--drone-core-root", type=Path, default=DEFAULT_DRONE_CORE)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return prepare(args.drone_core_root.resolve(), platform.system(), platform.machine())
    except (PrepareError, OSError, urllib.error.URLError, zipfile.BadZipFile, tarfile.TarError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
