from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .catalog import AssemblyPort, CatalogStore, CatalogType
from .errors import ResolutionError, ValidationError
from .transforms import (
    compose_transform,
    inverse_transform,
    quaternion_from_rpy_deg,
    rpy_deg_from_quaternion,
)
from .yaml_io import load_yaml


Vector3 = tuple[float, float, float]
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _vector3(value: Any, path: str) -> Vector3:
    if not isinstance(value, list) or len(value) != 3 or any(
        isinstance(item, bool) or not isinstance(item, (int, float)) for item in value
    ):
        raise ValidationError(f"{path} must contain three numbers")
    return (float(value[0]), float(value[1]), float(value[2]))


@dataclass(frozen=True)
class AssemblyNode:
    id: str
    kind: str
    product: str
    name: str | None
    rotor_index: int | None
    rotor_name: str | None
    rotation_direction: int | None


@dataclass(frozen=True)
class AssemblyConnection:
    provider_node: str
    provider_port: str
    consumer_node: str
    consumer_port: str
    adjustment_position_m: Vector3
    adjustment_rpy_deg: Vector3


@dataclass(frozen=True)
class AssemblyGraph:
    name: str
    vehicle_type: str
    controller_mode: str
    nodes: tuple[AssemblyNode, ...]
    connections: tuple[AssemblyConnection, ...]


@dataclass(frozen=True)
class ResolvedAssembly:
    graph: AssemblyGraph
    nodes: dict[str, AssemblyNode]
    components: dict[str, CatalogType]
    connections: tuple[AssemblyConnection, ...]


@dataclass(frozen=True)
class AssemblyPose:
    """A component pose in the frame-rooted Catalog FLU coordinate system."""

    position_m: Vector3
    rotation: tuple[float, float, float, float]


