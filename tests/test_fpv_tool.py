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
        self.assertIn('"-m", "rc-custom"', source)

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

    @unittest.skipUnless(
        importlib.util.find_spec("trimesh"),
        "trimesh is not installed in this test interpreter",
    )
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

    def test_verified_configs_keep_generated_radio_state_machine_values(self):
        # configure overwrites the generated control-param.txt with the verified
        # copy, so a missing CTRLMODE_* key silently falls back to 0.0 at runtime.
        from fpv_drone_generator.catalog import load_catalogs
        from fpv_drone_generator.package import generate_package
        from fpv_drone_generator.recipe import load_recipe
        from fpv_drone_generator.resolver import resolve_vehicle
        from fpv_drone_generator.target import (
            bundled_drone_pro_rotor_contract_path,
            load_drone_pro_rotor_contract,
        )

        def ctrlmode_values(path):
            values = {}
            for line in path.read_text(encoding="utf-8").splitlines():
                fields = line.split()
                if len(fields) >= 2 and fields[0].startswith("CTRLMODE_"):
                    values[fields[0]] = float(fields[1])
            return values

        catalogs = load_catalogs(FPV_TOOL.ROOT / "catalogs")
        contract = load_drone_pro_rotor_contract(bundled_drone_pro_rotor_contract_path())
        receipts = sorted((FPV_TOOL.ROOT / "verified-configs").glob("*/receipt.json"))
        self.assertGreaterEqual(len(receipts), 2)
        for receipt_path in receipts:
            with self.subTest(verified_config=receipt_path.parent.name):
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                vehicle = resolve_vehicle(
                    load_recipe(FPV_TOOL.ROOT / receipt["source_recipe"]), catalogs
                )
                with tempfile.TemporaryDirectory() as directory:
                    generated = ctrlmode_values(
                        generate_package(
                            vehicle, Path(directory) / "vehicle", rotor_contract=contract
                        ) / "control-param.txt"
                    )
                verified = ctrlmode_values(
                    receipt_path.parent / "drone-config" / "control-param.txt"
                )
                self.assertIn("CTRLMODE_LANDING_COMPLETION_STABLE_ANGLE_DEG", generated)
                self.assertEqual(generated, verified)
                FPV_TOOL.validate_verified_config(receipt_path.parent / "drone-config")

    def test_master3x_recipe_discovers_tuned_config(self):
        self.assertEqual(
            FPV_TOOL.ROOT / "verified-configs" / "master3x-angle" / "drone-config",
            FPV_TOOL.discover_verified_config(
                FPV_TOOL.ROOT / "recipes" / "examples" / "master3x.yaml",
                FPV_TOOL.DEFAULT_WORLD,
            ),
        )

    def test_runtime_state_follows_the_latest_log_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resolved = {"vehicle": root / "vehicle", "logs": root / "logs"}
            resolved["vehicle"].mkdir()
            resolved["logs"].mkdir()
            (resolved["vehicle"] / "control-param.txt").write_text(
                "CTRLMODE_START_IN_HOVERING 1\n", encoding="utf-8"
            )
            self.assertEqual(
                {"simulation": "not started", "radio_control": "OFF", "mode": "GPS",
                 "flight_state": "Hovering", "controller": "unknown"},
                FPV_TOOL.runtime_state(resolved),
            )
            (resolved["logs"] / "fpv-drone-service.out").write_text(
                "INFO: start simulation\n"
                "DroneService::advanceTimeStep: Control mode changed to ATTI\n"
                "DroneService::advanceTimeStep: Control mode changed to GPS\n"
                "radio_control: 1\n"
                "DroneService::advanceTimeStep: Control mode changed to ATTI\n"
                "[STATE] Hovering -> Landing\n"
                "[STATE] Idle -> Ascending\n",
                encoding="utf-8",
            )
            (resolved["logs"] / "fpv-remote-controller.out").write_text(
                "ジョイスティックの名前: DualSense Wireless Controller\n", encoding="utf-8"
            )
            self.assertEqual(
                {"simulation": "running", "radio_control": "ON", "mode": "ATTI",
                 "flight_state": "Landing", "controller": "DualSense Wireless Controller"},
                FPV_TOOL.runtime_state(resolved),
            )

    def test_threejs_skips_the_native_mujoco_viewer_unless_requested(self):
        parse = FPV_TOOL.parser().parse_args
        self.assertFalse(parse(["configure", "--threejs"]).mujoco_viewer)
        self.assertTrue(parse(["configure", "--threejs", "--mujoco-viewer"]).mujoco_viewer)

    def test_foundation_python_follows_the_platform_venv_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(root / "bin" / "python3", FPV_TOOL.foundation_python_path(root, windows=False))
            self.assertEqual(root / "Scripts" / "python.exe", FPV_TOOL.foundation_python_path(root, windows=True))
            (root / "python.exe").write_text("", encoding="utf-8")
            self.assertEqual(root / "python.exe", FPV_TOOL.foundation_python_path(root, windows=True))

    def test_windows_library_paths_include_dll_locations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install = root / "work" / "foundation" / "install"
            (install.parent / "config").mkdir(parents=True)
            (install.parent / "config" / "toolchain.json").write_text(
                json.dumps({"schema_version": 1, "vcpkg_root": str(root / "vcpkg")}), encoding="utf-8"
            )
            core = root / "hakoniwa-drone-core"
            self.assertEqual(
                [install / "lib", core / "mac"],
                FPV_TOOL.native_library_paths(install, core, core / "mac", windows=False),
            )
            self.assertEqual(
                [install / "bin", install / "lib", core / "win", core / "vendor" / "mujoco" / "bin",
                 root / "vcpkg" / "installed" / "x64-windows" / "bin"],
                FPV_TOOL.native_library_paths(install, core, core / "win", windows=True),
            )

    def test_start_rejects_a_taken_threejs_port(self):
        import socket

        with tempfile.TemporaryDirectory() as directory, socket.socket() as holder:
            holder.bind(("0.0.0.0", 0))
            holder.listen()
            port = holder.getsockname()[1]
            launcher = Path(directory) / "launcher.json"
            launcher.write_text(
                json.dumps({"assets": [{"name": "fpv-threejs-web-bridge"}]}), encoding="utf-8"
            )
            with mock.patch.dict(FPV_TOOL.THREEJS_PORTS, {"fpv-threejs-web-bridge": port}):
                with self.assertRaisesRegex(FPV_TOOL.RuntimeErrorWithMessage, f"port {port}"):
                    FPV_TOOL.require_free_ports(launcher)
                launcher.write_text(
                    json.dumps({"assets": [{"name": "fpv-drone-service"}]}), encoding="utf-8"
                )
                FPV_TOOL.require_free_ports(launcher)

    def test_master3x_assembly_projection_discovers_tuned_config(self):
        assembly = FPV_TOOL.ROOT / "recipes" / "examples" / "master3x-visual-demo.assembly.json"
        with tempfile.TemporaryDirectory() as directory:
            projected = Path(directory) / "assembly-projected-recipe.yaml"
            projected.write_bytes(
                (FPV_TOOL.ROOT / "recipes" / "examples" / "master3x.yaml").read_bytes()
            )
            self.assertEqual(
                FPV_TOOL.ROOT / "verified-configs" / "master3x-angle" / "drone-config",
                FPV_TOOL.discover_verified_config(projected, FPV_TOOL.DEFAULT_WORLD, assembly),
            )
            projected.write_text(projected.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")
            self.assertIsNone(
                FPV_TOOL.discover_verified_config(projected, FPV_TOOL.DEFAULT_WORLD, assembly)
            )

    def test_master3x_recipe_matches_its_assembly_projection(self):
        # The tuned config is keyed to master3x.yaml, so it must not drift from
        # the Assembly Graph that the Three.js assets are built from.
        import yaml
        from fpv_drone_generator.assembly import load_assembly_graph, project_recipe, resolve_assembly
        from fpv_drone_generator.catalog import load_catalogs

        graph = load_assembly_graph(
            FPV_TOOL.ROOT / "recipes" / "examples" / "master3x-visual-demo.assembly.json"
        )
        projected = project_recipe(
            resolve_assembly(graph, load_catalogs(FPV_TOOL.ROOT / "catalogs"))
        )
        committed = yaml.safe_load(
            (FPV_TOOL.ROOT / "recipes" / "examples" / "master3x.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(projected, committed)

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
            self.assertEqual(
                [0.0, 0.0, -2.0],
                generated["components"]["droneDynamics"]["position_meter"],
            )
            self.assertEqual("TuningController", generated["controller"]["moduleName"])
            self.assertEqual("adapter-hakoniwa", generated["controller"]["backendType"])

    def test_fpv_hover_profile_uses_vertical_speed_derivative_and_more_trials(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            (profile / "controller").mkdir()
            (profile / "search-space").mkdir()
            (profile / "manifests").mkdir()
            (profile / "param-sets").mkdir()
            (profile / "score").mkdir()
            (profile / "controller" / "controller-params.txt").write_text(
                "PID_ALT_Kp 10\nPID_ALT_Kd 5\nPID_ALT_SPD_Kp 10\n"
                "PID_ALT_SPD_Ki 0\nPID_ALT_SPD_Kd 5\n",
                encoding="utf-8",
            )
            (profile / "search-space" / "hover-optuna.json").write_text(
                json.dumps({"parameters": {"PID_ALT_SPD_Kp": {}, "PID_ALT_SPD_Ki": {}, "PID_ALT_SPD_Kd": {}}}),
                encoding="utf-8",
            )
            (profile / "param-sets" / "base-overrides.json").write_text(
                json.dumps({"PID_ROLL_RATE_Kp": 3.0}), encoding="utf-8"
            )
            (profile / "score" / "hover-score.json").write_text(
                json.dumps({
                    "hard_gates": [{"id": "hover_entry_time", "value": 3.0}],
                    "score_terms": [{"id": "hover_entry_time", "worst": 3.0}],
                }),
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
            self.assertEqual({"value": 6.0}, search["parameters"]["PID_ROLL_Kp"])
            base = json.loads(
                (profile / "param-sets" / "base-overrides.json").read_text(encoding="utf-8")
            )
            self.assertEqual(0.15, base["PID_ROLL_RATE_Kp"])
            self.assertEqual(0.005, base["PID_ROLL_RATE_Kd"])
            score = json.loads(
                (profile / "score" / "hover-score.json").read_text(encoding="utf-8")
            )
            self.assertEqual(5.0, score["hard_gates"][0]["value"])
            self.assertEqual(5.0, score["score_terms"][0]["worst"])
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
                {"min": 0.0, "max": 0.03, "step": 0.005},
                search["parameters"]["PID_ROLL_RATE_Kd"],
            )
            self.assertLessEqual(search["parameters"]["PID_ROLL_RATE_Kp"]["min"], 0.15)
            self.assertGreaterEqual(search["parameters"]["PID_ROLL_Kp"]["max"], 6.0)
            with self.assertRaisesRegex(FPV_TOOL.RuntimeErrorWithMessage, "angle-trials"):
                FPV_TOOL.configure_fpv_angle_profile(profile, 0)

    def test_fpv_trial_flight_gate_rejects_motor_saturation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trial = root / "trial_0000"
            scenarios = trial / "suite" / "generated_scenarios"
            log_dir = root / "scenario-output" / "drone_log0"
            scenarios.mkdir(parents=True)
            log_dir.mkdir(parents=True)
            (scenarios / "roll-step.json").write_text(
                json.dumps({
                    "prepare": {"settle_time_sec": 0.0},
                    "logging": {"output_dir": str(log_dir.parent)},
                }),
                encoding="utf-8",
            )
            (log_dir / "drone_dynamics.csv").write_text(
                "timestamp,X,Y,Z,Rx,Ry,Rz,Vx,Vy,Vz,VRx,VRy,VRz,collided_counts\n"
                "0,0,0,-2,0,0,0,0,0,0,0,0,0,0\n"
                "1000,0,0,-2,0,0,0,0,0,0,0,0,0,0\n",
                encoding="utf-8",
            )
            for index in range(4):
                (log_dir / f"log_rotor_{index}.csv").write_text(
                    "timestamp,Duty,RadPerSec,Current\n"
                    "0,0.5,100,1\n1000,0.5,100,1\n",
                    encoding="utf-8",
                )

            passed = FPV_TOOL.evaluate_fpv_trial_flight_gate(trial, root)
            self.assertTrue(passed["passed"])

            (log_dir / "log_rotor_0.csv").write_text(
                "timestamp,Duty,RadPerSec,Current\n"
                "0,1.0,100,1\n1000,0.5,100,1\n",
                encoding="utf-8",
            )
            failed = FPV_TOOL.evaluate_fpv_trial_flight_gate(trial, root)
            self.assertFalse(failed["passed"])
            self.assertGreater(
                failed["scenarios"][0]["motor_saturation_ratio"], 0.1
            )

            with (log_dir / "drone_dynamics.csv").open("a", encoding="utf-8") as stream:
                stream.write("2000,0,0\n")
            still_failed = FPV_TOOL.evaluate_fpv_trial_flight_gate(trial, root)
            self.assertFalse(still_failed["passed"])

    def test_post_angle_hover_validation_requires_hover_and_flight_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drone_pro = root / "drone-pro"
            profile = drone_pro / "work" / "profile"
            runtime = root / "runtime"
            foundation_python = root / "python3"
            selected = runtime / "selected.json"
            (drone_pro / "tuning" / "tools" / "suites").mkdir(parents=True)
            (drone_pro / "tuning" / "tools" / "suites" / "run_hover_sanity.py").write_text(
                "# test", encoding="utf-8"
            )
            (profile / "phases").mkdir(parents=True)
            (profile / "phases" / "hover.json").write_text("{}", encoding="utf-8")
            runtime.mkdir()
            foundation_python.write_text("", encoding="utf-8")
            selected.write_text("{}", encoding="utf-8")

            def materialize_result(_command, **_kwargs):
                suite = profile / "results" / "autotune" / "fpv-post-angle-hover" / "trial_0000" / "suite"
                suite.mkdir(parents=True)
                (suite / "hover-sanity-eval.json").write_text(
                    json.dumps({"status": "PASS"}), encoding="utf-8"
                )

            with mock.patch.object(FPV_TOOL, "run", side_effect=materialize_result), mock.patch.object(
                FPV_TOOL,
                "evaluate_fpv_trial_flight_gate",
                return_value={"passed": True, "scenarios": []},
            ):
                report = FPV_TOOL.run_post_angle_hover_validation(
                    profile, selected, drone_pro, foundation_python, runtime
                )

            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual("passed", payload["status"])
            self.assertEqual(10, payload["requirements"]["sustain_sec"])
            validation_phase = json.loads(
                (runtime / "pid-tuning-post-angle-hover-phase.json").read_text(encoding="utf-8")
            )
            self.assertFalse(validation_phase["simulation_model_overrides"]["remove_floor"])


if __name__ == "__main__":
    unittest.main()
