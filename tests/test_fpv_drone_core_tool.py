import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "fpv-drone-core.py"
SPEC = importlib.util.spec_from_file_location("fpv_drone_core_tool", TOOL_PATH)
assert SPEC and SPEC.loader
TOOL = importlib.util.module_from_spec(SPEC)
# dataclasses resolve string annotations through sys.modules.
sys.modules[SPEC.name] = TOOL
SPEC.loader.exec_module(TOOL)


class FpvDroneCoreToolTest(unittest.TestCase):
    def test_distributions_match_release_archive_layout(self):
        self.assertEqual(("mac.zip", "mac", "mac-", ""), self._layout("Darwin"))
        self.assertEqual(("lnx.zip", "lnx", "linux-", ""), self._layout("Linux"))
        self.assertEqual(("win.zip", "win", "win-", ".exe"), self._layout("Windows"))
        for distribution in TOOL.DISTRIBUTIONS.values():
            self.assertRegex(distribution.sha256, r"^[0-9a-f]{64}$")

    def _layout(self, system):
        distribution = TOOL.DISTRIBUTIONS[system]
        return (
            distribution.archive,
            distribution.directory,
            distribution.binary_prefix,
            distribution.executable_suffix,
        )

    def test_mujoco_asset_follows_platform_and_architecture(self):
        self.assertEqual("mujoco-3.13.0-macos-universal2.dmg", TOOL.mujoco_asset("3.13.0", "Darwin", "arm64"))
        self.assertEqual("mujoco-3.13.0-linux-aarch64.tar.gz", TOOL.mujoco_asset("3.13.0", "Linux", "arm64"))
        self.assertEqual("mujoco-3.13.0-linux-x86_64.tar.gz", TOOL.mujoco_asset("3.13.0", "Linux", "AMD64"))
        self.assertEqual("mujoco-3.13.0-windows-x86_64.zip", TOOL.mujoco_asset("3.13.0", "Windows", "AMD64"))
        with self.assertRaises(TOOL.PrepareError):
            TOOL.mujoco_asset("3.13.0", "Windows", "arm64")

    def test_checksum_must_name_the_requested_asset(self):
        digest = "a" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.sha256"
            path.write_text(f"{digest}  mujoco-3.13.0-macos-universal2.dmg\n", encoding="utf-8")
            self.assertEqual(digest, TOOL.read_checksum(path, "mujoco-3.13.0-macos-universal2.dmg"))
            with self.assertRaises(TOOL.PrepareError):
                TOOL.read_checksum(path, "mujoco-3.13.0-linux-x86_64.tar.gz")

    def test_safe_extract_rejects_paths_outside_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("../escape.txt", "x")
            with self.assertRaises(TOOL.PrepareError):
                TOOL.safe_extract_zip(archive, Path(directory) / "out")
            self.assertFalse((Path(directory) / "escape.txt").exists())

    def test_safe_extract_restores_unix_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "release.zip"
            with zipfile.ZipFile(archive, "w") as package:
                executable = zipfile.ZipInfo("mac/mac-drone_service_rc")
                executable.external_attr = 0o755 << 16
                package.writestr(executable, "binary")
            TOOL.safe_extract_zip(archive, Path(directory) / "out")
            mode = (Path(directory) / "out" / "mac" / "mac-drone_service_rc").stat().st_mode & 0o777
            self.assertEqual(0o755, mode)

    def test_prepare_requires_a_drone_core_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(TOOL.PrepareError, "recipe.py configure"):
                TOOL.prepare(Path(directory), "Darwin", "arm64")


if __name__ == "__main__":
    unittest.main()