def load_assembly_graph(path: Path) -> AssemblyGraph:
    raw = load_yaml(path)
    if raw.get("schema_version") != 1:
        raise ValidationError("assembly.schema_version must be 1")
    if raw.get("kind") != "fpv-assembly":
        raise ValidationError("assembly.kind must be fpv-assembly")
    name = raw.get("name")
    vehicle_type = raw.get("type")
    controller_mode = raw.get("controller_mode")
    if not isinstance(name, str) or not name:
        raise ValidationError("assembly.name must be a non-empty string")
    if vehicle_type not in ("quad_x", "multirotor"):
        raise ValidationError("assembly.type must be quad_x or multirotor")
    if controller_mode not in ("angle", "rate"):
        raise ValidationError("assembly.controller_mode must be angle or rate")
    nodes_raw = raw.get("nodes")
    connections_raw = raw.get("connections")
    if not isinstance(nodes_raw, list) or not isinstance(connections_raw, list):
        raise ValidationError("assembly.nodes and assembly.connections must be arrays")
    nodes: list[AssemblyNode] = []
    for index, entry in enumerate(nodes_raw):
        if not isinstance(entry, dict):
            raise ValidationError(f"assembly.nodes[{index}] must be an object")
        node_id, kind, product = entry.get("id"), entry.get("kind"), entry.get("product")
        if not isinstance(node_id, str) or not node_id:
            raise ValidationError(f"assembly.nodes[{index}].id must be a non-empty string")
        if kind not in ("frame", "motor", "propeller", "battery", "camera", "controller", "landing_gear", "attachment"):
            raise ValidationError(f"assembly.nodes[{index}].kind is unsupported")
        if not isinstance(product, str) or not product:
            raise ValidationError(f"assembly.nodes[{index}].product must be a non-empty string")
        entry_name = entry.get("name")
        if entry_name is not None and (not isinstance(entry_name, str) or not entry_name):
            raise ValidationError(f"assembly.nodes[{index}].name must be a non-empty string when present")
        rotor = entry.get("rotor")
        if kind == "motor":
            if not isinstance(rotor, dict):
                raise ValidationError(f"assembly.nodes[{index}].rotor is required for motor")
            rotor_index, rotor_name, rotation_direction = rotor.get("index"), rotor.get("name"), rotor.get("rotation_direction")
            if not isinstance(rotor_index, int) or isinstance(rotor_index, bool) or rotor_index <= 0:
                raise ValidationError(f"assembly.nodes[{index}].rotor.index must be a positive integer")
            if not isinstance(rotor_name, str) or not rotor_name:
                raise ValidationError(f"assembly.nodes[{index}].rotor.name must be a non-empty string")
            if rotation_direction not in (-1, 1):
                raise ValidationError(f"assembly.nodes[{index}].rotor.rotation_direction must be -1 or 1")
        elif rotor is not None:
            raise ValidationError(f"assembly.nodes[{index}].rotor is valid only for motor")
        else:
            rotor_index = rotor_name = rotation_direction = None
        nodes.append(AssemblyNode(node_id, kind, product, entry_name, rotor_index, rotor_name, rotation_direction))
    if len({node.id for node in nodes}) != len(nodes):
        raise ValidationError("assembly.nodes ids must be unique")
    connections: list[AssemblyConnection] = []
    for index, entry in enumerate(connections_raw):
        if not isinstance(entry, dict):
            raise ValidationError(f"assembly.connections[{index}] must be an object")
        provider, consumer = entry.get("provider"), entry.get("consumer")
        if not isinstance(provider, dict) or not isinstance(consumer, dict):
            raise ValidationError(f"assembly.connections[{index}] must have provider and consumer objects")
        provider_node, provider_port = provider.get("node"), provider.get("port")
        consumer_node, consumer_port = consumer.get("node"), consumer.get("port")
        if not all(isinstance(value, str) and value for value in (provider_node, provider_port, consumer_node, consumer_port)):
            raise ValidationError(f"assembly.connections[{index}] node and port IDs must be non-empty strings")
        adjustment = entry.get("adjustment", {})
        if not isinstance(adjustment, dict):
            raise ValidationError(f"assembly.connections[{index}].adjustment must be an object")
        connections.append(AssemblyConnection(
            provider_node, provider_port, consumer_node, consumer_port,
            _vector3(adjustment.get("position_m", [0, 0, 0]), f"assembly.connections[{index}].adjustment.position_m"),
            _vector3(adjustment.get("rpy_deg", [0, 0, 0]), f"assembly.connections[{index}].adjustment.rpy_deg"),
        ))
    return AssemblyGraph(name, vehicle_type, controller_mode, tuple(nodes), tuple(connections))


def _component(catalogs: CatalogStore, node: AssemblyNode) -> CatalogType:
    groups = {
        "frame": catalogs.frames, "motor": catalogs.motors, "propeller": catalogs.propellers,
        "battery": catalogs.batteries, "camera": catalogs.cameras, "controller": catalogs.controllers,
        "landing_gear": catalogs.landing_gears, "attachment": catalogs.attachments,
    }
    return groups[node.kind].get(node.product)


def _port(component: CatalogType, port_id: str, role: str, node_id: str) -> AssemblyPort:
    matches = [port for port in component.assembly_ports if port.id == port_id and port.role == role]
    if len(matches) != 1:
        raise ResolutionError(f"assembly node {node_id} has no {role} port {port_id}")
    return matches[0]


