from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .generators.hakoniwa_control_param import generate_control_parameters
from .generators.hakoniwa_drone_config import generate_drone_config
from .generators.mujoco import generate_mujoco
from .geometry_bounds import vehicle_collision_lower_bound
from .generators.threejs_course import generate_threejs_course
from .model import ResolvedVehicle
from .target import DroneProRotorContract
from .world import World
from .yaml_io import dump_yaml


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _component_dict(component: Any) -> dict[str, Any]:
    return asdict(component)


def build_bom(vehicle: ResolvedVehicle) -> dict[str, Any]:
    c = vehicle.components
    items = [
        {"kind": "frame", "catalog_id": c.frame.id, "quantity": 1, "unit_mass_kg": c.frame.mass_kg},
        {"kind": "motor", "catalog_id": c.motor.id, "quantity": len(vehicle.rotors), "unit_mass_kg": c.motor.mass_kg},
        {"kind": "propeller", "catalog_id": c.propeller.id, "quantity": len(vehicle.rotors), "unit_mass_kg": c.propeller.mass_kg},
        {"kind": "battery", "catalog_id": c.battery.id, "quantity": 1, "unit_mass_kg": c.battery.mass_kg},
        {"kind": "camera", "catalog_id": c.camera.id, "quantity": 1, "unit_mass_kg": c.camera.mass_kg},
        {"kind": "controller", "catalog_id": c.controller.id, "quantity": 1, "unit_mass_kg": c.controller.mass_kg},
    ]
    if c.landing_gear is not None:
        items.append({"kind": "landing_gear", "catalog_id": c.landing_gear.id, "quantity": 1, "unit_mass_kg": c.landing_gear.mass_kg})
    attachment_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for attachment in vehicle.attachments:
        key = (attachment.component.id, attachment.component.physical_role)
        if key not in attachment_rows:
            attachment_rows[key] = {
                "kind": "attachment",
                "catalog_id": attachment.component.id,
                "quantity": 0,
                "instance_names": [],
                "unit_mass_kg": attachment.component.mass_kg if attachment.component.physical_role == "physical" else 0.0,
                "physical_role": attachment.component.physical_role,
            }
            items.append(attachment_rows[key])
        attachment_rows[key]["quantity"] += 1
        attachment_rows[key]["instance_names"].append(attachment.name)
    return {
        "schema_version": 1,
        "vehicle": vehicle.recipe.name,
        "items": items,
        "total_mass_kg": vehicle.total_mass_kg,
    }


def resolved_components(vehicle: ResolvedVehicle) -> dict[str, Any]:
    c = vehicle.components
    return {
        "schema_version": 1,
        "recipe": vehicle.recipe.name,
        "components": {
            "frame": _component_dict(c.frame),
            "motor": _component_dict(c.motor),
            "propeller": _component_dict(c.propeller),
            "battery": _component_dict(c.battery),
            "camera": _component_dict(c.camera),
            "controller": _component_dict(c.controller),
            "landing_gear": None if c.landing_gear is None else _component_dict(c.landing_gear),
            "attachments": [
                {
                    "name": attachment.name,
                    "component": _component_dict(attachment.component),
                    "parent": attachment.parent,
                    "position_m": list(attachment.position_m),
                    "rpy_deg": list(attachment.rpy_deg),
                }
                for attachment in vehicle.attachments
            ],
        },
    }


