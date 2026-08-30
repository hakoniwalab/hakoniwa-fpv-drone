from __future__ import annotations

import math

from .catalog import CatalogStore, Vector3
from .errors import ResolutionError
from .model import ResolvedAttachment, ResolvedComponents, ResolvedVehicle, Rotor
from .physics.inertia import add_diagonals, box_diagonal, point_mass_diagonal
from .physics.mass import weighted_center
from .physics.propulsion import max_rotor_speed_rad_s, max_total_thrust_n
from .recipe import VehicleRecipe


def _rotors(recipe: VehicleRecipe, wheelbase_m: float, positions: tuple[Vector3, ...] | None) -> tuple[Rotor, ...]:
    if recipe.rotor_layout:
        if positions is not None:
            for index, entry in enumerate(recipe.rotor_layout):
                if any(abs(entry.position_flu_m[axis] - positions[index][axis]) > 1.0e-9 for axis in range(3)):
                    raise ResolutionError("frame motor mounts must match rotor_layout MuJoCo positions and order")
        return tuple(Rotor(entry.name, entry.position_flu_m, None, entry.rotation_direction) for entry in recipe.rotor_layout)
    arm = wheelbase_m / (2.0 * math.sqrt(2.0))
    # Order and signs follow the existing Hakoniwa quad-X mixer fixtures.
    return (
        Rotor("prop1", (arm, -arm, 0.0), (arm, arm, 0.0), -1.0),
        Rotor("prop2", (arm, arm, 0.0), (arm, -arm, 0.0), 1.0),
        Rotor("prop3", (-arm, arm, 0.0), (-arm, -arm, 0.0), -1.0),
        Rotor("prop4", (-arm, -arm, 0.0), (-arm, arm, 0.0), 1.0),
    )


def resolve_vehicle(recipe: VehicleRecipe, catalogs: CatalogStore) -> ResolvedVehicle:
    refs = recipe.components
    components = ResolvedComponents(
        frame=catalogs.frames.get(refs.frame),
        motor=catalogs.motors.get(refs.motor),
        propeller=catalogs.propellers.get(refs.propeller),
        battery=catalogs.batteries.get(refs.battery),
        camera=catalogs.cameras.get(refs.camera),
        controller=catalogs.controllers.get(refs.controller),
        landing_gear=None if refs.landing_gear is None else catalogs.landing_gears.get(refs.landing_gear),
    )
    if components.controller.backend != "hakoniwa":
        raise ResolutionError("MVP implements only controller backend: hakoniwa")
    if recipe.controller_mode not in components.controller.supported_modes:
        raise ResolutionError(f"controller {components.controller.id} does not support mode {recipe.controller_mode}")

    if components.frame.motor_mount_positions_m is not None and len(components.frame.motor_mount_positions_m) != refs.motor_count:
        raise ResolutionError("frame motor mount count must match components.motors.count")
    rotors = _rotors(recipe, components.frame.wheelbase_m, components.frame.motor_mount_positions_m)
    attachments = tuple(
        ResolvedAttachment(
            name=reference.name,
            component=catalogs.attachments.get(reference.product),
            parent=reference.parent,
            position_m=reference.position_m,
            rpy_deg=reference.rpy_deg,
        )
        for reference in recipe.attachments
    )
    if recipe.schema_version >= 2:
        physical_components = [
            ("frame", components.frame),
            ("motor", components.motor),
            ("propeller", components.propeller),
            ("battery", components.battery),
            ("camera", components.camera),
            ("controller", components.controller),
        ]
        if components.landing_gear is not None:
            physical_components.append(("landing_gear", components.landing_gear))
        physical_components.extend(
            (f"attachment {attachment.name}", attachment.component)
            for attachment in attachments
            if attachment.component.physical_role == "physical"
        )
        for label, component in physical_components:
            if component.geometry is None or not component.geometry.inertial:
                raise ResolutionError(f"schema v2 physical {label} requires geometry.inertial")
    frame_position: Vector3 = (0.0, 0.0, 0.0)
    masses: list[tuple[float, Vector3]] = [(components.frame.mass_kg, frame_position)]
    for rotor in rotors:
        masses.append((components.motor.mass_kg, rotor.position_m))
        masses.append((components.propeller.mass_kg, rotor.position_m))
    masses.extend(
        [
            (components.battery.mass_kg, recipe.placements.battery_m),
            (components.camera.mass_kg, recipe.placements.camera_m),
            (components.controller.mass_kg, recipe.placements.controller_m),
        ]
    )
    if components.landing_gear is not None:
        masses.append((components.landing_gear.mass_kg, recipe.placements.landing_gear_m))
    for attachment in attachments:
        if attachment.component.physical_role == "physical" and attachment.component.mass_kg > 0.0:
            masses.append((attachment.component.mass_kg, attachment.position_m))
    total_mass = sum(mass for mass, _ in masses)
    center = weighted_center(masses) if recipe.schema_version == 1 else None

    approximations: list[str] = []
    if recipe.schema_version >= 2:
        inertia = None
        approximations.append("rigid-body center of mass and inertia: delegated to MuJoCo geometry inference")
    elif components.frame.legacy_inertia_kg_m2 is None:
        frame_inertia = box_diagonal(components.frame.mass_kg, components.frame.dimensions_m)
        approximations.append("frame inertia: uniform box from catalog dimensions")
        inertia_terms = [frame_inertia, point_mass_diagonal(components.frame.mass_kg, frame_position, center)]
        for mass, position in masses[1:]:
            inertia_terms.append(point_mass_diagonal(mass, position, center))
        inertia = add_diagonals(inertia_terms)
        approximations.append("non-frame component inertia: point masses at recipe placements")
    else:
        frame_inertia = components.frame.legacy_inertia_kg_m2
        inertia_terms = [frame_inertia, point_mass_diagonal(components.frame.mass_kg, frame_position, center)]
        for mass, position in masses[1:]:
            inertia_terms.append(point_mass_diagonal(mass, position, center))
        inertia = add_diagonals(inertia_terms)
        approximations.append("legacy v1 frame inertia plus non-frame point masses")

    max_speed, speed_source = max_rotor_speed_rad_s(components.motor.kv_rpm_per_v, components.battery.nominal_voltage_v, components.motor.max_rad_per_sec)
    if speed_source != "catalog":
        approximations.append(f"motor maximum speed: {speed_source}")
    max_thrust = max_total_thrust_n(len(rotors), components.propeller.thrust_coefficient_ns2_rad2, max_speed)
    ratio = max_thrust / (total_mass * 9.81)
    return ResolvedVehicle(
        recipe=recipe,
        components=components,
        total_mass_kg=total_mass,
        center_of_mass_m=center,
        inertia_kg_m2=inertia,
        rotors=rotors,
        attachments=attachments,
        max_rad_per_sec=max_speed,
        max_rad_per_sec_source=speed_source,
        estimated_max_thrust_n=max_thrust,
        thrust_to_weight_ratio=ratio,
        approximations=tuple(approximations),
    )
