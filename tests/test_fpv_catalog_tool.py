import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "fpv-catalog.py"
SPEC = importlib.util.spec_from_file_location("fpv_catalog_tool", TOOL_PATH)
assert SPEC and SPEC.loader
FPV_CATALOG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FPV_CATALOG)


class FpvCatalogToolTest(unittest.TestCase):
    def test_parser_exposes_staged_workflow_and_selection(self):
        self.assertEqual("prepare", FPV_CATALOG.parser().parse_args(["prepare"]).command)
        self.assertEqual("doctor", FPV_CATALOG.parser().parse_args(["doctor"]).command)

        args = FPV_CATALOG.parser().parse_args(
            ["open-viewer", "motor", "generic_2207_1850kv"]
        )
        self.assertEqual("open-viewer", args.command)
        self.assertEqual("motor", args.kind)
        self.assertEqual("generic_2207_1850kv", args.item_id)

        args = FPV_CATALOG.parser().parse_args(
            ["export-glb", "propeller", "generic_5inch_3blade"]
        )
        self.assertEqual("export-glb", args.command)
        self.assertEqual("propeller", args.kind)
        self.assertEqual("generic_5inch_3blade", args.item_id)

    def test_prepare_creates_managed_venv_and_installs_showroom_extra(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory) / "work"
            args = FPV_CATALOG.parser().parse_args(
                ["prepare", "--work-dir", str(work_dir)]
            )
            expected_python = FPV_CATALOG.managed_python(work_dir)

            with mock.patch.object(FPV_CATALOG, "run") as runner:
                with mock.patch.object(
                    FPV_CATALOG,
                    "require_file",
                    return_value=expected_python,
                ):
                    self.assertEqual(0, FPV_CATALOG.prepare(args))

            self.assertEqual(2, runner.call_count)
            self.assertEqual(
                [sys.executable, "-m", "venv", str((work_dir / ".venv").resolve())],
                runner.call_args_list[0].args[0],
            )
            self.assertEqual(
                [
                    str(expected_python),
                    "-m",
                    "pip",
                    "install",
                    "-e",
                    f"{FPV_CATALOG.ROOT}[showroom]",
                ],
                runner.call_args_list[1].args[0],
            )

    def test_delegate_uses_managed_python_and_marks_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            work_dir = Path(directory) / "work"
            python = FPV_CATALOG.managed_python(work_dir)
            raw_argv = ["doctor", "--work-dir", str(work_dir)]
            completed = subprocess.CompletedProcess([], 0)

            with mock.patch.object(
                FPV_CATALOG,
                "require_file",
                return_value=python,
            ):
                with mock.patch.object(
                    FPV_CATALOG.subprocess,
                    "run",
                    return_value=completed,
                ) as runner:
                    self.assertEqual(
                        0,
                        FPV_CATALOG._delegate_to_managed_python(raw_argv, work_dir),
                    )

            command = runner.call_args.args[0]
            self.assertEqual(str(python), command[0])
            self.assertEqual(str(TOOL_PATH.resolve()), command[1])
            self.assertEqual(raw_argv, command[2:])
            env = runner.call_args.kwargs["env"]
            self.assertEqual("1", env[FPV_CATALOG.MANAGED_ENV_FLAG])
            self.assertEqual(os.environ.get("PATH"), env.get("PATH"))


if __name__ == "__main__":
    unittest.main()
