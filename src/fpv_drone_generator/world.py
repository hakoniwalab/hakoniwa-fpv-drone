from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import FpvDroneError


@dataclass(frozen=True)
class Light:
    name: str
    pos_m: tuple[float, float, float]
    direction: tuple[float, float, float]
    diffuse: tuple[float, float, float]
    ambient: tuple[float, float, float]


@dataclass(frozen=True)
class Obstacle:
    name: str
    kind: str
    center_m: tuple[float, float, float]
    yaw_deg: float
    rgba: tuple[float, float, float, float]
    dimensions_m: tuple[float, float, float] | None = None
    radius_m: float | None = None
    height_m: float | None = None
    inner_width_m: float | None = None
    inner_height_m: float | None = None
    bar_thickness_m: float | None = None
    depth_m: float | None = None


@dataclass(frozen=True)
class ContactPolicy:
    ground_friction: tuple[float, float, float]
    vehicle_friction: tuple[float, float, float]
    obstacle_friction: tuple[float, float, float]
    obstacle_condim: int
    propeller_obstacle_collision: bool


@dataclass(frozen=True)
class World:
    path: Path
    sky_rgba: tuple[float, float, float, float]
    haze_rgba: tuple[float, float, float, float]
    headlight_ambient: tuple[float, float, float]
    headlight_diffuse: tuple[float, float, float]
    ground_size_m: tuple[float, float]
    ground_rgba: tuple[float, float, float, float]
    contact: ContactPolicy
    lights: tuple[Light, ...]
    obstacles: tuple[Obstacle, ...]


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FpvDroneError(f"{label} must be a mapping")
    return value


def _sequence(value: Any, length: int, label: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != length:
        raise FpvDroneError(f"{label} must contain {length} numbers")
    try:
        return tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise FpvDroneError(f"{label} must contain only numbers") from exc


def _positive(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise FpvDroneError(f"{label} must be a number") from exc
    if result <= 0:
        raise FpvDroneError(f"{label} must be positive")
    return result


def _nonnegative_sequence(value: Any, length: int, label: str) -> tuple[float, ...]:
    result = _sequence(value, length, label)
    if any(item < 0 for item in result):
        raise FpvDroneError(f"{label} must contain non-negative values")
    return result


def load_world(path: Path) -> World:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise FpvDroneError(f"cannot read world config: {path}") from exc
    root = _mapping(raw, "world config")
    if root.get("schema_version") != 1:
        raise FpvDroneError("world schema_version must be 1")

    visual = _mapping(root.get("visual"), "visual")
    ground = _mapping(root.get("ground"), "ground")
    contact = _mapping(root.get("contact", {}), "contact")
    lights_raw = root.get("lights", [])
    obstacles_raw = root.get("obstacles", [])
    if not isinstance(lights_raw, list) or not isinstance(obstacles_raw, list):
        raise FpvDroneError("lights and obstacles must be arrays")

    lights: list[Light] = []
    for index, item in enumerate(lights_raw):
        entry = _mapping(item, f"lights[{index}]")
        lights.append(Light(
            name=str(entry.get("name", f"light-{index + 1}")),
            pos_m=_sequence(entry["pos_m"], 3, f"lights[{index}].pos_m"),
            direction=_sequence(entry.get("direction", [0, 0, -1]), 3, f"lights[{index}].direction"),
            diffuse=_sequence(entry.get("diffuse", [0.8, 0.8, 0.8]), 3, f"lights[{index}].diffuse"),
            ambient=_sequence(entry.get("ambient", [0.2, 0.2, 0.2]), 3, f"lights[{index}].ambient"),
        ))

    obstacles: list[Obstacle] = []
    seen: set[str] = set()
    for index, item in enumerate(obstacles_raw):
        entry = _mapping(item, f"obstacles[{index}]")
        name = str(entry.get("name", "")).strip()
        if not name or name in seen:
            raise FpvDroneError(f"obstacles[{index}].name must be non-empty and unique")
        seen.add(name)
        kind = str(entry.get("type", ""))
        common = {
            "name": name,
            "kind": kind,
            "center_m": _sequence(entry["center_m"], 3, f"obstacles[{index}].center_m"),
            "yaw_deg": float(entry.get("yaw_deg", 0.0)),
            "rgba": _sequence(entry.get("rgba", [1, 0.35, 0.05, 1]), 4, f"obstacles[{index}].rgba"),
        }
        if kind == "box":
            obstacles.append(Obstacle(
                **common,
                dimensions_m=_sequence(entry["dimensions_m"], 3, f"obstacles[{index}].dimensions_m"),
            ))
        elif kind == "pylon":
            obstacles.append(Obstacle(
                **common,
                radius_m=_positive(entry["radius_m"], f"obstacles[{index}].radius_m"),
                height_m=_positive(entry["height_m"], f"obstacles[{index}].height_m"),
            ))
        elif kind == "gate":
            obstacles.append(Obstacle(
                **common,
                inner_width_m=_positive(entry["inner_width_m"], f"obstacles[{index}].inner_width_m"),
                inner_height_m=_positive(entry["inner_height_m"], f"obstacles[{index}].inner_height_m"),
                bar_thickness_m=_positive(entry["bar_thickness_m"], f"obstacles[{index}].bar_thickness_m"),
                depth_m=_positive(entry["depth_m"], f"obstacles[{index}].depth_m"),
            ))
        else:
            raise FpvDroneError(f"obstacles[{index}].type must be box, pylon, or gate")

    obstacle_condim = int(contact.get("obstacle_condim", 3))
    if obstacle_condim not in (1, 3, 4, 6):
        raise FpvDroneError("contact.obstacle_condim must be 1, 3, 4, or 6")
    propeller_obstacle_collision = contact.get("propeller_obstacle_collision", False)
    if not isinstance(propeller_obstacle_collision, bool):
        raise FpvDroneError("contact.propeller_obstacle_collision must be a boolean")

    return World(
        path=path,
        sky_rgba=_sequence(visual.get("sky_rgba", [0.65, 0.78, 0.92, 1]), 4, "visual.sky_rgba"),
        haze_rgba=_sequence(visual.get("haze_rgba", [0.72, 0.82, 0.92, 1]), 4, "visual.haze_rgba"),
        headlight_ambient=_sequence(visual.get("headlight_ambient", [0.45, 0.45, 0.45]), 3, "visual.headlight_ambient"),
        headlight_diffuse=_sequence(visual.get("headlight_diffuse", [0.75, 0.75, 0.75]), 3, "visual.headlight_diffuse"),
        ground_size_m=_sequence(ground.get("size_m", [30, 30]), 2, "ground.size_m"),
        ground_rgba=_sequence(ground.get("rgba", [0.28, 0.38, 0.24, 1]), 4, "ground.rgba"),
        contact=ContactPolicy(
            ground_friction=_nonnegative_sequence(contact.get("ground_friction", [0.8, 0.02, 0.001]), 3, "contact.ground_friction"),
            vehicle_friction=_nonnegative_sequence(contact.get("vehicle_friction", [0.15, 0.002, 0.0001]), 3, "contact.vehicle_friction"),
            obstacle_friction=_nonnegative_sequence(contact.get("obstacle_friction", [0.15, 0.002, 0.0001]), 3, "contact.obstacle_friction"),
            obstacle_condim=obstacle_condim,
            propeller_obstacle_collision=propeller_obstacle_collision,
        ),
        lights=tuple(lights),
        obstacles=tuple(obstacles),
    )
