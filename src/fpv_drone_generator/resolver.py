from __future__ import annotations

import math

from .catalog import CatalogStore, Vector3
from .errors import ResolutionError
from .model import ResolvedComponents, ResolvedVehicle, Rotor
from .physics.inertia import add_diagonals, box_diagonal, point_mass_diagonal
from .physics.mass import weighted_center
from .physics.propulsion import max_rotor_speed_rad_s, max_total_thrust_n
from .recipe import VehicleRecipe


def _rotors(wheelbase_m: float) -> tuple[Rotor, Rotor, Rotor, Rotor]:
    arm = wheelbase_m / (2.0 * math.sqrt(2.0))
    # Order and signs follow the existing Hakoniwa quad-X mixer fixtures.
    return (
        Rotor("prop1", (arm, -arm, 0.0), -1.0),
        Rotor("prop2", (arm, arm, 0.0), 1.0),
        Rotor("prop3", (-arm, arm, 0.0), -1.0),
        Rotor("prop4", (-arm, -arm, 0.0), 1.0),
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
    )
    if components.controller.backend != "hakoniwa":
        raise ResolutionError("MVP implements only controller backend: hakoniwa")
    if recipe.controller_mode not in components.controller.supported_modes:
        raise ResolutionError(f"controller {components.controller.id} does not support mode {recipe.controller_mode}")

    rotors = _rotors(components.frame.wheelbase_m)
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
    total_mass = sum(mass for mass, _ in masses)
    center = weighted_center(masses)

    approximations: list[str] = []
    if components.frame.inertia_kg_m2 is None:
        frame_inertia = box_diagonal(components.frame.mass_kg, components.frame.dimensions_m)
        approximations.append("frame inertia: uniform box from catalog dimensions")
    else:
        frame_inertia = components.frame.inertia_kg_m2
    inertia_terms = [frame_inertia, point_mass_diagonal(components.frame.mass_kg, frame_position, center)]
    for mass, position in masses[1:]:
        inertia_terms.append(point_mass_diagonal(mass, position, center))
    inertia = add_diagonals(inertia_terms)
    approximations.append("non-frame component inertia: point masses at recipe/catalog mount positions")

    max_speed, speed_source = max_rotor_speed_rad_s(components.motor.kv_rpm_per_v, components.battery.nominal_voltage_v, components.motor.max_rad_per_sec)
    if speed_source != "catalog":
        approximations.append(f"motor maximum speed: {speed_source}")
    max_thrust = max_total_thrust_n(4, components.propeller.thrust_coefficient_ns2_rad2, max_speed)
    ratio = max_thrust / (total_mass * 9.81)
    return ResolvedVehicle(
        recipe=recipe,
        components=components,
        total_mass_kg=total_mass,
        center_of_mass_m=center,
        inertia_kg_m2=inertia,
        rotors=rotors,
        max_rad_per_sec=max_speed,
        max_rad_per_sec_source=speed_source,
        estimated_max_thrust_n=max_thrust,
        thrust_to_weight_ratio=ratio,
        approximations=tuple(approximations),
    )
