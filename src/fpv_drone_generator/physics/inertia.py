from __future__ import annotations

from ..catalog import Vector3


def point_mass_diagonal(mass_kg: float, position_m: Vector3, center_of_mass_m: Vector3) -> Vector3:
    x = position_m[0] - center_of_mass_m[0]
    y = position_m[1] - center_of_mass_m[1]
    z = position_m[2] - center_of_mass_m[2]
    return (mass_kg * (y * y + z * z), mass_kg * (x * x + z * z), mass_kg * (x * x + y * y))


def add_diagonals(values: list[Vector3]) -> Vector3:
    return tuple(sum(value[axis] for value in values) for axis in range(3))  # type: ignore[return-value]


def box_diagonal(mass_kg: float, dimensions_m: Vector3) -> Vector3:
    x, y, z = dimensions_m
    return (
        mass_kg * (y * y + z * z) / 12.0,
        mass_kg * (x * x + z * z) / 12.0,
        mass_kg * (x * x + y * y) / 12.0,
    )
