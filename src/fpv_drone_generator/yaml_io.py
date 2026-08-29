from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .errors import ValidationError


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
    except OSError as exc:
        raise ValidationError(f"cannot read YAML {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValidationError(f"invalid YAML {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"YAML root must be an object: {path}")
    return value


def dump_yaml(path: Path, value: Any) -> None:
    path.write_text(
        yaml.safe_dump(value, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
