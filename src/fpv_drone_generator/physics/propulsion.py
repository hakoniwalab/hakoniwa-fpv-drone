from __future__ import annotations

import math


def max_rotor_speed_rad_s(kv_rpm_per_v: float, voltage_v: float, explicit_max: float | None) -> tuple[float, str]:
    if explicit_max is not None:
        return explicit_max, "catalog"
    no_load = kv_rpm_per_v * voltage_v * (2.0 * math.pi / 60.0)
    return no_load * 0.85, "approximation: 85% of catalog KV no-load speed"


def max_total_thrust_n(rotor_count: int, coefficient: float, max_rad_per_sec: float) -> float:
    return rotor_count * coefficient * max_rad_per_sec * max_rad_per_sec
