from __future__ import annotations

from ..catalog import Vector3


def weighted_center(parts: list[tuple[float, Vector3]]) -> Vector3:
    total = sum(mass for mass, _ in parts)
    return tuple(sum(mass * position[axis] for mass, position in parts) / total for axis in range(3))  # type: ignore[return-value]
