import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "fpv_portable.py"
SPEC = importlib.util.spec_from_file_location("fpv_portable", TOOL_PATH)
assert SPEC and SPEC.loader
PORTABLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PORTABLE)


class FpvPortableTest(unittest.TestCase):
    def test_collect_copies_runtime_dlls_from_the_foundation_vcpkg(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            foundation = root / "foundation"
            (foundation / "config").mkdir(parents=True)
            (foundation / "config" / "toolchain.json").write_text(
                json.dumps({"vcpkg_root": str(root / "vcpkg")}), encoding="utf-8"
            )
            source = PORTABLE.vcpkg_bin(foundation)
            source.mkdir(parents=True)
            (source / "glfw3.dll").write_bytes(b"dll")

            collected = PORTABLE.collect(source, root / "out")

            self.assertEqual([root / "out" / "glfw3.dll"], collected)
            self.assertEqual(b"dll", (root / "out" / "glfw3.dll").read_bytes())
            (source / "glfw3.dll").unlink()
            with self.assertRaisesRegex(PORTABLE.PortableError, "glfw3.dll"):
                PORTABLE.collect(source, root / "out")

    def test_vcpkg_bin_requires_a_registered_toolchain(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(PORTABLE.PortableError, "foundation.py toolchain"):
                PORTABLE.vcpkg_bin(Path(directory))

    def test_relocate_core_config_replaces_the_package_placeholder(self):
        with tempfile.TemporaryDirectory() as directory:
            foundation = Path(directory) / "foundation"
            (foundation / "config").mkdir(parents=True)
            config = foundation / "config" / "cpp_core_config.json"
            config.write_text(
                json.dumps({"shm_type": "mmap", "core_mmap_path": "__HAKONIWA_PORTABLE_MMAP__"}), encoding="utf-8"
            )

            mmap = PORTABLE.relocate_core_config(foundation)

            payload = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(mmap.as_posix(), payload["core_mmap_path"])
            self.assertEqual("mmap", payload["shm_type"])
            self.assertTrue(mmap.is_dir())

    def test_layout_is_current_only_for_the_same_extraction_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "build" / "portable-master3x"
            (output / "runtime").mkdir(parents=True)
            (output / "runtime" / "launcher.json").write_text("{}", encoding="utf-8")
            stamp = output / "portable-layout.json"
            self.assertFalse(PORTABLE.layout_is_current(stamp, root))
            stamp.write_text(
                json.dumps({"layout_version": PORTABLE.LAYOUT_VERSION, "package_root": str(root.resolve())}),
                encoding="utf-8",
            )
            self.assertTrue(PORTABLE.layout_is_current(stamp, root))
            self.assertFalse(PORTABLE.layout_is_current(stamp, root / "moved"))
            (output / "runtime" / "launcher.json").unlink()
            self.assertFalse(PORTABLE.layout_is_current(stamp, root))

    def test_prepare_configures_master3x_threejs_once_per_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "portable-master3x"

            def configure(command):
                self.assertIn("configure", command)
                self.assertIn("--threejs", command)
                self.assertEqual(str(PORTABLE.ASSEMBLY), command[command.index("--assembly") + 1])
                (output / "runtime").mkdir(parents=True)
                (output / "runtime" / "launcher.json").write_text("{}", encoding="utf-8")
                return 0

            with mock.patch.multiple(
                PORTABLE, OUTPUT=output, STAMP=output / "portable-layout.json",
                relocate_core_config=mock.DEFAULT,
            ), mock.patch.object(PORTABLE, "_run", side_effect=configure) as run:
                self.assertEqual(0, PORTABLE.prepare())
                self.assertEqual(0, PORTABLE.prepare())
            self.assertEqual(1, run.call_count)

    def test_doctor_reports_missing_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.exe"
            with mock.patch.object(PORTABLE, "required_inputs", return_value={"service": missing}):
                self.assertEqual(1, PORTABLE.doctor())
            missing.write_bytes(b"x")
            with mock.patch.object(PORTABLE, "required_inputs", return_value={"service": missing}):
                self.assertEqual(0, PORTABLE.doctor())

    def test_profile_declares_the_tool_contract_and_bundled_inputs(self):
        profile = json.loads((ROOT / "portable" / "windows-profile.json").read_text(encoding="utf-8"))
        self.assertEqual("tools/fpv_portable.py", profile["tool"])
        self.assertTrue((ROOT / profile["tool"]).is_file())
        self.assertTrue((ROOT / profile["readme"]).is_file())
        owner = next(item for item in profile["repositories"] if item["name"] == ROOT.name)
        self.assertIn("build/portable-runtime", owner["include_paths"])
        for relative in ("tools", "src", "recipes", "catalogs", "verified-configs"):
            self.assertIn(relative, owner["include_paths"])
            self.assertTrue((ROOT / relative).exists(), relative)
        # The embeddable Python ignores PYTHONPATH because of its ._pth file,
        # so the generator package must be on the packaged interpreter path.
        self.assertIn(f"{ROOT.name}/src", profile["python_paths"])
        self.assertIn("fpv_drone_generator", profile["validation_imports"])
        self.assertEqual(["hakoniwa-fpv-drone/build/portable-master3x"], profile["staging_cleanup"])
        self.assertEqual(
            PORTABLE.OUTPUT.relative_to(ROOT.parent).as_posix(), profile["staging_cleanup"][0]
        )


if __name__ == "__main__":
    unittest.main()
