from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ..world import Obstacle, World


def _obstacle_payload(obstacle: Obstacle) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": obstacle.name,
        "type": obstacle.kind,
        "center_m": list(obstacle.center_m),
        "yaw_deg": obstacle.yaw_deg,
        "rgba": list(obstacle.rgba),
    }
    for key in (
        "dimensions_m",
        "radius_m",
        "height_m",
        "inner_width_m",
        "inner_height_m",
        "bar_thickness_m",
        "depth_m",
    ):
        value = getattr(obstacle, key)
        if value is not None:
            payload[key] = list(value) if isinstance(value, tuple) else value
    return payload


def generate_threejs_course(world: World, output: Path) -> None:
    """Render a validated World into the optional Three.js adapter format."""
    payload = {
        "schema_version": 1,
        "kind": "hakoniwa-fpv-course",
        "coordinates": "mujoco-flu-meters",
        "visual": {
            "sky_rgba": list(world.sky_rgba),
            "haze_rgba": list(world.haze_rgba),
            "headlight_ambient": list(world.headlight_ambient),
            "headlight_diffuse": list(world.headlight_diffuse),
        },
        "ground": {
            "size_m": list(world.ground_size_m),
            "rgba": list(world.ground_rgba),
        },
        "lights": [asdict(light) for light in world.lights],
        "obstacles": [_obstacle_payload(obstacle) for obstacle in world.obstacles],
    }
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
