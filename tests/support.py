from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOGS = ROOT / "catalogs"
SAMPLE_RECIPE = ROOT / "recipes" / "examples" / "5inch-fpv.yaml"
SAMPLE_WORLD = ROOT / "recipes" / "environments" / "fpv-training-course.yaml"
