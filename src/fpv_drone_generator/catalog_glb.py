from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .catalog import (
    Attachment,
    Battery,
    Camera,
    CatalogStore,
    CatalogType,
    Controller,
    Frame,
    LandingGear,
    Motor,
    Propeller,
)
from .showroom import DisplayPrimitive, _display_geometry, _selected_items
from .yaml_io import load_yaml


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _rotation_matrix(rpy_deg: tuple[float, float, float]):
    import numpy as np

    roll, pitch, yaw = (math.radians(value) for value in rpy_deg)
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array(((1.0, 0.0, 0.0), (0.0, cr, -sr), (0.0, sr, cr)))
    ry = np.array(((cp, 0.0, sp), (0.0, 1.0, 0.0), (-sp, 0.0, cp)))
    rz = np.array(((cy, -sy, 0.0), (sy, cy, 0.0), (0.0, 0.0, 1.0)))
    return rz @ ry @ rx


def _primitive_transform(primitive: DisplayPrimitive):
    import numpy as np

    transform = np.eye(4)
    transform[:3, :3] = _rotation_matrix(primitive.rpy_deg)
    transform[:3, 3] = primitive.center_m
    return transform


def _mesh_from_primitive(primitive: DisplayPrimitive):
    import numpy as np
    import trimesh

    if primitive.primitive_type == "box":
        assert primitive.dimensions_m is not None
        mesh = trimesh.creation.box(extents=primitive.dimensions_m)
    elif primitive.primitive_type == "cylinder":
        assert primitive.radius_m is not None and primitive.length_m is not None
        mesh = trimesh.creation.cylinder(radius=primitive.radius_m, height=primitive.length_m, sections=32)
    elif primitive.primitive_type == "capsule":
        assert primitive.radius_m is not None and primitive.length_m is not None
        mesh = trimesh.creation.capsule(radius=primitive.radius_m, height=primitive.length_m)
    elif primitive.primitive_type == "sphere":
        assert primitive.radius_m is not None
        mesh = trimesh.creation.icosphere(subdivisions=2, radius=primitive.radius_m)
    else:
        raise ValueError(f"unsupported display primitive: {primitive.primitive_type}")

    rgba = np.array(
        [max(0, min(255, round(channel * 255.0))) for channel in primitive.rgba],
        dtype=np.uint8,
    )
    mesh.visual.vertex_colors = np.tile(rgba, (len(mesh.vertices), 1))
    mesh.apply_transform(_primitive_transform(primitive))
    return mesh


def _component_specs(component: CatalogType) -> dict[str, Any]:
    specs: dict[str, Any] = {"mass_kg": component.mass_kg}
    if isinstance(component, Frame):
        specs.update(dimensions_m=list(component.dimensions_m), wheelbase_m=component.wheelbase_m)
    elif isinstance(component, Motor):
        specs.update(kv_rpm_per_v=component.kv_rpm_per_v, max_current_a=component.max_current_a, max_rad_per_sec=component.max_rad_per_sec)
    elif isinstance(component, Propeller):
        specs.update(diameter_m=component.diameter_m, pitch_m=component.pitch_m, blade_count=component.blade_count)
    elif isinstance(component, Battery):
        specs.update(dimensions_m=list(component.dimensions_m), cell_count=component.cell_count, nominal_voltage_v=component.nominal_voltage_v, capacity_ah=component.capacity_ah)
    elif isinstance(component, Camera):
        specs.update(dimensions_m=list(component.dimensions_m), fov_deg=component.fov_deg)
    elif isinstance(component, Controller):
        specs.update(backend=component.backend, supported_modes=list(component.supported_modes), default_mode=component.default_mode)
    elif isinstance(component, Attachment):
        specs.update(physical_role=component.physical_role)
    elif isinstance(component, LandingGear):
        pass
    return specs


def export_component_glb(kind: str, component: CatalogType, output_path: Path) -> dict[str, Any]:
    try:
        import trimesh
    except ImportError as exc:
        raise RuntimeError("trimesh is required for Catalog GLB export") from exc

    scene = trimesh.Scene()
    for index, primitive in enumerate(_display_geometry(component, kind)):
        name = f"{kind}__{component.id}__visual_{index}"
        scene.add_geometry(_mesh_from_primitive(primitive), node_name=name, geom_name=name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    exported = scene.export(file_type="glb")
    if not isinstance(exported, (bytes, bytearray)):
        raise RuntimeError(f"GLB exporter returned unexpected type: {type(exported).__name__}")
    output_path.write_bytes(bytes(exported))

    bounds = scene.bounds
    extents = scene.extents
    return {
        "kind": kind,
        "id": component.id,
        "name": component.name,
        "vendor": component.vendor,
        "description": component.description,
        "asset": output_path.name,
        "specs": _component_specs(component),
        "metadata": component.metadata,
        "bounds_m": None if bounds is None else bounds.tolist(),
        "extents_m": None if extents is None else extents.tolist(),
    }


def _port_contract(component: CatalogType) -> list[dict[str, Any]]:
    return [
        {
            "id": port.id,
            "role": port.role,
            "interface": port.interface,
            "pose": {"position_m": list(port.position_m), "rpy_deg": list(port.rpy_deg)},
            "capacity": port.capacity,
        }
        for port in component.assembly_ports
    ]


def export_assembly_contract(
    catalogs: CatalogStore,
    output_dir: Path,
    kind: str | None = None,
    item_id: str | None = None,
    interface_root: Path | None = None,
) -> Path:
    items = _selected_items(catalogs, kind, item_id)
    root = interface_root or _REPOSITORY_ROOT / "assembly-interfaces"
    definitions = load_yaml(root / "definitions.yaml")
    variants = load_yaml(root / "variants.yaml")
    rules = load_yaml(root / "connection-rules.yaml")
    contract = {
        "schema_version": 1,
        "coordinate_system": "Hakoniwa catalog local frame; FLU; meters and degrees",
        "selection": {"kind": kind, "item_id": item_id},
        "components": [
            {
                "id": selected.component.id,
                "kind": selected.kind,
                "assembly_ports": _port_contract(selected.component),
            }
            for selected in items
        ],
        "interface_definitions": definitions["items"],
        "interface_variants": variants["items"],
        "connection_rules": rules["items"],
    }
    path = output_dir / "assembly-contract.json"
    path.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def export_catalog_glb(catalogs: CatalogStore, output_dir: Path, kind: str | None = None, item_id: str | None = None) -> Path:
    items = _selected_items(catalogs, kind, item_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_items: list[dict[str, Any]] = []
    for selected in items:
        relative_asset = Path(selected.kind) / f"{selected.component.id}.glb"
        entry = export_component_glb(selected.kind, selected.component, output_dir / relative_asset)
        entry["asset"] = relative_asset.as_posix()
        manifest_items.append(entry)

    manifest = {
        "schema_version": 1,
        "coordinate_system": "Hakoniwa catalog local frame; meters",
        "selection": {"kind": kind, "item_id": item_id},
        "items": manifest_items,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    export_assembly_contract(catalogs, output_dir, kind, item_id)
    return manifest_path
