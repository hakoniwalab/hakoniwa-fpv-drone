from __future__ import annotations

from dataclasses import dataclass

from .catalog import Attachment, Battery, Camera, Controller, Frame, LandingGear, Motor, Propeller, Vector3
from .recipe import VehicleRecipe


@dataclass(frozen=True)
class Rotor:
    name: str
    position_m: Vector3
    legacy_drone_pro_position_frd_m: Vector3 | None
    rotation_direction: float


@dataclass(frozen=True)
class ResolvedComponents:
    frame: Frame
    motor: Motor
    propeller: Propeller
    battery: Battery
    camera: Camera
    controller: Controller
    landing_gear: LandingGear | None


@dataclass(frozen=True)
class ResolvedAttachment:
    name: str
    component: Attachment
    parent: str
    position_m: Vector3
    rpy_deg: Vector3


@dataclass(frozen=True)
class ResolvedVehicle:
    recipe: VehicleRecipe
    components: ResolvedComponents
    total_mass_kg: float
    center_of_mass_m: Vector3 | None
    inertia_kg_m2: Vector3 | None
    rotors: tuple[Rotor, ...]
    attachments: tuple[ResolvedAttachment, ...]
    max_rad_per_sec: float
    max_rad_per_sec_source: str
    estimated_max_thrust_n: float
    thrust_to_weight_ratio: float
    approximations: tuple[str, ...]
