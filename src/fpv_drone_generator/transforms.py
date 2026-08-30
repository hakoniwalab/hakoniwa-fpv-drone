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


def rotate_vector(rotation: Quaternion, value: Vector3) -> Vector3:
    pure = (0.0, value[0], value[1], value[2])
    conjugate = (rotation[0], -rotation[1], -rotation[2], -rotation[3])
    result = multiply_quaternions(multiply_quaternions(rotation, pure), conjugate)
    return (result[1], result[2], result[3])


def transform_point(position_m: Vector3, rotation: Quaternion, local: Vector3) -> Vector3:
    rotated = rotate_vector(rotation, local)
    return tuple(position_m[index] + rotated[index] for index in range(3))  # type: ignore[return-value]
