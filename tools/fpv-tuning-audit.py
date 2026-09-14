#!/usr/bin/env python3
"""Verify that generated FPV physics and controller tuning inputs agree.

This intentionally runs with the Foundation Python environment: that is the
environment which owns the MuJoCo binding used by the generated runtime.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import mujoco


def fail(checks: list[dict[str, object]], name: str, detail: str) -> None:
    checks.append({"name": name, "status": "error", "detail": detail})


def passed(checks: list[dict[str, object]], name: str, detail: str) -> None:
    checks.append({"name": name, "status": "ok", "detail": detail})


def parse_parameters(path: Path) -> dict[str, float]:
    result: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        content = line.split("#", 1)[0].strip()
        if not content:
            continue
        fields = content.split()
        if len(fields) >= 2:
            try:
                result[fields[0]] = float(fields[1])
            except ValueError:
                continue
    return result


def close(first: float, second: float, *, tolerance: float = 1e-9) -> bool:
    return math.isclose(first, second, rel_tol=tolerance, abs_tol=tolerance)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit generated Drone PRO PID tuning inputs.")
    parser.add_argument("vehicle_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    vehicle = args.vehicle_dir.resolve()
    config_path = vehicle / "drone_config_0.json"
    model_path = vehicle / "drone.xml"
    parameter_path = vehicle / "control-param.txt"
    missing = [str(path) for path in (config_path, model_path, parameter_path) if not path.is_file()]
    if missing:
        raise SystemExit("missing generated tuning input: " + ", ".join(missing))

    config = json.loads(config_path.read_text(encoding="utf-8"))
    parameters = parse_parameters(parameter_path)
    components = config["components"]
    dynamics = components["droneDynamics"]
    rotor = components["rotor"]
    thruster = components["thruster"]
    checks: list[dict[str, object]] = []

    mass = float(dynamics["mass_kg"])
    parameter_mass = parameters.get("MASS")
    if mass <= 0 or not math.isfinite(mass):
        fail(checks, "config_mass", f"mass_kg must be positive, got {mass}")
    else:
        passed(checks, "config_mass", f"mass_kg={mass}")
    if parameter_mass is None:
        fail(checks, "controller_mass", "MASS is absent from control-param.txt")
    elif not close(mass, parameter_mass):
        fail(checks, "controller_mass", f"drone_config mass_kg={mass} != control-param MASS={parameter_mass}")
    else:
        passed(checks, "controller_mass", f"MASS={parameter_mass} matches mass_kg")

    rotor_ct = float(rotor["dynamics_constants"]["Ct"])
    thruster_ct = float(thruster["Ct"])
    if rotor_ct <= 0 or not close(rotor_ct, thruster_ct):
        fail(checks, "thrust_coefficient", f"rotor Ct={rotor_ct} != thruster Ct={thruster_ct}")
    else:
        passed(checks, "thrust_coefficient", f"Ct={rotor_ct} is shared by rotor and thruster")
    for key in ("Cq", "R", "K", "J"):
        value = float(rotor["dynamics_constants"][key])
        if value <= 0 or not math.isfinite(value):
            fail(checks, f"rotor_{key}", f"{key} must be positive, got {value}")
        else:
            passed(checks, f"rotor_{key}", f"{key}={value}")
    maximum_speed = float(rotor["max_rad_per_sec"])
    if maximum_speed <= 0 or not math.isfinite(maximum_speed):
        fail(checks, "maximum_rotor_speed", f"max_rad_per_sec must be positive, got {maximum_speed}")
    else:
        passed(checks, "maximum_rotor_speed", f"max_rad_per_sec={maximum_speed}")

    model = mujoco.MjModel.from_xml_path(str(model_path))
    model_name = dynamics["mujoco"]["modelName"]
    body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, model_name)
    if body_id < 0:
        fail(checks, "mujoco_body", f"body {model_name!r} is absent from drone.xml")
        mujoco_mass = None
        inertia = None
        center_of_mass = None
    else:
        mujoco_mass = float(model.body_mass[body_id])
        inertia = [float(value) for value in model.body_inertia[body_id]]
        center_of_mass = [float(value) for value in model.body_ipos[body_id]]
        if close(mass, mujoco_mass, tolerance=1e-7):
            passed(checks, "mujoco_mass", f"MuJoCo body mass={mujoco_mass} matches mass_kg")
        else:
            fail(checks, "mujoco_mass", f"MuJoCo body mass={mujoco_mass} != mass_kg={mass}")

    props = dynamics["mujoco"].get("propNames", [])
    positions = thruster.get("rotorPositions", [])
    if len(props) != len(positions):
        fail(checks, "rotor_count", f"propNames={len(props)} != rotorPositions={len(positions)}")
    else:
        passed(checks, "rotor_count", f"{len(props)} rotor positions")
    rotor_audit: list[dict[str, object]] = []
    for index, (name, expected) in enumerate(zip(props, positions), start=1):
        direction = float(expected.get("rotationDirection", 0))
        expected_position = [float(value) for value in expected.get("position", [])]
        prop_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        item: dict[str, object] = {"index": index, "name": name, "rotation_direction": direction}
        if direction not in (-1.0, 1.0):
            fail(checks, f"rotor_{index}_direction", f"{name}: rotationDirection must be -1 or 1, got {direction}")
        if prop_id < 0:
            fail(checks, f"rotor_{index}_body", f"{name}: absent from drone.xml")
            item["status"] = "error"
        elif len(expected_position) != 3:
            fail(checks, f"rotor_{index}_position", f"{name}: invalid rotorPositions entry")
            item["status"] = "error"
        else:
            mujoco_position = [float(value) for value in model.body_pos[prop_id]]
            # MuJoCo FLU -> Drone PRO FRD. This is a coordinate conversion,
            # not a demand that raw XML and JSON have equal signs.
            transformed = [mujoco_position[0], -mujoco_position[1], -mujoco_position[2]]
            item.update({"mujoco_flu_m": mujoco_position, "drone_pro_frd_m": expected_position})
            if all(close(actual, required, tolerance=1e-7) for actual, required in zip(transformed, expected_position)):
                passed(checks, f"rotor_{index}_position", f"{name}: MuJoCo pose matches FRD rotor position")
                item["status"] = "ok"
            else:
                fail(checks, f"rotor_{index}_position", f"{name}: MuJoCo FLU {mujoco_position} converts to {transformed}, expected {expected_position}")
                item["status"] = "error"
        rotor_audit.append(item)

    report = {
        "schema_version": 1,
        "status": "failed" if any(check["status"] == "error" for check in checks) else "passed",
        "vehicle_dir": str(vehicle),
        "physical_model": {
            "mass_kg": mass,
            "mujoco_mass_kg": mujoco_mass,
            "mujoco_center_of_mass_m": center_of_mass,
            "mujoco_inertia_diagonal_kg_m2": inertia,
            "drone_config_inertia": dynamics.get("inertia"),
            "inertia_source": "MuJoCo inertiafromgeom" if dynamics.get("inertia") == [0.0, 0.0, 0.0] else "drone_config_0.json",
        },
        "controller": {"MASS": parameter_mass},
        "rotor_contract": {
            "Ct": rotor_ct,
            "Cq": float(rotor["dynamics_constants"]["Cq"]),
            "max_rad_per_sec": maximum_speed,
            "rotors": rotor_audit,
        },
        "checks": checks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Tuning input audit ({report['status']}): {args.output}")
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
