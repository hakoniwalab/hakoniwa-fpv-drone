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
        for command in ("tune-build", "tune-audit", "tune-prepare", "tune-hover", "tune-angle", "tune-apply"):
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

    def test_assembly_threejs_viewer_uses_generated_three_asset_drone_type(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            vehicle = output / "runtime" / "vehicle"
            viewer = output / "runtime" / "threejs"
            vehicle.mkdir(parents=True)
            (output / "fpv-course.json").write_text("{}", encoding="utf-8")
            (vehicle / "drone.xml").write_text(
                '<mujoco><worldbody><body><camera name="fpv" pos="0.067 0 0.014" '
                'xyaxes="0 -1 0 0 0 1" fovy="120"/></body></worldbody></mujoco>',
                encoding="utf-8",
            )
            threejs_root = root / "threejs"
            threejs_root.mkdir()
            (threejs_root / "index.html").write_text("viewer", encoding="utf-8")
            resolved = {"output": output, "vehicle": vehicle, "viewer": viewer}

            FPV_TOOL.materialize_threejs_viewer(
                resolved,
                threejs_root,
                assembly=FPV_TOOL.ROOT / "recipes/examples/master3x-visual-demo.assembly.json",
                catalogs=FPV_TOOL.ROOT / "catalogs",
            )

            scene = json.loads((viewer / "scene-config.json").read_text(encoding="utf-8"))
            self.assertEqual("./assets/drone-types.json", scene["droneTypesPath"])
            self.assertEqual("master3x-visual-demo", scene["drones"][0]["type"])
            self.assertEqual(1.0, scene["drones"][0]["scale"])
            for name in ("body.glb", "propeller.glb", "camera.glb"):
                self.assertEqual(b"glTF", (viewer / "assets" / name).read_bytes()[:4])
            types = json.loads((viewer / "assets" / "drone-types.json").read_text(encoding="utf-8"))
            camera = types["master3x-visual-demo"]["cameras"][0]
            self.assertEqual([0.067, 0.0, 0.014], camera["pos"])
            self.assertEqual(120.0, camera["fov"])

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

    def test_verified_config_keeps_generated_radio_state_machine_values(self):
        # configure overwrites the generated control-param.txt with the verified
        # copy, so a missing CTRLMODE_* key silently falls back to 0.0 at runtime.
        from fpv_drone_generator.catalog import load_catalogs
        from fpv_drone_generator.package import generate_package
        from fpv_drone_generator.recipe import load_recipe
        from fpv_drone_generator.resolver import resolve_vehicle

        def ctrlmode_values(path):
            values = {}
            for line in path.read_text(encoding="utf-8").splitlines():
                fields = line.split()
                if len(fields) >= 2 and fields[0].startswith("CTRLMODE_"):
                    values[fields[0]] = float(fields[1])
            return values

        vehicle = resolve_vehicle(
            load_recipe(FPV_TOOL.DEFAULT_RECIPE), load_catalogs(FPV_TOOL.ROOT / "catalogs")
        )
        with tempfile.TemporaryDirectory() as directory:
            generated = ctrlmode_values(
                generate_package(vehicle, Path(directory) / "vehicle") / "control-param.txt"
            )
        verified = ctrlmode_values(FPV_TOOL.DEFAULT_VERIFIED_CONFIG / "control-param.txt")

        self.assertIn("CTRLMODE_LANDING_COMPLETION_STABLE_ANGLE_DEG", generated)
        self.assertEqual(generated, verified)

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

    def test_fpv_hover_profile_uses_vertical_speed_derivative_and_more_trials(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            (profile / "controller").mkdir()
            (profile / "search-space").mkdir()
            (profile / "manifests").mkdir()
            (profile / "controller" / "controller-params.txt").write_text(
                "PID_ALT_Kp 10\nPID_ALT_Kd 5\nPID_ALT_SPD_Kp 10\n"
                "PID_ALT_SPD_Ki 0\nPID_ALT_SPD_Kd 5\n",
                encoding="utf-8",
            )
            (profile / "search-space" / "hover-optuna.json").write_text(
                json.dumps({"parameters": {"PID_ALT_SPD_Kp": {}, "PID_ALT_SPD_Ki": {}, "PID_ALT_SPD_Kd": {}}}),
                encoding="utf-8",
            )
            (profile / "manifests" / "01-hover.json").write_text(
                json.dumps({"phases": [{"name": "hover", "args": {"trials": 20}}]}),
                encoding="utf-8",
            )

            FPV_TOOL.configure_fpv_hover_profile(profile, 40)

            params = (profile / "controller" / "controller-params.txt").read_text(encoding="utf-8")
            self.assertIn("PID_ALT_SPD_Kd", params)
            search = json.loads((profile / "search-space" / "hover-optuna.json").read_text(encoding="utf-8"))
            self.assertEqual({"min": 0.0, "max": 2.0, "step": 0.25}, search["parameters"]["PID_ALT_SPD_Kd"])
            manifest = json.loads((profile / "manifests" / "01-hover.json").read_text(encoding="utf-8"))
            self.assertEqual(40, manifest["phases"][0]["args"]["trials"])

    def test_fpv_angle_refinement_is_configurable(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            (profile / "manifests").mkdir()
            (profile / "search-space").mkdir()
            manifest_path = profile / "manifests" / "02-angle.json"
            manifest_path.write_text(
                json.dumps({"phases": [{"name": "angle_roll", "args": {"trials": 20}}]}),
                encoding="utf-8",
            )
            search_path = profile / "search-space" / "angle-optuna.json"
            search_path.write_text(
                json.dumps({"parameters": {
                    "PID_ROLL_RATE_Kp": {}, "PID_ROLL_RATE_Ki": {}, "PID_ROLL_RATE_Kd": {},
                    "PID_ROLL_Kp": {}, "PID_ROLL_Ki": {}, "PID_ROLL_Kd": {},
                }}),
                encoding="utf-8",
            )

            FPV_TOOL.configure_fpv_angle_profile(profile, 40, refine=True)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(40, manifest["phases"][0]["args"]["trials"])
            search = json.loads(search_path.read_text(encoding="utf-8"))
            self.assertEqual(
                {"min": 0.09, "max": 0.15, "step": 0.01},
                search["parameters"]["PID_ROLL_RATE_Kd"],
            )
            with self.assertRaisesRegex(FPV_TOOL.RuntimeErrorWithMessage, "angle-trials"):
                FPV_TOOL.configure_fpv_angle_profile(profile, 0)


if __name__ == "__main__":
    unittest.main()
