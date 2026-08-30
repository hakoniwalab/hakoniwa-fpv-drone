from __future__ import annotations

import math
from pathlib import Path
from xml.etree import ElementTree as ET

from ..catalog import GeometryAssembly, GeometryPrimitive, Vector3
from ..model import ResolvedVehicle
from ..transforms import multiply_quaternions, quaternion_from_rpy_deg, transform_point
from ..world import Obstacle, World


def _numbers(values: tuple[float, ...]) -> str:
    return " ".join(f"{value:.12g}" for value in values)


def _primitive_size(primitive: GeometryPrimitive) -> str:
    if primitive.primitive_type == "box":
        assert primitive.dimensions_m is not None
        return _numbers(tuple(value / 2.0 for value in primitive.dimensions_m))
    if primitive.primitive_type == "sphere":
        assert primitive.radius_m is not None
        return f"{primitive.radius_m:.12g}"
    assert primitive.radius_m is not None and primitive.length_m is not None
    return f"{primitive.radius_m:.12g} {primitive.length_m / 2.0:.12g}"


def _primitive_volume(primitive: GeometryPrimitive) -> float:
    if primitive.primitive_type == "box":
        assert primitive.dimensions_m is not None
        return primitive.dimensions_m[0] * primitive.dimensions_m[1] * primitive.dimensions_m[2]
    assert primitive.radius_m is not None
    if primitive.primitive_type == "sphere":
        return 4.0 * math.pi * primitive.radius_m ** 3 / 3.0
    assert primitive.length_m is not None
    cylinder = math.pi * primitive.radius_m ** 2 * primitive.length_m
    if primitive.primitive_type == "capsule":
        return cylinder + 4.0 * math.pi * primitive.radius_m ** 3 / 3.0
    return cylinder


def _add_assembly(
    body: ET.Element,
    prefix: str,
    assembly: GeometryAssembly,
    position_m: Vector3 = (0.0, 0.0, 0.0),
    rpy_deg: Vector3 = (0.0, 0.0, 0.0),
    default_friction: tuple[float, float, float] = (0.8, 0.1, 0.1),
    physical_mass_kg: float | None = None,
) -> None:
    mount_rotation = quaternion_from_rpy_deg(rpy_deg)
    inertial_volume = sum(_primitive_volume(primitive) for primitive in assembly.inertial)
    density = None
    if physical_mass_kg is not None:
        if inertial_volume <= 0.0:
            raise ValueError(f"{prefix} requires non-empty positive-volume inertial geometry")
        density = physical_mass_kg / inertial_volume
    for role, primitives in (("visual", assembly.visual), ("collision", assembly.collision), ("inertial", assembly.inertial)):
        for primitive in primitives:
            primitive_rotation = quaternion_from_rpy_deg(primitive.rpy_deg)
            attributes = {
                "name": f"{prefix}_{primitive.name}",
                "type": primitive.primitive_type,
                "pos": _numbers(transform_point(position_m, mount_rotation, primitive.center_m)),
                "quat": _numbers(multiply_quaternions(mount_rotation, primitive_rotation)),
                "size": _primitive_size(primitive),
                "rgba": _numbers(primitive.rgba),
            }
            if role == "visual":
                attributes.update({"mass": "0", "group": "1", "contype": "0", "conaffinity": "0"})
            elif role == "collision":
                attributes.update({
                    "mass": "0",
                    "group": "2",
                    "contype": "1",
                    "conaffinity": "1",
                    "friction": _numbers(primitive.friction or default_friction),
                })
            else:
                if density is None:
                    continue
                attributes.update({
                    "density": f"{density:.12g}",
                    "group": "5",
                    "contype": "0",
                    "conaffinity": "0",
                    "rgba": "0 0 0 0",
                })
            ET.SubElement(body, "geom", attributes)


