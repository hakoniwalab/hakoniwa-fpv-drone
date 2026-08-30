from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .yaml_io import load_yaml


Vector3 = tuple[float, float, float]


def _ref(raw: Any, path: str) -> str:
    if isinstance(raw, str) and raw:
        return raw
    if isinstance(raw, dict) and isinstance(raw.get("product"), str) and raw["product"]:
        return raw["product"]
    raise ValidationError(f"{path} must be a catalog id or an object containing product")


def _position(raw: Any, path: str) -> Vector3:
    if not isinstance(raw, list) or len(raw) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in raw):
        raise ValidationError(f"{path} must contain three numbers")
    return (float(raw[0]), float(raw[1]), float(raw[2]))


@dataclass(frozen=True)
class ComponentReferences:
    frame: str
    motor: str
    motor_count: int
    propeller: str
    battery: str
    camera: str
    controller: str
    landing_gear: str | None


@dataclass(frozen=True)
class Placement:
    position_m: Vector3
    rpy_deg: Vector3
    parent: str = "frame"


@dataclass(frozen=True)
class Placements:
    battery: Placement
    camera: Placement
    controller: Placement
    landing_gear: Placement

    # Compatibility accessors keep the v1 generator path and third-party callers stable.
    @property
    def battery_m(self) -> Vector3:
        return self.battery.position_m

    @property
    def camera_m(self) -> Vector3:
        return self.camera.position_m

    @property
    def controller_m(self) -> Vector3:
        return self.controller.position_m

    @property
    def landing_gear_m(self) -> Vector3:
        return self.landing_gear.position_m

    @property
    def landing_gear_rpy_deg(self) -> Vector3:
        return self.landing_gear.rpy_deg


@dataclass(frozen=True)
class AttachmentReference:
    name: str
    product: str
    parent: str
    position_m: Vector3
    rpy_deg: Vector3


@dataclass(frozen=True)
class RotorLayoutReference:
    name: str
    position_flu_m: Vector3
    rotation_direction: float


@dataclass(frozen=True)
class VehicleRecipe:
    path: Path
    schema_version: int
    name: str
    vehicle_type: str
    components: ComponentReferences
    controller_mode: str
    placements: Placements
    attachments: tuple[AttachmentReference, ...]
    rotor_contract: str | None
    rotor_layout: tuple[RotorLayoutReference, ...]
    ground_clearance_m: float
    raw: dict[str, Any]


