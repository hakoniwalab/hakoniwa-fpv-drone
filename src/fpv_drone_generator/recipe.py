from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .yaml_io import load_yaml


Vector3 = tuple[float, float, float]


def _ref(raw: Any, path: str) -> str:
    if isinstance(raw, str) and raw:
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("product"), str) and raw["product"]:
        return raw["product"]
    raise ValidationError(f"{path} must be a catalog id or an object containing product")


def _position(raw: Any, path: str) -> Vector3:
    if not isinstance(raw, list) or len(raw) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in raw):
        raise ValidationError(f"{path} must contain three numbers")
    return (float(raw[0]), float(raw[1]), float(raw[2]))


@dataclass(frozen=True)
class ComponentReferences:
    frame: str
    motor: str
    motor_count: int
    propeller: str
    battery: str
    camera: str
    controller: str


@dataclass(frozen=True)
class Placements:
    battery_m: Vector3
    camera_m: Vector3
    controller_m: Vector3


@dataclass(frozen=True)
class VehicleRecipe:
    path: Path
    schema_version: int
    name: str
    vehicle_type: str
    components: ComponentReferences
    controller_mode: str
    placements: Placements
    raw: dict[str, Any]


def load_recipe(path: Path) -> VehicleRecipe:
    path = path.resolve()
    raw = load_yaml(path)
    if raw.get("schema_version") != 1:
        raise ValidationError("recipe.schema_version must be 1")
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise ValidationError("recipe.name must be a non-empty string")
    vehicle_type = raw.get("type")
    if vehicle_type != "quad_x":
        raise ValidationError("MVP supports only type: quad_x")
    components = raw.get("components")
    if not isinstance(components, dict):
        raise ValidationError("recipe.components must be an object")
    motors_raw = components.get("motors")
    motor_count = motors_raw.get("count") if isinstance(motors_raw, dict) else None
    if motor_count != 4:
        raise ValidationError("quad_x requires components.motors.count: 4")
    controller_raw = raw.get("controller")
    if not isinstance(controller_raw, dict):
        raise ValidationError("recipe.controller must be an object")
    mode = controller_raw.get("mode")
    if mode not in ("rate", "angle"):
        raise ValidationError("recipe.controller.mode must be rate or angle")
    placements_raw = raw.get("placements", {})
    if not isinstance(placements_raw, dict):
        raise ValidationError("recipe.placements must be an object")
    return VehicleRecipe(
        path=path,
        schema_version=1,
        name=name,
        vehicle_type=vehicle_type,
        components=ComponentReferences(
            frame=_ref(components.get("frame"), "components.frame"),
            motor=_ref(motors_raw, "components.motors"),
            motor_count=4,
            propeller=_ref(components.get("propeller"), "components.propeller"),
            battery=_ref(components.get("battery"), "components.battery"),
            camera=_ref(components.get("camera"), "components.camera"),
            controller=_ref(controller_raw, "controller"),
        ),
        controller_mode=mode,
        placements=Placements(
            battery_m=_position(placements_raw.get("battery_m", [0, 0, 0]), "placements.battery_m"),
            camera_m=_position(placements_raw.get("camera_m", [0, 0, 0]), "placements.camera_m"),
            controller_m=_position(placements_raw.get("controller_m", [0, 0, 0]), "placements.controller_m"),
        ),
        raw=raw,
    )
