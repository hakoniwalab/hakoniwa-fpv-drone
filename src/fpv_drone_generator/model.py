from __future__ import annotations

from dataclasses import dataclass

from .catalog import Battery, Camera, Controller, Frame, Motor, Propeller, Vector3
from .recipe import VehicleRecipe


@dataclass(frozen=True)
class Rotor:
    name: str
    position_m: Vector3
    rotation_direction: float


@dataclass(frozen=True)
class ResolvedComponents:
    frame: Frame
    motor: Motor
    propeller: Propeller
    battery: Battery
    camera: Camera
    controller: Controller


@dataclass(frozen=True)
class ResolvedVehicle:
    recipe: VehicleRecipe
    components: ResolvedComponents
    total_mass_kg: float
    center_of_mass_m: Vector3
    inertia_kg_m2: Vector3
    rotors: tuple[Rotor, Rotor, Rotor, Rotor]
    max_rad_per_sec: float
    max_rad_per_sec_source: str
    estimated_max_thrust_n: float
    thrust_to_weight_ratio: float
    approximations: tuple[str, ...]