def _add_obstacle(worldbody: ET.Element, obstacle: Obstacle, world_config: World) -> None:
    body = ET.SubElement(worldbody, "body", {
        "name": f"course_{obstacle.name}",
        "pos": _numbers(obstacle.center_m),
        "euler": f"0 0 {obstacle.yaw_deg:.12g}",
    })
    common = {
        "contype": "1",
        "conaffinity": "1",
        "friction": _numbers(world_config.contact.obstacle_friction),
        "condim": str(world_config.contact.obstacle_condim),
        "rgba": _numbers(obstacle.rgba),
    }
    if obstacle.kind == "box":
        assert obstacle.dimensions_m is not None
        ET.SubElement(body, "geom", {
            **common,
            "name": f"{obstacle.name}_geom",
            "type": "box",
            "size": _numbers(tuple(value / 2.0 for value in obstacle.dimensions_m)),
        })
    elif obstacle.kind == "pylon":
        assert obstacle.radius_m is not None and obstacle.height_m is not None
        ET.SubElement(body, "geom", {
            **common,
            "name": f"{obstacle.name}_geom",
            "type": "cylinder",
            "size": f"{obstacle.radius_m:.12g} {obstacle.height_m / 2.0:.12g}",
        })
    else:
        assert obstacle.inner_width_m is not None
        assert obstacle.inner_height_m is not None
        assert obstacle.bar_thickness_m is not None
        assert obstacle.depth_m is not None
        half_width = obstacle.inner_width_m / 2.0
        half_height = obstacle.inner_height_m / 2.0
        half_bar = obstacle.bar_thickness_m / 2.0
        half_depth = obstacle.depth_m / 2.0
        side_z = 0.0
        top_z = half_height + half_bar
        side_x = half_width + half_bar
        for suffix, pos, size in (
            ("left", (-side_x, 0.0, side_z), (half_bar, half_depth, half_height + obstacle.bar_thickness_m)),
            ("right", (side_x, 0.0, side_z), (half_bar, half_depth, half_height + obstacle.bar_thickness_m)),
            ("top", (0.0, 0.0, top_z), (half_width, half_depth, half_bar)),
            ("bottom", (0.0, 0.0, -top_z), (half_width, half_depth, half_bar)),
        ):
            ET.SubElement(body, "geom", {
                **common,
                "name": f"{obstacle.name}_{suffix}",
                "type": "box",
                "pos": _numbers(pos),
                "size": _numbers(size),
            })


