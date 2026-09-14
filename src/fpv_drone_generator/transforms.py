from __future__ import annotations

import math

from .catalog import Vector3


Quaternion = tuple[float, float, float, float]


def quaternion_from_rpy_deg(rpy_deg: Vector3) -> Quaternion:
    roll, pitch, yaw = (math.radians(value) / 2.0 for value in rpy_deg)
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return (
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    )


def multiply_quaternions(left: Quaternion, right: Quaternion) -> Quaternion:
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return (
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    )


def normalize_quaternion(value: Quaternion) -> Quaternion:
    magnitude = math.sqrt(sum(component * component for component in value))
    if magnitude == 0.0:
        raise ValueError("quaternion must not be zero")
    return tuple(component / magnitude for component in value)  # type: ignore[return-value]


def inverse_quaternion(value: Quaternion) -> Quaternion:
    normalized = normalize_quaternion(value)
    return (normalized[0], -normalized[1], -normalized[2], -normalized[3])


def compose_transform(
    first_position_m: Vector3,
    first_rotation: Quaternion,
    second_position_m: Vector3,
    second_rotation: Quaternion,
) -> tuple[Vector3, Quaternion]:
    return (
        transform_point(first_position_m, first_rotation, second_position_m),
        normalize_quaternion(multiply_quaternions(first_rotation, second_rotation)),
    )


def inverse_transform(position_m: Vector3, rotation: Quaternion) -> tuple[Vector3, Quaternion]:
    inverse_rotation = inverse_quaternion(rotation)
    return (
        rotate_vector(inverse_rotation, (-position_m[0], -position_m[1], -position_m[2])),
        inverse_rotation,
    )


def rpy_deg_from_quaternion(value: Quaternion) -> Vector3:
    w, x, y, z = normalize_quaternion(value)
    roll = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    pitch_sine = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    pitch = math.asin(pitch_sine)
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return (math.degrees(roll), math.degrees(pitch), math.degrees(yaw))


def rotate_vector(rotation: Quaternion, value: Vector3) -> Vector3:
    pure = (0.0, value[0], value[1], value[2])
    conjugate = (rotation[0], -rotation[1], -rotation[2], -rotation[3])
    result = multiply_quaternions(multiply_quaternions(rotation, pure), conjugate)
    return (result[1], result[2], result[3])


def transform_point(position_m: Vector3, rotation: Quaternion, local: Vector3) -> Vector3:
    rotated = rotate_vector(rotation, local)
    return tuple(position_m[index] + rotated[index] for index in range(3))  # type: ignore[return-value]
