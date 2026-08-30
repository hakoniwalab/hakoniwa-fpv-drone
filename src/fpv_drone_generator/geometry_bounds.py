from __future__ import annotations

import math

from .catalog import GeometryAssembly, GeometryPrimitive, Vector3
from .model import ResolvedVehicle
from .transforms import multiply_quaternions, quaternion_from_rpy_deg, rotate_vector, transform_point


def _primitive_min_z(primitive: GeometryPrimitive, position_m: Vector3, rpy_deg: Vector3) -> float:
    mount_rotation = quaternion_from_rpy_deg(rpy_deg)
    rotation = multiply_quaternions(mount_rotation, quaternion_from_rpy_deg(primitive.rpy_deg))
    center = transform_point(position_m, mount_rotation, primitive.center_m)
    if primitive.primitive_type == "sphere":
        assert primitive.radius_m is not None
        extent = primitive.radius_m
    elif primitive.primitive_type == "box":
        assert primitive.dimensions_m is not None
        axes = tuple(rotate_vector(rotation, axis) for axis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
        extent = sum(abs(axes[index][2]) * primitive.dimensions_m[index] / 2.0 for index in range(3))
    else:
        assert primitive.radius_m is not None and primitive.length_m is not None
        axis = rotate_vector(rotation, (0.0, 0.0, 1.0))
        axial = abs(axis[2]) * primitive.length_m / 2.0
        if primitive.primitive_type == "capsule":
            extent = axial + primitive.radius_m
        else:
            extent = axial + primitive.radius_m * math.sqrt(max(0.0, 1.0 - axis[2] * axis[2]))
    return center[2] - extent


def _assembly_min_z(assembly: GeometryAssembly | None, position_m: Vector3 = (0.0, 0.0, 0.0), rpy_deg: Vector3 = (0.0, 0.0, 0.0)) -> list[float]:
    if assembly is None:
        return []
    return [_primitive_min_z(primitive, position_m, rpy_deg) for primitive in assembly.collision]


def vehicle_collision_lower_bound(vehicle: ResolvedVehicle) -> float:
    values = _assembly_min_z(vehicle.components.frame.geometry)
    if vehicle.components.landing_gear is not None:
        values.extend(_assembly_min_z(
            vehicle.components.landing_gear.geometry,
            vehicle.recipe.placements.landing_gear.position_m,
            vehicle.recipe.placements.landing_gear.rpy_deg,
        ))
    for attachment in vehicle.attachments:
        values.extend(_assembly_min_z(attachment.component.geometry, attachment.position_m, attachment.rpy_deg))
    if not values:
        raise ValueError("schema v2 vehicle requires at least one collision primitive for automatic ground placement")
    return min(values)
