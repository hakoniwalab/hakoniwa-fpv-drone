from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .generators.hakoniwa_control_param import generate_control_parameters
from .generators.hakoniwa_drone_config import generate_drone_config
from .generators.mujoco import generate_mujoco
from .model import ResolvedVehicle
from .yaml_io import dump_yaml


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _component_dict(component: Any) -> dict[str, Any]:
    return asdict(component)


def build_bom(vehicle: ResolvedVehicle) -> dict[str, Any]:
    c = vehicle.components
    return {
        "schema_version": 1,
        "vehicle": vehicle.recipe.name,
        "items": [
            {"kind": "frame", "catalog_id": c.frame.id, "quantity": 1, "unit_mass_kg": c.frame.mass_kg},
            {"kind": "motor", "catalog_id": c.motor.id, "quantity": 4, "unit_mass_kg": c.motor.mass_kg},
            {"kind": "propeller", "catalog_id": c.propeller.id, "quantity": 4, "unit_mass_kg": c.propeller.mass_kg},
            {"kind": "battery", "catalog_id": c.battery.id, "quantity": 1, "unit_mass_kg": c.battery.mass_kg},
            {"kind": "camera", "catalog_id": c.camera.id, "quantity": 1, "unit_mass_kg": c.camera.mass_kg},
            {"kind": "controller", "catalog_id": c.controller.id, "quantity": 1, "unit_mass_kg": c.controller.mass_kg},
        ],
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
        },
    }


def build_report(vehicle: ResolvedVehicle) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "vehicle": vehicle.recipe.name,
        "properties": {
            "total_mass_kg": {"status": "calculated", "value": vehicle.total_mass_kg, "source": "catalog BOM sum"},
            "center_of_mass_m": {"status": "calculated", "value": list(vehicle.center_of_mass_m), "source": "catalog masses + recipe placements"},
            "inertia_kg_m2": {"status": "approximation", "value": list(vehicle.inertia_kg_m2), "reason": "frame catalog inertia or uniform box plus non-frame point masses"},
            "motor_positions_m": {"status": "calculated", "value": [list(rotor.position_m) for rotor in vehicle.rotors], "source": "quad-X geometry + frame wheelbase"},
            "maximum_rotor_speed_rad_s": {"status": "catalog" if vehicle.max_rad_per_sec_source == "catalog" else "approximation", "value": vehicle.max_rad_per_sec, "source": vehicle.max_rad_per_sec_source},
            "estimated_maximum_thrust_n": {"status": "estimate", "value": vehicle.estimated_max_thrust_n, "reason": "4 * catalog Ct * maximum rotor speed squared"},
            "thrust_to_weight_ratio": {"status": "estimate", "value": vehicle.thrust_to_weight_ratio, "reason": "estimated maximum thrust / catalog-derived weight"},
            "estimated_flight_time": {"status": "not_calculated", "value": None, "reason": "MVP has no mission current model"},
        },
        "approximations": list(vehicle.approximations),
        "limitations": [
            "Generated controller gains are initial values and are not validated for a real aircraft.",
            "The MuJoCo frame uses a box collision/visual proxy, not a product CAD model.",
            "Camera metadata targets future Three.js integration; the MVP does not generate a Three.js model.",
        ],
    }


def generate_package(vehicle: ResolvedVehicle, output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(vehicle.recipe.path, output / "recipe.yaml")
    dump_yaml(output / "resolved-components.yaml", resolved_components(vehicle))
    dump_yaml(output / "bom.yaml", build_bom(vehicle))
    generate_mujoco(vehicle, output / "drone.xml")
    generate_drone_config(vehicle, output / "drone_config.json")
    generate_control_parameters(vehicle, output / "control-param.json", output / "control-param.txt")
    report = build_report(vehicle)
    report["artifacts"] = {}
    for name in ("recipe.yaml", "resolved-components.yaml", "bom.yaml", "drone.xml", "drone_config.json", "control-param.json", "control-param.txt"):
        report["artifacts"][name] = {"sha256": _sha256(output / name)}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return output
