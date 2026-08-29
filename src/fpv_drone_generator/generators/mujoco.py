from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from ..model import ResolvedVehicle


def _numbers(values: tuple[float, ...]) -> str:
    return " ".join(f"{value:.12g}" for value in values)


def generate_mujoco(vehicle: ResolvedVehicle, output: Path) -> None:
    frame = vehicle.components.frame
    camera = vehicle.components.camera
    root = ET.Element("mujoco", {"model": vehicle.recipe.name})
    ET.SubElement(root, "compiler", {"angle": "degree", "inertiafromgeom": "false"})
    ET.SubElement(root, "option", {"timestep": "0.001", "density": "1.204", "viscosity": "0.000018", "integrator": "RK4"})
    visual = ET.SubElement(root, "visual")
    ET.SubElement(visual, "global", {"azimuth": "135", "elevation": "-20"})
    world = ET.SubElement(root, "worldbody")
    ET.SubElement(world, "light", {"pos": "0 0 4", "diffuse": "0.8 0.8 0.8"})
    ET.SubElement(world, "geom", {"name": "ground", "type": "plane", "size": "5 5 0.1", "rgba": "0.18 0.20 0.22 1"})
    body = ET.SubElement(world, "body", {"name": "drone_base", "pos": "0 0 0.25"})
    ET.SubElement(body, "freejoint", {"name": "drone_freejoint"})
    ET.SubElement(body, "inertial", {"pos": _numbers(vehicle.center_of_mass_m), "mass": f"{vehicle.total_mass_kg:.12g}", "diaginertia": _numbers(vehicle.inertia_kg_m2)})
    ET.SubElement(body, "geom", {"name": "frame", "type": "box", "size": _numbers(tuple(value / 2.0 for value in frame.dimensions_m)), "mass": "0", "rgba": "0.12 0.12 0.14 1", "friction": "0.8 0.1 0.1"})
    for rotor in vehicle.rotors:
        rotor_body = ET.SubElement(body, "body", {"name": rotor.name, "pos": _numbers(rotor.position_m)})
        ET.SubElement(rotor_body, "geom", {"name": f"{rotor.name}_geom", "type": "cylinder", "size": f"{vehicle.components.propeller.diameter_m / 2.0:.12g} 0.0015", "mass": "0", "contype": "0", "conaffinity": "0", "rgba": "0.18 0.18 0.20 0.55"})
        ET.SubElement(rotor_body, "site", {"name": f"{rotor.name}_axis", "type": "sphere", "size": "0.006", "rgba": "0.9 0.2 0.15 1" if rotor.rotation_direction < 0 else "0.15 0.55 1 1"})
    camera_position = vehicle.recipe.placements.camera_m
    ET.SubElement(body, "geom", {"name": "fpv_camera", "type": "box", "pos": _numbers(camera_position), "size": _numbers(tuple(value / 2.0 for value in camera.dimensions_m)), "mass": "0", "contype": "0", "conaffinity": "0", "rgba": "0.15 0.15 0.15 1"})
    ET.SubElement(body, "camera", {"name": "fpv", "pos": _numbers(camera_position), "xyaxes": "0 -1 0 0 0 1", "fovy": f"{camera.fov_deg or 90.0:.12g}"})
    ET.indent(root, space="  ")
    output.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
