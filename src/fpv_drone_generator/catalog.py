from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable
from typing import Any, Generic, TypeVar

from .errors import ResolutionError, ValidationError
from .yaml_io import load_yaml


Vector3 = tuple[float, float, float]
Vector4 = tuple[float, float, float, float]


def _number(value: Any, path: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{path} must be a number")
    result = float(value)
    if positive and result <= 0.0:
        raise ValidationError(f"{path} must be greater than zero")
    return result


def _vector3(value: Any, path: str, *, positive: bool = False) -> Vector3:
    if not isinstance(value, list) or len(value) != 3:
        raise ValidationError(f"{path} must contain three numbers")
    return tuple(_number(item, f"{path}[{index}]", positive=positive) for index, item in enumerate(value))  # type: ignore[return-value]


def _vector4(value: Any, path: str) -> Vector4:
    if not isinstance(value, list) or len(value) != 4:
        raise ValidationError(f"{path} must contain four numbers")
    return tuple(_number(item, f"{path}[{index}]") for index, item in enumerate(value))  # type: ignore[return-value]


@dataclass(frozen=True)
class GeometryPrimitive:
    name: str
    primitive_type: str
    center_m: Vector3
    rpy_deg: Vector3
    rgba: Vector4
    dimensions_m: Vector3 | None = None
    radius_m: float | None = None
    length_m: float | None = None
    friction: Vector3 | None = None


@dataclass(frozen=True)
class GeometryAssembly:
    visual: tuple[GeometryPrimitive, ...]
    collision: tuple[GeometryPrimitive, ...]
    inertial: tuple[GeometryPrimitive, ...]


@dataclass(frozen=True)
class Common:
    id: str
    name: str
    vendor: str | None
    description: str
    metadata: dict[str, Any]
    geometry: GeometryAssembly | None


@dataclass(frozen=True)
class Frame(Common):
    mass_kg: float
    dimensions_m: Vector3
    wheelbase_m: float
    legacy_inertia_kg_m2: Vector3 | None
    motor_mount_positions_m: tuple[Vector3, ...] | None


@dataclass(frozen=True)
class Motor(Common):
    mass_kg: float
    kv_rpm_per_v: float
    max_current_a: float | None
    resistance_ohm: float
    torque_constant_nm_per_a: float
    viscous_drag_nm_s_per_rad: float
    rotor_inertia_kg_m2: float
    max_rad_per_sec: float | None


@dataclass(frozen=True)
class Propeller(Common):
    mass_kg: float
    diameter_m: float
    pitch_m: float
    blade_count: int
    thrust_coefficient_ns2_rad2: float
    torque_coefficient_nms2_rad2: float


@dataclass(frozen=True)
class Battery(Common):
    mass_kg: float
    dimensions_m: Vector3
    cell_count: int
    nominal_voltage_v: float
    capacity_ah: float
    internal_resistance_ohm: float | None


@dataclass(frozen=True)
class Camera(Common):
    mass_kg: float
    dimensions_m: Vector3
    fov_deg: float | None


@dataclass(frozen=True)
class Controller(Common):
    mass_kg: float
    backend: str
    supported_modes: tuple[str, ...]
    default_mode: str
    parameters: dict[str, float]
    parameter_origins: dict[str, str]


@dataclass(frozen=True)
class LandingGear(Common):
    mass_kg: float


@dataclass(frozen=True)
class Attachment(Common):
    mass_kg: float
    physical_role: str


CatalogType = Frame | Motor | Propeller | Battery | Camera | Controller | LandingGear | Attachment
T = TypeVar("T", bound=CatalogType)


@dataclass(frozen=True)
class CatalogGroup(Generic[T]):
    kind: str
    items: dict[str, T]

    def get(self, item_id: str) -> T:
        try:
            return self.items[item_id]
        except KeyError as exc:
            raise ResolutionError(f"unknown {self.kind} catalog id: {item_id}") from exc


@dataclass(frozen=True)
class CatalogStore:
    root: Path
    roots: tuple[Path, ...]
    frames: CatalogGroup[Frame]
    motors: CatalogGroup[Motor]
    propellers: CatalogGroup[Propeller]
    batteries: CatalogGroup[Battery]
    cameras: CatalogGroup[Camera]
    controllers: CatalogGroup[Controller]
    landing_gears: CatalogGroup[LandingGear]
    attachments: CatalogGroup[Attachment]


def _make_primitive(raw: Any, path: str) -> GeometryPrimitive:
    if not isinstance(raw, dict):
        raise ValidationError(f"{path} must be an object")
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise ValidationError(f"{path}.name must be a non-empty string")
    primitive_type = raw.get("type")
    if primitive_type not in ("box", "cylinder", "capsule", "sphere"):
        raise ValidationError(f"{path}.type must be box, cylinder, capsule, or sphere")
    dimensions = raw.get("dimensions_m")
    radius = raw.get("radius_m")
    length = raw.get("length_m")
    if primitive_type == "box":
        if dimensions is None:
            raise ValidationError(f"{path}.dimensions_m is required for box")
        dimensions_m = _vector3(dimensions, f"{path}.dimensions_m", positive=True)
        radius_m = None
        length_m = None
    elif primitive_type in ("cylinder", "capsule"):
        dimensions_m = None
        radius_m = _number(radius, f"{path}.radius_m", positive=True)
        length_m = _number(length, f"{path}.length_m", positive=True)
    else:
        dimensions_m = None
        radius_m = _number(radius, f"{path}.radius_m", positive=True)
        length_m = None
    friction_raw = raw.get("friction")
    friction = None if friction_raw is None else _vector3(friction_raw, f"{path}.friction")
    if friction is not None and any(value < 0.0 for value in friction):
        raise ValidationError(f"{path}.friction values must not be negative")
    return GeometryPrimitive(
        name=name,
        primitive_type=primitive_type,
        center_m=_vector3(raw.get("center_m", [0, 0, 0]), f"{path}.center_m"),
        rpy_deg=_vector3(raw.get("rpy_deg", [0, 0, 0]), f"{path}.rpy_deg"),
        rgba=_vector4(raw.get("rgba", [0.35, 0.35, 0.38, 1.0]), f"{path}.rgba"),
        dimensions_m=dimensions_m,
        radius_m=radius_m,
        length_m=length_m,
        friction=friction,
    )


def _make_geometry(raw: Any, path: str, *, required: bool = False) -> GeometryAssembly | None:
    if raw is None and not required:
        return None
    if not isinstance(raw, dict):
        raise ValidationError(f"{path} must be an object")
    result: dict[str, tuple[GeometryPrimitive, ...]] = {}
    for role in ("visual", "collision", "inertial"):
        entries = raw.get(role, [])
        if not isinstance(entries, list):
            raise ValidationError(f"{path}.{role} must be an array")
        result[role] = tuple(_make_primitive(entry, f"{path}.{role}[{index}]") for index, entry in enumerate(entries))
    if required and not result["visual"] and not result["collision"]:
        raise ValidationError(f"{path} must contain at least one primitive")
    names = [primitive.name for role in result.values() for primitive in role]
    if len(names) != len(set(names)):
        raise ValidationError(f"{path} primitive names must be unique")
    return GeometryAssembly(visual=result["visual"], collision=result["collision"], inertial=result["inertial"])


def _common(raw: dict[str, Any], path: str) -> Common:
    item_id = raw.get("id")
    name = raw.get("name")
    if not isinstance(item_id, str) or not item_id:
        raise ValidationError(f"{path}.id must be a non-empty string")
    if not isinstance(name, str) or not name:
        raise ValidationError(f"{path}.name must be a non-empty string")
    vendor = raw.get("vendor")
    if vendor is not None and not isinstance(vendor, str):
        raise ValidationError(f"{path}.vendor must be a string or null")
    description = raw.get("description", "")
    if not isinstance(description, str):
        raise ValidationError(f"{path}.description must be a string")
    metadata = raw.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValidationError(f"{path}.metadata must be an object")
    return Common(item_id, name, vendor, description, metadata, _make_geometry(raw.get("geometry"), f"{path}.geometry"))


def _make_frame(raw: dict[str, Any], path: str) -> Frame:
    common = _common(raw, path)
    inertia = raw.get("inertia_kg_m2")
    mounts_raw = raw.get("motor_mount_positions_m")
    mounts = None
    if mounts_raw is not None:
        if not isinstance(mounts_raw, list) or len(mounts_raw) < 4:
            raise ValidationError(f"{path}.motor_mount_positions_m must contain at least four positions")
        mounts = tuple(_vector3(value, f"{path}.motor_mount_positions_m[{index}]") for index, value in enumerate(mounts_raw))
    return Frame(**common.__dict__, mass_kg=_number(raw.get("mass_kg"), f"{path}.mass_kg", positive=True), dimensions_m=_vector3(raw.get("dimensions_m"), f"{path}.dimensions_m", positive=True), wheelbase_m=_number(raw.get("wheelbase_m"), f"{path}.wheelbase_m", positive=True), legacy_inertia_kg_m2=None if inertia is None else _vector3(inertia, f"{path}.inertia_kg_m2", positive=True), motor_mount_positions_m=mounts)


def _make_motor(raw: dict[str, Any], path: str) -> Motor:
    common = _common(raw, path)
    dynamics = raw.get("dynamics")
    if not isinstance(dynamics, dict):
        raise ValidationError(f"{path}.dynamics must be an object")
    max_current = raw.get("max_current_a")
    max_speed = dynamics.get("max_rad_per_sec")
    return Motor(
        **common.__dict__,
        mass_kg=_number(raw.get("mass_kg"), f"{path}.mass_kg", positive=True),
        kv_rpm_per_v=_number(raw.get("kv_rpm_per_v"), f"{path}.kv_rpm_per_v", positive=True),
        max_current_a=None if max_current is None else _number(max_current, f"{path}.max_current_a", positive=True),
        resistance_ohm=_number(dynamics.get("resistance_ohm"), f"{path}.dynamics.resistance_ohm", positive=True),
        torque_constant_nm_per_a=_number(dynamics.get("torque_constant_nm_per_a"), f"{path}.dynamics.torque_constant_nm_per_a", positive=True),
        viscous_drag_nm_s_per_rad=_number(dynamics.get("viscous_drag_nm_s_per_rad", 0.0), f"{path}.dynamics.viscous_drag_nm_s_per_rad"),
        rotor_inertia_kg_m2=_number(dynamics.get("rotor_inertia_kg_m2"), f"{path}.dynamics.rotor_inertia_kg_m2", positive=True),
        max_rad_per_sec=None if max_speed is None else _number(max_speed, f"{path}.dynamics.max_rad_per_sec", positive=True),
    )


def _make_propeller(raw: dict[str, Any], path: str) -> Propeller:
    common = _common(raw, path)
    blade_count = raw.get("blade_count")
    if not isinstance(blade_count, int) or isinstance(blade_count, bool) or blade_count <= 0:
        raise ValidationError(f"{path}.blade_count must be a positive integer")
    return Propeller(**common.__dict__, mass_kg=_number(raw.get("mass_kg"), f"{path}.mass_kg", positive=True), diameter_m=_number(raw.get("diameter_m"), f"{path}.diameter_m", positive=True), pitch_m=_number(raw.get("pitch_m"), f"{path}.pitch_m", positive=True), blade_count=blade_count, thrust_coefficient_ns2_rad2=_number(raw.get("thrust_coefficient_ns2_rad2"), f"{path}.thrust_coefficient_ns2_rad2", positive=True), torque_coefficient_nms2_rad2=_number(raw.get("torque_coefficient_nms2_rad2"), f"{path}.torque_coefficient_nms2_rad2", positive=True))


def _make_battery(raw: dict[str, Any], path: str) -> Battery:
    common = _common(raw, path)
    cells = raw.get("cell_count")
    if not isinstance(cells, int) or isinstance(cells, bool) or cells <= 0:
        raise ValidationError(f"{path}.cell_count must be a positive integer")
    resistance = raw.get("internal_resistance_ohm")
    return Battery(**common.__dict__, mass_kg=_number(raw.get("mass_kg"), f"{path}.mass_kg", positive=True), dimensions_m=_vector3(raw.get("dimensions_m"), f"{path}.dimensions_m", positive=True), cell_count=cells, nominal_voltage_v=_number(raw.get("nominal_voltage_v"), f"{path}.nominal_voltage_v", positive=True), capacity_ah=_number(raw.get("capacity_ah"), f"{path}.capacity_ah", positive=True), internal_resistance_ohm=None if resistance is None else _number(resistance, f"{path}.internal_resistance_ohm", positive=True))


def _make_camera(raw: dict[str, Any], path: str) -> Camera:
    common = _common(raw, path)
    fov = raw.get("fov_deg")
    return Camera(**common.__dict__, mass_kg=_number(raw.get("mass_kg"), f"{path}.mass_kg", positive=True), dimensions_m=_vector3(raw.get("dimensions_m"), f"{path}.dimensions_m", positive=True), fov_deg=None if fov is None else _number(fov, f"{path}.fov_deg", positive=True))


def _make_controller(raw: dict[str, Any], path: str) -> Controller:
    common = _common(raw, path)
    backend = raw.get("backend")
    if not isinstance(backend, str) or not backend:
        raise ValidationError(f"{path}.backend must be a non-empty string")
    modes = raw.get("supported_modes")
    if not isinstance(modes, list) or not modes or not all(mode in ("rate", "angle") for mode in modes):
        raise ValidationError(f"{path}.supported_modes must contain rate and/or angle")
    default_mode = raw.get("default_mode")
    if default_mode not in modes:
        raise ValidationError(f"{path}.default_mode must be one of supported_modes")
    parameters_raw = raw.get("parameters")
    if not isinstance(parameters_raw, dict):
        raise ValidationError(f"{path}.parameters must be an object")
    parameters: dict[str, float] = {}
    origins: dict[str, str] = {}
    for key, entry in parameters_raw.items():
        if not isinstance(key, str) or not isinstance(entry, dict):
            raise ValidationError(f"{path}.parameters entries must be objects")
        parameters[key] = _number(entry.get("value"), f"{path}.parameters.{key}.value")
        origin = entry.get("origin", "catalog_default")
        if origin not in ("catalog_default", "generated_initial", "generic_default"):
            raise ValidationError(f"{path}.parameters.{key}.origin is invalid")
        origins[key] = origin
    return Controller(**common.__dict__, mass_kg=_number(raw.get("mass_kg"), f"{path}.mass_kg", positive=True), backend=backend, supported_modes=tuple(modes), default_mode=default_mode, parameters=parameters, parameter_origins=origins)


def _make_mounted_component(raw: dict[str, Any], path: str, kind: str) -> LandingGear | Attachment:
    for obsolete in ("center_of_mass_m", "inertia_kg_m2"):
        if obsolete in raw:
            raise ValidationError(f"{path}.{obsolete} is not supported; MuJoCo derives rigid-body properties from geometry.inertial")
    common = _common(raw, path)
    if common.geometry is None:
        raise ValidationError(f"{path}.geometry is required")
    values = dict(
        **common.__dict__,
        mass_kg=_number(raw.get("mass_kg", 0.0), f"{path}.mass_kg"),
    )
    if values["mass_kg"] < 0.0:
        raise ValidationError(f"{path}.mass_kg must not be negative")
    if kind == "landing_gear":
        if not common.geometry.inertial:
            raise ValidationError(f"{path}.geometry.inertial must contain at least one primitive")
        return LandingGear(**values)
    physical_role = raw.get("physical_role", "physical")
    if physical_role not in ("physical", "visual_only"):
        raise ValidationError(f"{path}.physical_role must be physical or visual_only")
    if physical_role == "physical" and not common.geometry.inertial:
        raise ValidationError(f"{path}.geometry.inertial must contain at least one primitive for a physical attachment")
    if physical_role == "visual_only" and common.geometry.inertial:
        raise ValidationError(f"{path}.geometry.inertial must be empty for a visual_only attachment")
    return Attachment(**values, physical_role=physical_role)


def _make_landing_gear(raw: dict[str, Any], path: str) -> LandingGear:
    return _make_mounted_component(raw, path, "landing_gear")  # type: ignore[return-value]


def _make_attachment(raw: dict[str, Any], path: str) -> Attachment:
    return _make_mounted_component(raw, path, "attachment")  # type: ignore[return-value]


_LOADERS = {
    "frame": ("frames.yaml", _make_frame),
    "motor": ("motors.yaml", _make_motor),
    "propeller": ("propellers.yaml", _make_propeller),
    "battery": ("batteries.yaml", _make_battery),
    "camera": ("cameras.yaml", _make_camera),
    "controller": ("controllers.yaml", _make_controller),
    "landing_gear": ("landing-gears.yaml", _make_landing_gear),
    "attachment": ("attachments.yaml", _make_attachment),
}


def _load_group(roots: tuple[Path, ...], kind: str) -> CatalogGroup[Any]:
    filename, factory = _LOADERS[kind]
    items: dict[str, Any] = {}
    found = False
    for root in roots:
        catalog_path = root / filename
        if not catalog_path.is_file():
            continue
        found = True
        raw = load_yaml(catalog_path)
        if raw.get("schema_version") != 1 or raw.get("kind") != kind:
            raise ValidationError(f"{catalog_path} must declare schema_version: 1 and kind: {kind}")
        entries = raw.get("items")
        if not isinstance(entries, list):
            raise ValidationError(f"{catalog_path}.items must be an array")
        for index, entry in enumerate(entries):
            entry_path = f"{catalog_path}.items[{index}]"
            if not isinstance(entry, dict):
                raise ValidationError(f"{entry_path} must be an object")
            item = factory(entry, entry_path)
            if item.id in items:
                raise ValidationError(f"duplicate {kind} catalog id across catalog roots: {item.id}")
            items[item.id] = item
    if not found:
        raise ValidationError(f"missing {filename} in catalog roots")
    return CatalogGroup(kind, items)


def load_catalogs(root: Path | Iterable[Path]) -> CatalogStore:
    roots = (root.resolve(),) if isinstance(root, Path) else tuple(path.resolve() for path in root)
    if not roots:
        raise ValidationError("at least one catalog root is required")
    return CatalogStore(
        root=roots[0],
        roots=roots,
        frames=_load_group(roots, "frame"),
        motors=_load_group(roots, "motor"),
        propellers=_load_group(roots, "propeller"),
        batteries=_load_group(roots, "battery"),
        cameras=_load_group(roots, "camera"),
        controllers=_load_group(roots, "controller"),
        landing_gears=_load_group(roots, "landing_gear"),
        attachments=_load_group(roots, "attachment"),
    )
