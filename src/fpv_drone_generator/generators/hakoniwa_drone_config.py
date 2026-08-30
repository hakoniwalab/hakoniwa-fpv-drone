from __future__ import annotations

import json
from pathlib import Path

from ..model import ResolvedVehicle
from ..target import DroneProRotorContract


def generate_drone_config(vehicle: ResolvedVehicle, output: Path, rotor_contract: DroneProRotorContract | None = None, initial_z_m: float = 0.25) -> None:
    propeller = vehicle.components.propeller
    motor = vehicle.components.motor
    battery = vehicle.components.battery
    config = {
        # The current Drone PRO single-vehicle PDU definition uses the fixed
        # robot name "Drone". The user-facing vehicle name remains available
        # in recipe.yaml, resolved-components.yaml and report.json.
        "name": "Drone",
        "simulation": {
            "lockstep": True,
            "timeStep": 0.001,
            "logging": {"mode": "none"},
            "logOutputDirectory": ".",
            "location": {
                "latitude": 35.681236,
                "longitude": 139.767125,
                "altitude": 0.0,
                "magneticField": {"intensity_nT": 0.0, "declination_deg": 0.0, "inclination_deg": 0.0},
            },
        },
        "components": {
            "droneDynamics": {
                "physicsEquation": "MuJoCo",
                "mujoco": {"modelName": "drone_base", "propNames": [rotor.name for rotor in vehicle.rotors], "modelPath": "drone.xml"},
                "useQuaternion": True,
                "collision_detection": True,
                "enable_disturbance": True,
                "manual_control": False,
                "airFrictionCoefficient": [0.5, 0.0],
                # Required only by the legacy BodyFrame path. MuJoCo derives
                # rigid-body inertia from MJCF geoms and ignores this setter.
                "inertia": list(vehicle.inertia_kg_m2 or (0.0, 0.0, 0.0)),
                "mass_kg": vehicle.total_mass_kg,
                "body_size": list(vehicle.components.frame.dimensions_m),
                # MuJoCo world is Z-up while Drone PRO's vehicle state uses
                # NED/ROS-PDU convention here. The XML body starts at +0.25 m,
                # so its corresponding configured down position is -0.25 m.
                "position_meter": [0.0, 0.0, -initial_z_m],
                "angle_degree": [0.0, 0.0, 0.0],
                "body_boundary_disturbance_power": 1.0,
            },
            "battery": {
                "vendor": "None",
                "model": "constant",
                "BatteryModelCsvFilePath": "battery-model.csv",
                "VoltageLevelGreen": battery.nominal_voltage_v * 0.90,
                "VoltageLevelYellow": battery.nominal_voltage_v * 0.80,
                "CapacityLevelYellow": battery.capacity_ah * 0.20,
                "NominalVoltage": battery.nominal_voltage_v,
                "NominalCapacity": battery.capacity_ah,
                "EODVoltage": battery.cell_count * 3.0,
            },
            "rotor": {
                "vendor": "BatteryModel",
                "max_rad_per_sec": vehicle.max_rad_per_sec,
                "dynamics_constants": {
                    "R": motor.resistance_ohm,
                    "Ct": propeller.thrust_coefficient_ns2_rad2,
                    "Cq": propeller.torque_coefficient_nms2_rad2,
                    "K": motor.torque_constant_nm_per_a,
                    "D": motor.viscous_drag_nm_s_per_rad,
                    "J": motor.rotor_inertia_kg_m2,
                },
                "radius": propeller.diameter_m / 2.0,
            },
            "thruster": {
                "vendor": "MuJoCo",
                # ResolvedVehicle/MuJoCo use a Z-up frame. Drone PRO's rotor
                # geometry uses the vehicle frame whose Y axis has the
                # opposite sign. Preserve rotor index/name correspondence.
                "rotorPositions": [
                    {
                        "position": list(
                            rotor_contract.transform_position(rotor.position_m)
                            if rotor_contract is not None
                            else rotor.legacy_drone_pro_position_frd_m
                        ),
                        "rotationDirection": rotor.rotation_direction,
                    }
                    for rotor in vehicle.rotors
                ],
                "Ct": propeller.thrust_coefficient_ns2_rad2,
            },
            "sensors": {
                "acc": {"sampleCount": 1, "noise": 0.03},
                "gyro": {"sampleCount": 1, "noise": 0.0},
                "mag": {"sampleCount": 1, "noise": 0.03},
                "baro": {"sampleCount": 1, "noise": 0.01},
                "gps": {"sampleCount": 1, "noise": 0.0},
            },
        },
        "controller": {
            "serviceMode": "rc",
            "moduleName": "RadioController",
            "paramText": "",
            "paramFilePath": "control-param.txt",
            "backendType": "adapter-hakoniwa",
            "direct_rotor_control": False,
            "mixer": {"vendor": "None", "enableDebugLog": False, "enableErrorLog": False},
        },
        "fpv": {
            "controllerMode": vehicle.recipe.controller_mode,
            "camera": {"catalogId": vehicle.components.camera.id, "fov_deg": vehicle.components.camera.fov_deg, "position_m": list(vehicle.recipe.placements.camera_m)},
            "viewer": {"backend": "hakoniwa-threejs-drone", "status": "metadata-only-in-mvp"},
        },
    }
    output.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
