import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "fpv.py"
SPEC = importlib.util.spec_from_file_location("fpv_tool", TOOL_PATH)
assert SPEC and SPEC.loader
FPV_TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FPV_TOOL)


class FpvToolTest(unittest.TestCase):
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
