"""Materialize Assembly Graph visuals for the PDU-driven Three.js viewer."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .assembly import ResolvedAssembly, resolve_assembly_poses
from .catalog import Camera
from .catalog_glb import _mesh_from_primitive
from .errors import ResolutionError
from .showroom import _display_geometry
from .transforms import normalize_quaternion, rpy_deg_from_quaternion


def _matrix(position_m: tuple[float, float, float], rotation: tuple[float, float, float, float]):
    import numpy as np

    w, x, y, z = normalize_quaternion(rotation)
    result = np.eye(4)
    result[:3, :3] = (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
    )
    result[:3, 3] = position_m
    return result


def _flu_to_three_matrix():
    """Map Catalog FLU mesh vertices into Three.js's right/up/back basis."""
    import numpy as np

    # Catalog / ROS: Forward, Left, Up.  The viewer maps positions as
    # [-left, up, -forward], but a GLB attachment has no RenderEntity wrapper.
    # Bake the identical basis change into every generated visual asset.
    result = np.eye(4)
    result[:3, :3] = ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (-1.0, 0.0, 0.0))
    return result


def _export_scene(scene: Any, path: Path) -> None:
    scene.apply_transform(_flu_to_three_matrix())
    exported = scene.export(file_type="glb")
    if not isinstance(exported, (bytes, bytearray)):
        raise RuntimeError(f"GLB exporter returned unexpected type: {type(exported).__name__}")
    path.write_bytes(bytes(exported))


def _safe_type_name(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_").lower()
    return name or "fpv_assembly"


def _one(nodes: list[Any], kind: str) -> Any:
    if len(nodes) != 1:
        raise ResolutionError(f"Three.js asset export requires exactly one {kind}")
    return nodes[0]


def export_threejs_assets(resolved: ResolvedAssembly, output_dir: Path, *, type_name: str | None = None) -> Path:
    """Write body, propeller, camera GLBs and a viewer-compatible drone type.

    GLBs are source models in Catalog FLU.  The generated drone type applies
    resolved Assembly poses, so the Three.js viewer can animate propellers from
    PWM without duplicating the Assembly connection rules.
    """
    try:
        import trimesh
    except ImportError as exc:
        raise RuntimeError("trimesh is required for Three.js asset export") from exc

    by_kind: dict[str, list[Any]] = {}
    for node in resolved.graph.nodes:
        by_kind.setdefault(node.kind, []).append(node)
    frame = _one(by_kind.get("frame", []), "frame")
    camera_node = _one(by_kind.get("camera", []), "camera")
    motors = sorted(by_kind.get("motor", []), key=lambda node: node.rotor_index or 0)
    propellers = by_kind.get("propeller", [])
    if not motors or len(motors) != len(propellers):
        raise ResolutionError("Three.js asset export requires one propeller for every motor")
    propeller_products = {node.product for node in propellers}
    if len(propeller_products) != 1:
        raise ResolutionError("Three.js asset export requires one shared propeller product")
    if [node.rotor_index for node in motors] != list(range(1, len(motors) + 1)):
        raise ResolutionError("motor rotor.index values must be contiguous from 1")

    poses = resolve_assembly_poses(resolved)
    output_dir.mkdir(parents=True, exist_ok=True)
    body_path = output_dir / "body.glb"
    propeller_path = output_dir / "propeller.glb"
    camera_path = output_dir / "camera.glb"

    body = trimesh.Scene()
    for node in resolved.graph.nodes:
        if node.kind in {"propeller", "camera"}:
            continue
        pose = poses[node.id]
        for index, primitive in enumerate(_display_geometry(resolved.components[node.id], node.kind)):
            mesh = _mesh_from_primitive(primitive)
            mesh.apply_transform(_matrix(pose.position_m, pose.rotation))
            name = f"{node.id}__visual_{index}"
            body.add_geometry(mesh, node_name=name, geom_name=name)
    _export_scene(body, body_path)

    propeller = trimesh.Scene()
    propeller_component = resolved.components[propellers[0].id]
    for index, primitive in enumerate(_display_geometry(propeller_component, "propeller")):
        name = f"propeller__visual_{index}"
        propeller.add_geometry(_mesh_from_primitive(primitive), node_name=name, geom_name=name)
    _export_scene(propeller, propeller_path)

    camera_scene = trimesh.Scene()
    camera_component = resolved.components[camera_node.id]
    for index, primitive in enumerate(_display_geometry(camera_component, "camera")):
        name = f"camera__visual_{index}"
        camera_scene.add_geometry(_mesh_from_primitive(primitive), node_name=name, geom_name=name)
    _export_scene(camera_scene, camera_path)

    if not isinstance(camera_component, Camera):
        raise ResolutionError("assembly camera node does not resolve to a Camera Catalog item")
    generated_type_name = type_name or _safe_type_name(resolved.graph.name)
    camera_pose = poses[camera_node.id]
    rotors = []
    propeller_by_motor = {
        connection.provider_node: connection.consumer_node
        for connection in resolved.connections
        if resolved.nodes[connection.provider_node].kind == "motor"
        and resolved.nodes[connection.consumer_node].kind == "propeller"
    }
    for motor in motors:
        propeller_id = propeller_by_motor.get(motor.id)
        if propeller_id is None:
            raise ResolutionError(f"motor {motor.id} has no propeller connection")
        pose = poses[propeller_id]
        rotors.append({
            "name": motor.rotor_name,
            "pos": list(pose.position_m),
            "hpr": list(rpy_deg_from_quaternion(pose.rotation)),
            "spinDirection": motor.rotation_direction,
            "model": {"model_path": "./propeller.glb", "pos": [0, 0, 0], "hpr": [0, 0, 0]},
        })
    drone_type = {
        "model": {"model_path": "./body.glb", "pos": [0, 0, 0], "hpr": [0, 0, 0]},
        "rotors": rotors,
        "cameras": [{
            "name": "fpv",
            "pos": list(camera_pose.position_m),
            "hpr": list(rpy_deg_from_quaternion(camera_pose.rotation)),
            "fov": camera_component.fov_deg,
            "near": 0.02,
            "far": 1000.0,
            "window": {"width": 640, "height": 480},
            "model": {"model_path": "./camera.glb", "pos": [0, 0, 0], "hpr": [0, 0, 0]},
        }],
    }
    drone_types_path = output_dir / "drone-types.json"
    drone_types_path.write_text(json.dumps({generated_type_name: drone_type}, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "coordinate_system": "Hakoniwa Catalog FLU; metres and degrees (also viewer ROS FLU)",
        "source": {"assembly_name": resolved.graph.name, "frame": frame.product},
        "drone_type": generated_type_name,
        "artifacts": {"body": body_path.name, "propeller": propeller_path.name, "camera": camera_path.name, "drone_types": drone_types_path.name},
        "camera_pose_source": "catalog-assembly; runtime integration must use generated MuJoCo fpv camera pose and FOV when present",
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path