def generate_mujoco(vehicle: ResolvedVehicle, output: Path, world_config: World | None = None) -> None:
    frame = vehicle.components.frame
    camera = vehicle.components.camera
    root = ET.Element("mujoco", {"model": vehicle.recipe.name})
    compiler = {"angle": "degree", "inertiafromgeom": "false"}
    if vehicle.recipe.schema_version >= 2:
        compiler.update({"inertiafromgeom": "true", "inertiagrouprange": "5 5"})
    ET.SubElement(root, "compiler", compiler)
    ET.SubElement(root, "option", {"timestep": "0.001", "density": "1.204", "viscosity": "0.000018", "integrator": "RK4"})
    visual = ET.SubElement(root, "visual")
    ET.SubElement(visual, "global", {"azimuth": "135", "elevation": "-20"})
    if world_config is not None:
        ET.SubElement(visual, "rgba", {
            "haze": _numbers(world_config.haze_rgba),
        })
        ET.SubElement(visual, "headlight", {
            "ambient": _numbers(world_config.headlight_ambient),
            "diffuse": _numbers(world_config.headlight_diffuse),
            "specular": "0.25 0.25 0.25",
        })
        asset = ET.SubElement(root, "asset")
        sky = world_config.sky_rgba
        lighter_sky = tuple(min(1.0, value + 0.16) for value in sky[:3])
        ET.SubElement(asset, "texture", {
            "name": "fpv_sky",
            "type": "skybox",
            "builtin": "gradient",
            "rgb1": _numbers(sky[:3]),
            "rgb2": _numbers(lighter_sky),
            "width": "512",
            "height": "3072",
        })
    world = ET.SubElement(root, "worldbody")
    if world_config is None:
        ET.SubElement(world, "light", {"pos": "0 0 4", "diffuse": "0.8 0.8 0.8"})
        ground_size = (5.0, 5.0)
        ground_rgba = (0.18, 0.20, 0.22, 1.0)
        ground_friction = (0.8, 0.1, 0.1)
    else:
        for light in world_config.lights:
            ET.SubElement(world, "light", {
                "name": light.name,
                "pos": _numbers(light.pos_m),
                "dir": _numbers(light.direction),
                "diffuse": _numbers(light.diffuse),
                "ambient": _numbers(light.ambient),
                "directional": "true",
                "castshadow": "true",
            })
        ground_size = world_config.ground_size_m
        ground_rgba = world_config.ground_rgba
        ground_friction = world_config.contact.ground_friction
    ET.SubElement(world, "geom", {
        "name": "ground",
        "type": "plane",
        "size": f"{ground_size[0]:.12g} {ground_size[1]:.12g} 0.1",
        "rgba": _numbers(ground_rgba),
        "friction": _numbers(ground_friction),
    })
    if world_config is not None:
        for obstacle in world_config.obstacles:
            _add_obstacle(world, obstacle, world_config)
    body = ET.SubElement(world, "body", {"name": "drone_base", "pos": "0 0 0.25"})
    ET.SubElement(body, "freejoint", {"name": "drone_freejoint"})
    if vehicle.recipe.schema_version == 1:
        assert vehicle.center_of_mass_m is not None and vehicle.inertia_kg_m2 is not None
        ET.SubElement(body, "inertial", {"pos": _numbers(vehicle.center_of_mass_m), "mass": f"{vehicle.total_mass_kg:.12g}", "diaginertia": _numbers(vehicle.inertia_kg_m2)})
    vehicle_friction = world_config.contact.vehicle_friction if world_config is not None else (0.8, 0.1, 0.1)
    if frame.geometry is None:
        ET.SubElement(body, "geom", {"name": "frame", "type": "box", "size": _numbers(tuple(value / 2.0 for value in frame.dimensions_m)), "mass": "0", "rgba": "0.12 0.12 0.14 1", "friction": _numbers(vehicle_friction)})
    else:
        _add_assembly(body, "frame", frame.geometry, default_friction=vehicle_friction, physical_mass_kg=frame.mass_kg if vehicle.recipe.schema_version >= 2 else None)
    if vehicle.recipe.schema_version >= 2:
        for rotor in vehicle.rotors:
            assert vehicle.components.motor.geometry is not None
            assert vehicle.components.propeller.geometry is not None
            _add_assembly(body, f"motor_{rotor.name}", vehicle.components.motor.geometry, rotor.position_m, physical_mass_kg=vehicle.components.motor.mass_kg)
            _add_assembly(body, f"propeller_{rotor.name}", vehicle.components.propeller.geometry, rotor.position_m, physical_mass_kg=vehicle.components.propeller.mass_kg)
        for name, component, placement in (
            ("battery", vehicle.components.battery, vehicle.recipe.placements.battery),
            ("camera", vehicle.components.camera, vehicle.recipe.placements.camera),
            ("controller", vehicle.components.controller, vehicle.recipe.placements.controller),
        ):
            assert component.geometry is not None
            _add_assembly(body, name, component.geometry, placement.position_m, placement.rpy_deg, physical_mass_kg=component.mass_kg)
    if vehicle.components.landing_gear is not None:
        _add_assembly(
            body,
            "landing_gear",
            vehicle.components.landing_gear.geometry,
            vehicle.recipe.placements.landing_gear_m,
            vehicle.recipe.placements.landing_gear_rpy_deg,
            vehicle_friction,
            vehicle.components.landing_gear.mass_kg if vehicle.recipe.schema_version >= 2 else None,
        )
    for attachment in vehicle.attachments:
        _add_assembly(
            body,
            f"attachment_{attachment.name}",
            attachment.component.geometry,
            attachment.position_m,
            attachment.rpy_deg,
            vehicle_friction,
            attachment.component.mass_kg if vehicle.recipe.schema_version >= 2 and attachment.component.physical_role == "physical" else None,
        )
    for rotor in vehicle.rotors:
        rotor_body = ET.SubElement(body, "body", {"name": rotor.name, "pos": _numbers(rotor.position_m)})
        ET.SubElement(rotor_body, "geom", {"name": f"{rotor.name}_geom", "type": "cylinder", "size": f"{vehicle.components.propeller.diameter_m / 2.0:.12g} 0.0015", "mass": "0", "contype": "0", "conaffinity": "0", "rgba": "0.18 0.18 0.20 0.55"})
        ET.SubElement(rotor_body, "site", {"name": f"{rotor.name}_axis", "type": "sphere", "size": "0.006", "rgba": "0.9 0.2 0.15 1" if rotor.rotation_direction < 0 else "0.15 0.55 1 1"})
    camera_position = vehicle.recipe.placements.camera_m
    ET.SubElement(body, "geom", {"name": "fpv_camera", "type": "box", "pos": _numbers(camera_position), "size": _numbers(tuple(value / 2.0 for value in camera.dimensions_m)), "mass": "0", "contype": "0", "conaffinity": "0", "rgba": "0.15 0.15 0.15 1"})
    ET.SubElement(body, "camera", {"name": "fpv", "pos": _numbers(camera_position), "xyaxes": "0 -1 0 0 0 1", "fovy": f"{camera.fov_deg or 90.0:.12g}"})
    ET.indent(root, space="  ")
    output.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