def build_report(vehicle: ResolvedVehicle, rotor_contract: DroneProRotorContract | None = None) -> dict[str, Any]:
    drone_pro_positions = [
        list(rotor_contract.transform_position(rotor.position_m) if rotor_contract is not None else rotor.legacy_drone_pro_position_frd_m)
        for rotor in vehicle.rotors
    ]
    return {
        "schema_version": 1,
        "vehicle": vehicle.recipe.name,
        "properties": {
            "total_mass_kg": {"status": "calculated", "value": vehicle.total_mass_kg, "source": "catalog BOM sum"},
            "center_of_mass_m": (
                {"status": "delegated", "value": None, "source": "MuJoCo inertiafromgeom"}
                if vehicle.center_of_mass_m is None
                else {"status": "calculated", "value": list(vehicle.center_of_mass_m), "source": "legacy v1 catalog masses + recipe placements"}
            ),
            "inertia_kg_m2": (
                {"status": "delegated", "value": None, "source": "MuJoCo inertiafromgeom"}
                if vehicle.inertia_kg_m2 is None
                else {"status": "approximation", "value": list(vehicle.inertia_kg_m2), "reason": "legacy v1 frame inertia or uniform box plus non-frame point masses"}
            ),
            "motor_positions_m": {"status": "resolved", "value": [list(rotor.position_m) for rotor in vehicle.rotors], "source": "explicit rotor_layout or legacy quad-X wheelbase mapping"},
            "drone_pro_rotor_positions_frd_m": {"status": "resolved", "value": drone_pro_positions, "source": vehicle.recipe.rotor_contract or "legacy quad adapter mapping"},
            "maximum_rotor_speed_rad_s": {"status": "catalog" if vehicle.max_rad_per_sec_source == "catalog" else "approximation", "value": vehicle.max_rad_per_sec, "source": vehicle.max_rad_per_sec_source},
            "estimated_maximum_thrust_n": {"status": "estimate", "value": vehicle.estimated_max_thrust_n, "reason": f"{len(vehicle.rotors)} * catalog Ct * maximum rotor speed squared"},
            "thrust_to_weight_ratio": {"status": "estimate", "value": vehicle.thrust_to_weight_ratio, "reason": "estimated maximum thrust / catalog-derived weight"},
            "estimated_flight_time": {"status": "not_calculated", "value": None, "reason": "MVP has no mission current model"},
        },
        "approximations": list(vehicle.approximations),
        "limitations": [
            "Generated controller gains are initial values and are not validated for a real aircraft.",
            "MuJoCo geometry uses catalog primitives, not product CAD, unless a catalog explicitly states otherwise.",
            "Three.js uses an existing visual drone model scaled to the generated wheelbase; it is not product CAD.",
        ],
    }


def generate_package(vehicle: ResolvedVehicle, output: Path, world: World | None = None, rotor_contract: DroneProRotorContract | None = None) -> Path:
    if vehicle.recipe.schema_version >= 2:
        if rotor_contract is None:
            raise ValidationError("schema v2 package generation requires a Drone PRO target contract")
        rotor_contract.validate(vehicle)
    output.mkdir(parents=True, exist_ok=True)
    initial_z_m = 0.25 if vehicle.recipe.schema_version == 1 else -vehicle_collision_lower_bound(vehicle) + vehicle.recipe.ground_clearance_m
    shutil.copyfile(vehicle.recipe.path, output / "recipe.yaml")
    dump_yaml(output / "resolved-components.yaml", resolved_components(vehicle))
    dump_yaml(output / "bom.yaml", build_bom(vehicle))
    if world is not None:
        shutil.copyfile(world.path, output / "world.yaml")
        generate_threejs_course(world, output / "fpv-course.json")
    generate_mujoco(vehicle, output / "drone.xml", world, initial_z_m)
    generate_drone_config(vehicle, output / "drone_config.json", rotor_contract, initial_z_m)
    generate_control_parameters(vehicle, output / "control-param.json", output / "control-param.txt")
    report = build_report(vehicle, rotor_contract)
    report["initial_pose"] = {"mujoco_z_m": initial_z_m, "ground_clearance_m": vehicle.recipe.ground_clearance_m}
    report["artifacts"] = {}
    artifacts = ["recipe.yaml", "resolved-components.yaml", "bom.yaml", "drone.xml", "drone_config.json", "control-param.json", "control-param.txt"]
    if world is not None:
        artifacts.extend(("world.yaml", "fpv-course.json"))
        report["world"] = {
            "source": str(world.path),
            "obstacle_count": len(world.obstacles),
            "light_count": len(world.lights),
        }
    for name in artifacts:
        report["artifacts"][name] = {"sha256": _sha256(output / name)}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return output
