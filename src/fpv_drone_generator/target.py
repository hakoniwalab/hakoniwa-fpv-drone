from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
import json
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .model import ResolvedVehicle


@dataclass(frozen=True)
class DroneProRotorContract:
    path: Path
    contract_id: str
    runtime_min: int
    controllable_min: int
    maximum: int
    position_transform: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]

    def validate(self, vehicle: ResolvedVehicle) -> None:
        if vehicle.recipe.rotor_contract != self.contract_id:
            raise ValidationError(
                f"rotor contract mismatch: recipe={vehicle.recipe.rotor_contract!r} target={self.contract_id!r}"
            )
        count = len(vehicle.rotors)
        if count < self.controllable_min or count > self.maximum:
            raise ValidationError(
                f"Drone PRO controllable rotor count must be {self.controllable_min}..{self.maximum}: {count}"
            )

    def transform_position(self, position_flu_m: tuple[float, float, float]) -> tuple[float, float, float]:
        return tuple(
            sum(self.position_transform[row][column] * position_flu_m[column] for column in range(3))
            for row in range(3)
        )  # type: ignore[return-value]


def _integer(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{path} must be an integer")
    return value


def _matrix3(value: Any, path: str) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValidationError(f"{path} must contain three rows")
    rows = []
    for index, row in enumerate(value):
        if not isinstance(row, list) or len(row) != 3 or any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in row):
            raise ValidationError(f"{path}[{index}] must contain three numbers")
        rows.append(tuple(float(item) for item in row))
    return tuple(rows)  # type: ignore[return-value]


def bundled_drone_pro_rotor_contract_path() -> Path:
    return Path(str(files("fpv_drone_generator").joinpath("contracts/drone-pro-rotor-layout-v1.json")))


def load_drone_pro_rotor_contract(path: Path) -> DroneProRotorContract:
    path = path.resolve()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load Drone PRO rotor contract {path}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValidationError("Drone PRO rotor contract must have schema_version: 1")
    contract_id = raw.get("contract_id")
    counts = raw.get("rotor_count")
    transform = raw.get("position_transform")
    if not isinstance(contract_id, str) or not contract_id or not isinstance(counts, dict) or not isinstance(transform, dict):
        raise ValidationError("Drone PRO rotor contract id/count fields are invalid")
    contract = DroneProRotorContract(
        path=path,
        contract_id=contract_id,
        runtime_min=_integer(counts.get("runtime_min"), "rotor_count.runtime_min"),
        controllable_min=_integer(counts.get("controllable_min"), "rotor_count.controllable_min"),
        maximum=_integer(counts.get("max"), "rotor_count.max"),
        position_transform=_matrix3(transform.get("matrix"), "position_transform.matrix"),
    )
    if not 1 <= contract.runtime_min <= contract.controllable_min <= contract.maximum:
        raise ValidationError("Drone PRO rotor contract count ordering is invalid")
    return contract
