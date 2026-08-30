from __future__ import annotations

from dataclasses import dataclass
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


def _integer(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValidationError(f"{path} must be an integer")
    return value


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
    if not isinstance(contract_id, str) or not contract_id or not isinstance(counts, dict):
        raise ValidationError("Drone PRO rotor contract id/count fields are invalid")
    contract = DroneProRotorContract(
        path=path,
        contract_id=contract_id,
        runtime_min=_integer(counts.get("runtime_min"), "rotor_count.runtime_min"),
        controllable_min=_integer(counts.get("controllable_min"), "rotor_count.controllable_min"),
        maximum=_integer(counts.get("max"), "rotor_count.max"),
    )
    if not 1 <= contract.runtime_min <= contract.controllable_min <= contract.maximum:
        raise ValidationError("Drone PRO rotor contract count ordering is invalid")
    return contract
