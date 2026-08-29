import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "fpv.py"
SPEC = importlib.util.spec_from_file_location("fpv_tool", TOOL_PATH)
assert SPEC and SPEC.loader
FPV_TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FPV_TOOL)


class FpvToolTest(unittest.TestCase):
    def test_rc_bootstrap_is_owned_by_fpv_repository(self):
        bootstrap = FPV_TOOL.ROOT / "tools" / "fpv_rc_bootstrap.py"
        self.assertTrue(bootstrap.is_file())
        source = bootstrap.read_text(encoding="utf-8")
        self.assertIn("neutral.axis = [0.0] * 6", source)
        self.assertIn("neutral.button = [False] * 15", source)
        self.assertIn('"-m",\n            "rc-custom"', source)

    def test_tuning_digest_is_deterministic_and_tracks_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            vehicle = Path(directory)
            for name, value in (
                ("drone_config_0.json", "config"),
                ("drone.xml", "model"),
                ("control-param.txt", "control"),
            ):
                (vehicle / name).write_text(value, encoding="utf-8")

            first = FPV_TOOL.tuning_input_digest(vehicle)
            self.assertEqual(first, FPV_TOOL.tuning_input_digest(vehicle))

            (vehicle / "drone.xml").write_text("changed-model", encoding="utf-8")
            self.assertNotEqual(first, FPV_TOOL.tuning_input_digest(vehicle))

    def test_parser_exposes_only_sequential_tuning_steps(self):
        for command in ("tune-build", "tune-prepare", "tune-hover", "tune-angle", "tune-apply"):
            self.assertEqual(command, FPV_TOOL.parser().parse_args([command]).command)
        self.assertEqual("open-viewer", FPV_TOOL.parser().parse_args(["open-viewer"]).command)
        self.assertTrue(FPV_TOOL.parser().parse_args(["configure", "--threejs"]).threejs)

    def test_generated_wheelbase_uses_motor_diagonal(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            report.write_text(
                json.dumps({
                    "properties": {
                        "motor_positions_m": {
                            "value": [
                                [0.1, 0.1, 0.0],
                                [0.1, -0.1, 0.0],
                                [-0.1, -0.1, 0.0],
                                [-0.1, 0.1, 0.0],
                            ]
                        }
                    }
                }),
                encoding="utf-8",
            )
            self.assertAlmostEqual(2 ** 0.5 * 0.2, FPV_TOOL.generated_wheelbase(report))

    def test_mujoco_fpv_camera_is_runtime_source_of_truth(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "drone.xml"
            model.write_text(
                '<mujoco><worldbody><body><camera name="fpv" pos="0.08 0 0.005" '
                'xyaxes="0 -1 0 0 0 1" fovy="120"/></body></worldbody></mujoco>',
                encoding="utf-8",
            )
            camera = FPV_TOOL.mujoco_fpv_camera(model)
            self.assertEqual([0.08, 0.0, 0.005], camera["position_m"])
            self.assertEqual(120.0, camera["fov_deg"])

    def test_open_viewer_launches_default_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            viewer = output / "runtime" / "threejs"
            viewer.mkdir(parents=True)
            (viewer / "viewer-config.json").write_text("{}", encoding="utf-8")
            resolved = {"viewer": viewer}
            with mock.patch.object(FPV_TOOL, "viewer_url", return_value="http://example.test/viewer"):
                with mock.patch.object(FPV_TOOL.webbrowser, "open", return_value=True) as browser:
                    self.assertEqual("http://example.test/viewer", FPV_TOOL.open_viewer(resolved))
            browser.assert_called_once_with("http://example.test/viewer", new=2)

    def test_restore_verified_config_materializes_portable_model_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "verified"
            verified = package / "drone-config"
            output = root / "output"
            verified.mkdir(parents=True)
            (verified / "drone.xml").write_text("<mujoco/>", encoding="utf-8")
            (verified / "control-param.txt").write_text("PID_POS_MAX_ROLL 55\n", encoding="utf-8")
            (verified / "drone_config_0.json").write_text(
                json.dumps(
                    {
                        "components": {
                            "droneDynamics": {"mujoco": {"modelPath": "drone.xml"}}
                        }
                    }
                ),
                encoding="utf-8",
            )
            (package / "receipt.json").write_text(
                json.dumps(
                    {
                        "files": {
                            f"drone-config/{name}": {
                                "sha256": FPV_TOOL.sha256_file(verified / name)
                            }
                            for name in ("drone.xml", "drone_config_0.json", "control-param.txt")
                        }
                    }
                ),
                encoding="utf-8",
            )
            args = FPV_TOOL.parser().parse_args(
                [
                    "restore-verified-config",
                    "--output", str(output),
                    "--verified-config", str(verified),
                ]
            )

            self.assertEqual(0, FPV_TOOL.restore_verified_config(args))
            vehicle = output.resolve() / "runtime" / "vehicle"
            restored = json.loads((vehicle / "drone_config_0.json").read_text(encoding="utf-8"))
            self.assertEqual(
                str(vehicle / "drone.xml"),
                restored["components"]["droneDynamics"]["mujoco"]["modelPath"],
            )
            self.assertEqual("<mujoco/>", (vehicle / "drone.xml").read_text(encoding="utf-8"))
            self.assertIn("55", (vehicle / "control-param.txt").read_text(encoding="utf-8"))

    def test_default_recipe_discovers_reviewed_config(self):
        self.assertEqual(
            FPV_TOOL.DEFAULT_VERIFIED_CONFIG,
            FPV_TOOL.discover_verified_config(
                FPV_TOOL.DEFAULT_RECIPE,
                FPV_TOOL.DEFAULT_WORLD,
            ),
        )

    def test_parameter_overrides_preserve_comments_and_append_missing_keys(self):
        source = "# generated\nPID_ROLL_Kp 1\nPID_ROLL_Ki 0\n"
        result = FPV_TOOL.apply_parameter_overrides(
            source, {"PID_ROLL_Kp": 0.15, "PID_ROLL_Kd": 0.005}
        )
        self.assertIn("# generated", result)
        self.assertIn("PID_ROLL_Kp                                  0.15", result)
        self.assertIn("PID_ROLL_Ki 0", result)
        self.assertIn("PID_ROLL_Kd                                  0.005", result)

    def test_tuning_inputs_enable_csv_without_mutating_runtime_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vehicle = root / "vehicle"
            vehicle.mkdir()
            source = {
                "simulation": {"logging": {"mode": "none"}, "logOutputDirectory": "."},
                "components": {"droneDynamics": {"mujoco": {"modelPath": "/tmp/model.xml"}}},
                "controller": {"paramFilePath": "control-param.txt"},
            }
            (vehicle / "drone_config_0.json").write_text(json.dumps(source), encoding="utf-8")
            (vehicle / "drone.xml").write_text("model", encoding="utf-8")
            (vehicle / "control-param.txt").write_text("params", encoding="utf-8")

            tuning = FPV_TOOL.materialize_tuning_inputs(vehicle, root / "tuning")
            generated = json.loads((tuning / "drone_config_0.json").read_text(encoding="utf-8"))
            original = json.loads((vehicle / "drone_config_0.json").read_text(encoding="utf-8"))

            self.assertEqual("csv", generated["simulation"]["logging"]["mode"])
            self.assertEqual("none", original["simulation"]["logging"]["mode"])
            self.assertEqual("drone.xml", generated["components"]["droneDynamics"]["mujoco"]["modelPath"])
            self.assertEqual("TuningController", generated["controller"]["moduleName"])
            self.assertEqual("adapter-hakoniwa", generated["controller"]["backendType"])


if __name__ == "__main__":
    unittest.main()
