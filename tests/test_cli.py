import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .support import ROOT, SAMPLE_RECIPE, SAMPLE_WORLD


class CliTest(unittest.TestCase):
    def _run(self, *args: str):
        return subprocess.run(
            [sys.executable, "-m", "fpv_drone_generator.cli", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_validate_and_generate(self):
        result = self._run("validate", str(SAMPLE_RECIPE))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("OK: example-5inch-fpv", result.stdout)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "package"
            result = self._run("generate", str(SAMPLE_RECIPE), "--output", str(output))
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((output / "drone.xml").is_file())

            world_output = Path(directory) / "world-package"
            result = self._run(
                "generate", str(SAMPLE_RECIPE), "--world", str(SAMPLE_WORLD),
                "--output", str(world_output),
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((world_output / "world.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