def _rules(interface_root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    raw = load_yaml(interface_root / "connection-rules.yaml")
    return {(entry["provider_interface"], entry["consumer_interface"]): entry for entry in raw["items"]}


def _validate_adjustment(connection: AssemblyConnection, rule: dict[str, Any]) -> None:
    adjustment = rule["adjustment"]
    axes = (("x", "y", "z"), ("roll", "pitch", "yaw"))
    values = (connection.adjustment_position_m, connection.adjustment_rpy_deg)
    for allowed_key, limits_key, axis_names, selected in zip(
        ("translation_axes", "rotation_axes"), ("translation_limits_m", "rotation_limits_deg"), axes, values,
    ):
        allowed = set(adjustment[allowed_key])
        limits = adjustment.get(limits_key)
        for index, axis in enumerate(axis_names):
            if selected[index] != 0.0 and axis not in allowed:
                raise ResolutionError(f"assembly adjustment {axis} is not allowed by {rule['id']}")
            if limits is not None and abs(selected[index]) > float(limits[index]):
                raise ResolutionError(f"assembly adjustment {axis} exceeds {rule['id']} limit")


def _component_transform(provider: AssemblyPort, consumer: AssemblyPort, connection: AssemblyConnection):
    provider_rotation = quaternion_from_rpy_deg(provider.rpy_deg)
    adjustment_rotation = quaternion_from_rpy_deg(connection.adjustment_rpy_deg)
    consumer_rotation = quaternion_from_rpy_deg(consumer.rpy_deg)
    position, rotation = compose_transform(
        provider.position_m,
        provider_rotation,
        connection.adjustment_position_m,
        adjustment_rotation,
    )
    inverse_position, inverse_rotation = inverse_transform(consumer.position_m, consumer_rotation)
    position, rotation = compose_transform(position, rotation, inverse_position, inverse_rotation)
    return position, rotation


def _component_pose(provider: AssemblyPort, consumer: AssemblyPort, connection: AssemblyConnection) -> tuple[Vector3, Vector3]:
    position, rotation = _component_transform(provider, consumer, connection)
    return position, rpy_deg_from_quaternion(rotation)


def resolve_assembly(graph: AssemblyGraph, catalogs: CatalogStore, interface_root: Path | None = None) -> ResolvedAssembly:
    root = interface_root or _REPOSITORY_ROOT / "assembly-interfaces"
    nodes = {node.id: node for node in graph.nodes}
    components = {node.id: _component(catalogs, node) for node in graph.nodes}
    rules = _rules(root)
    provider_uses: dict[tuple[str, str], int] = {}
    consumer_uses: dict[tuple[str, str], int] = {}
    for connection in graph.connections:
        if connection.provider_node not in nodes or connection.consumer_node not in nodes:
            raise ResolutionError("assembly connection references an unknown node")
        provider = _port(components[connection.provider_node], connection.provider_port, "provider", connection.provider_node)
        consumer = _port(components[connection.consumer_node], connection.consumer_port, "consumer", connection.consumer_node)
        rule = rules.get((provider.interface, consumer.interface))
        if rule is None or rule["status"] != "compatible":
            raise ResolutionError(f"assembly ports {provider.interface} and {consumer.interface} are not compatible")
        _validate_adjustment(connection, rule)
        provider_key = (connection.provider_node, connection.provider_port)
        consumer_key = (connection.consumer_node, connection.consumer_port)
        provider_uses[provider_key] = provider_uses.get(provider_key, 0) + 1
        consumer_uses[consumer_key] = consumer_uses.get(consumer_key, 0) + 1
        if provider_uses[provider_key] > provider.capacity:
            raise ResolutionError(f"assembly provider port {connection.provider_node}.{connection.provider_port} exceeds capacity")
        if consumer_uses[consumer_key] > consumer.capacity:
            raise ResolutionError(f"assembly consumer port {connection.consumer_node}.{connection.consumer_port} exceeds capacity")
    frames = [node for node in graph.nodes if node.kind == "frame"]
    if len(frames) != 1:
        raise ResolutionError("assembly must contain exactly one frame root")
    for node in graph.nodes:
        if node.kind != "frame":
            component = components[node.id]
            for port in component.assembly_ports:
                if port.role == "consumer" and consumer_uses.get((node.id, port.id), 0) != 1:
                    raise ResolutionError(f"assembly consumer port {node.id}.{port.id} must be connected exactly once")
    return ResolvedAssembly(graph, nodes, components, graph.connections)


def resolve_assembly_poses(resolved: ResolvedAssembly) -> dict[str, AssemblyPose]:
    """Resolve every Assembly Graph node into the frame's FLU coordinate system.

    The relative child transform is the same rigid transform used by Recipe
    projection: provider port × connection adjustment × inverse(consumer port).
    Keeping this calculation here lets visual exporters and physical projection
    share one interpretation of an Assembly Graph.
    """
    frame = next(node for node in resolved.graph.nodes if node.kind == "frame")
    poses = {frame.id: AssemblyPose((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0))}
    pending = list(resolved.connections)
    while pending:
        next_pending: list[AssemblyConnection] = []
        progressed = False
        for connection in pending:
            provider_pose = poses.get(connection.provider_node)
            if provider_pose is None:
                next_pending.append(connection)
                continue
            provider = _port(
                resolved.components[connection.provider_node],
                connection.provider_port,
                "provider",
                connection.provider_node,
            )
            consumer = _port(
                resolved.components[connection.consumer_node],
                connection.consumer_port,
                "consumer",
                connection.consumer_node,
            )
            relative_position, relative_rotation = _component_transform(provider, consumer, connection)
            position, rotation = compose_transform(
                provider_pose.position_m,
                provider_pose.rotation,
                relative_position,
                relative_rotation,
            )
            if connection.consumer_node in poses:
                raise ResolutionError(f"assembly node {connection.consumer_node} has multiple parent connections")
            poses[connection.consumer_node] = AssemblyPose(position, rotation)
            progressed = True
        if not progressed:
            unresolved = ", ".join(connection.consumer_node for connection in next_pending)
            raise ResolutionError(f"assembly connections are not rooted at the frame: {unresolved}")
        pending = next_pending
    if len(poses) != len(resolved.nodes):
        missing = ", ".join(sorted(set(resolved.nodes) - set(poses)))
        raise ResolutionError(f"assembly nodes have no frame-rooted pose: {missing}")
    return poses


def project_recipe(resolved: ResolvedAssembly) -> dict[str, Any]:
    graph = resolved.graph
    by_kind: dict[str, list[AssemblyNode]] = {}
    for node in graph.nodes:
        by_kind.setdefault(node.kind, []).append(node)
    required_singletons = ("frame", "battery", "camera", "controller")
    if any(len(by_kind.get(kind, [])) != 1 for kind in required_singletons):
        raise ResolutionError("assembly must contain exactly one frame, battery, camera, and controller")
    motors, propellers = by_kind.get("motor", []), by_kind.get("propeller", [])
    if graph.vehicle_type == "quad_x" and (len(motors) != 4 or len(propellers) != 4):
        raise ResolutionError("quad_x assembly requires exactly four motors and four propellers")
    products = {kind: {node.product for node in nodes} for kind, nodes in by_kind.items()}
    if len(products["motor"]) != 1 or len(products["propeller"]) != 1:
        raise ResolutionError("existing Vehicle Recipe projection requires one motor and one propeller product")
    frame = by_kind["frame"][0]
    placements: dict[str, dict[str, list[float]]] = {}
    attachment_entries: list[dict[str, Any]] = []
    mount_connections = {connection.consumer_node: connection for connection in resolved.connections if connection.provider_node == frame.id}
    for kind in ("battery", "camera", "controller", "landing_gear"):
        if not by_kind.get(kind):
            continue
        node = by_kind[kind][0]
        connection = mount_connections.get(node.id)
        if connection is None:
            raise ResolutionError(f"assembly node {node.id} is not mounted on the frame")
        provider = _port(resolved.components[frame.id], connection.provider_port, "provider", frame.id)
        consumer = _port(resolved.components[node.id], connection.consumer_port, "consumer", node.id)
        position, rpy_deg = _component_pose(provider, consumer, connection)
        placements[kind] = {
            "position_m": list(position),
            "rpy_deg": list(rpy_deg),
        }
    for node in by_kind.get("attachment", []):
        connection = mount_connections.get(node.id)
        if connection is None:
            raise ResolutionError(f"assembly attachment {node.id} is not mounted on the frame")
        provider = _port(resolved.components[frame.id], connection.provider_port, "provider", frame.id)
        consumer = _port(resolved.components[node.id], connection.consumer_port, "consumer", node.id)
        position, rpy_deg = _component_pose(provider, consumer, connection)
        attachment_entries.append({
            "name": node.name or node.id,
            "product": node.product,
            "parent": "frame",
            "position_m": list(position),
            "rpy_deg": list(rpy_deg),
        })
    motor_connections = [connection for connection in resolved.connections if connection.provider_node == frame.id and resolved.nodes[connection.consumer_node].kind == "motor"]
    if len(motor_connections) != len(motors):
        raise ResolutionError("every motor must be connected directly to the frame")
    motor_propeller_connections = [
        connection for connection in resolved.connections
        if resolved.nodes[connection.provider_node].kind == "motor"
        and resolved.nodes[connection.consumer_node].kind == "propeller"
    ]
    if {connection.provider_node for connection in motor_propeller_connections} != {node.id for node in motors}:
        raise ResolutionError("every motor must provide exactly one propeller connection")
    motor_propeller_by_motor = {connection.provider_node: connection for connection in motor_propeller_connections}
    motor_connections.sort(key=lambda connection: resolved.nodes[connection.consumer_node].rotor_index or 0)
    rotor_indices = [resolved.nodes[connection.consumer_node].rotor_index for connection in motor_connections]
    if rotor_indices != list(range(1, len(motor_connections) + 1)):
        raise ResolutionError("motor rotor.index values must be contiguous from 1")
    if len({resolved.nodes[connection.consumer_node].rotor_name for connection in motor_connections}) != len(motor_connections):
        raise ResolutionError("motor rotor.name values must be unique")
    rotor_layout = []
    for index, connection in enumerate(motor_connections):
        port = _port(resolved.components[frame.id], connection.provider_port, "provider", frame.id)
        motor = resolved.nodes[connection.consumer_node]
        motor_mount = _port(resolved.components[motor.id], connection.consumer_port, "consumer", motor.id)
        motor_position, motor_rotation = _component_transform(port, motor_mount, connection)
        propeller_connection = motor_propeller_by_motor[motor.id]
        rotor_reference = _port(
            resolved.components[motor.id],
            propeller_connection.provider_port,
            "provider",
            motor.id,
        )
        rotor_position, _ = compose_transform(
            motor_position,
            motor_rotation,
            rotor_reference.position_m,
            quaternion_from_rpy_deg(rotor_reference.rpy_deg),
        )
        rotor_layout.append({
            "name": motor.rotor_name,
            "position_flu_m": list(rotor_position),
            "motor_position_flu_m": list(motor_position),
            "rotation_direction": motor.rotation_direction,
        })
    components: dict[str, Any] = {
        "frame": frame.product,
        "motors": {"product": motors[0].product, "count": len(motors)},
        "propeller": propellers[0].product,
        "battery": by_kind["battery"][0].product,
        "camera": by_kind["camera"][0].product,
    }
    if by_kind.get("landing_gear"):
        if len(by_kind["landing_gear"]) != 1:
            raise ResolutionError("existing Vehicle Recipe projection supports one landing gear product")
        components["landing_gear"] = by_kind["landing_gear"][0].product
    return {
        "schema_version": 2,
        "name": graph.name,
        "type": graph.vehicle_type,
        "components": components,
        "controller": {"product": by_kind["controller"][0].product, "mode": graph.controller_mode},
        "rotor_layout": {"contract": "hakoniwa-drone-pro/rotor-layout-v1", "rotors": rotor_layout},
        "placements": placements,
        "attachments": attachment_entries,
        "metadata": {"source": "assembly-graph"},
    }