def load_recipe(path: Path) -> VehicleRecipe:
    path = path.resolve()
    raw = load_yaml(path)
    schema_version = raw.get("schema_version")
    if schema_version not in (1, 2):
        raise ValidationError("recipe.schema_version must be 1 or 2")
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise ValidationError("recipe.name must be a non-empty string")
    vehicle_type = raw.get("type")
    if vehicle_type not in ("quad_x", "multirotor"):
        raise ValidationError("recipe.type must be quad_x or multirotor")
    components = raw.get("components")
    if not isinstance(components, dict):
        raise ValidationError("recipe.components must be an object")
    motors_raw = components.get("motors")
    motor_count = motors_raw.get("count") if isinstance(motors_raw, dict) else None
    if not isinstance(motor_count, int) or isinstance(motor_count, bool) or motor_count < 4:
        raise ValidationError("components.motors.count must be an integer of at least 4")
    if vehicle_type == "quad_x" and motor_count != 4:
        raise ValidationError("quad_x requires components.motors.count: 4")
    controller_raw = raw.get("controller")
    if not isinstance(controller_raw, dict):
        raise ValidationError("recipe.controller must be an object")
    mode = controller_raw.get("mode")
    if mode not in ("rate", "angle"):
        raise ValidationError("recipe.controller.mode must be rate or angle")
    placements_raw = raw.get("placements", {})
    if not isinstance(placements_raw, dict):
        raise ValidationError("recipe.placements must be an object")
    attachments_raw = raw.get("attachments", [])
    if not isinstance(attachments_raw, list):
        raise ValidationError("recipe.attachments must be an array")
    attachments: list[AttachmentReference] = []

    def placement(name: str) -> Placement:
        entry = placements_raw.get(name)
        if entry is None:
            return Placement(
                _position(placements_raw.get(f"{name}_m", [0, 0, 0]), f"placements.{name}_m"),
                _position(placements_raw.get(f"{name}_rpy_deg", [0, 0, 0]), f"placements.{name}_rpy_deg"),
            )
        if schema_version < 2:
            raise ValidationError(f"placements.{name} object requires recipe schema v2")
        if not isinstance(entry, dict):
            raise ValidationError(f"placements.{name} must be an object")
        parent = entry.get("parent", "frame")
        if parent != "frame":
            raise ValidationError(f"placements.{name}.parent must be frame")
        return Placement(
            _position(entry.get("position_m", [0, 0, 0]), f"placements.{name}.position_m"),
            _position(entry.get("rpy_deg", [0, 0, 0]), f"placements.{name}.rpy_deg"),
            parent,
        )
    names: set[str] = set()
    for index, entry in enumerate(attachments_raw):
        path_prefix = f"attachments[{index}]"
        if not isinstance(entry, dict):
            raise ValidationError(f"{path_prefix} must be an object")
        attachment_name = entry.get("name")
        if not isinstance(attachment_name, str) or not attachment_name:
            raise ValidationError(f"{path_prefix}.name must be a non-empty string")
        if attachment_name in names:
            raise ValidationError(f"duplicate attachment name: {attachment_name}")
        names.add(attachment_name)
        parent = entry.get("parent", "frame")
        if parent != "frame":
            raise ValidationError(f"{path_prefix}.parent must be frame")
        attachments.append(AttachmentReference(
            name=attachment_name,
            product=_ref(entry.get("product"), f"{path_prefix}.product"),
            parent=parent,
            position_m=_position(entry.get("position_m", [0, 0, 0]), f"{path_prefix}.position_m"),
            rpy_deg=_position(entry.get("rpy_deg", [0, 0, 0]), f"{path_prefix}.rpy_deg"),
        ))
    rotor_layout_raw = raw.get("rotor_layout")
    rotor_contract: str | None = None
    rotor_layout: list[RotorLayoutReference] = []
    if rotor_layout_raw is not None:
        if not isinstance(rotor_layout_raw, dict):
            raise ValidationError("recipe.rotor_layout must be an object")
        rotor_contract = rotor_layout_raw.get("contract")
        if not isinstance(rotor_contract, str) or not rotor_contract:
            raise ValidationError("recipe.rotor_layout.contract must be a non-empty string")
        entries = rotor_layout_raw.get("rotors")
        if not isinstance(entries, list) or len(entries) != motor_count:
            raise ValidationError("recipe.rotor_layout.rotors count must match components.motors.count")
        rotor_names: set[str] = set()
        for index, entry in enumerate(entries):
            entry_path = f"rotor_layout.rotors[{index}]"
            if not isinstance(entry, dict):
                raise ValidationError(f"{entry_path} must be an object")
            rotor_name = entry.get("name")
            if not isinstance(rotor_name, str) or not rotor_name or rotor_name in rotor_names:
                raise ValidationError(f"{entry_path}.name must be non-empty and unique")
            rotor_names.add(rotor_name)
            direction = entry.get("rotation_direction")
            if isinstance(direction, bool) or direction not in (-1, 1, -1.0, 1.0):
                raise ValidationError(f"{entry_path}.rotation_direction must be -1 or 1")
            rotor_layout.append(RotorLayoutReference(
                name=rotor_name,
                position_flu_m=_position(entry.get("position_flu_m"), f"{entry_path}.position_flu_m"),
                rotation_direction=float(direction),
            ))
    if schema_version >= 2 and not rotor_layout:
        raise ValidationError("recipe schema v2 requires explicit rotor_layout")
    initial_pose = raw.get("initial_pose", {})
    if not isinstance(initial_pose, dict):
        raise ValidationError("recipe.initial_pose must be an object")
    ground_clearance = initial_pose.get("ground_clearance_m", 0.01)
    if isinstance(ground_clearance, bool) or not isinstance(ground_clearance, (int, float)) or ground_clearance < 0.0:
        raise ValidationError("recipe.initial_pose.ground_clearance_m must be a non-negative number")
    return VehicleRecipe(
        path=path,
        schema_version=schema_version,
        name=name,
        vehicle_type=vehicle_type,
        components=ComponentReferences(
            frame=_ref(components.get("frame"), "components.frame"),
            motor=_ref(motors_raw, "components.motors"),
            motor_count=motor_count,
            propeller=_ref(components.get("propeller"), "components.propeller"),
            battery=_ref(components.get("battery"), "components.battery"),
            camera=_ref(components.get("camera"), "components.camera"),
            controller=_ref(controller_raw, "controller"),
            landing_gear=None if components.get("landing_gear") is None else _ref(components.get("landing_gear"), "components.landing_gear"),
        ),
        controller_mode=mode,
        placements=Placements(
            battery=placement("battery"),
            camera=placement("camera"),
            controller=placement("controller"),
            landing_gear=placement("landing_gear"),
        ),
        attachments=tuple(attachments),
        rotor_contract=rotor_contract,
        rotor_layout=tuple(rotor_layout),
        ground_clearance_m=float(ground_clearance),
        raw=raw,
    )
