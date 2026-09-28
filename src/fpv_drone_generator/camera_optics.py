"""FPV camera optics shared by the MuJoCo and Three.js generators.

A catalog camera's ``fov_deg`` is its diagonal field of view on a 4:3 FPV
sensor, as camera products state it. Renderers (MuJoCo ``fovy``, Three.js
``PerspectiveCamera.fov``) take the vertical field of view, so it is
converted here; passing the diagonal value as the vertical one renders a far
wider, flattened picture.

``uptilt_deg`` tilts the camera up from the body's forward axis, as FPV
pilots mount it to look ahead while the drone pitches forward.
"""

from __future__ import annotations

import math

# FPV camera sensors are 4:3 (width:height), so height / diagonal = 3 / 5.
SENSOR_ASPECT = (4.0, 3.0)
# The vertical field of view when a camera states none.
DEFAULT_VERTICAL_FOV_DEG = 90.0


def vertical_fov_deg(diagonal_fov_deg: float | None) -> float:
    """The vertical field of view of a camera with this diagonal one (4:3 sensor)."""
    if diagonal_fov_deg is None:
        return DEFAULT_VERTICAL_FOV_DEG
    width, height = SENSOR_ASPECT
    half = math.radians(diagonal_fov_deg) / 2.0
    return math.degrees(2.0 * math.atan(math.tan(half) * height / math.hypot(width, height)))


def mujoco_xyaxes(uptilt_deg: float) -> str:
    """MuJoCo camera xyaxes for a forward camera tilted up by uptilt_deg.

    The camera's right axis stays body -Y; its up axis leans back, so the
    view (-Z of the camera) points forward and up.
    """
    tilt = math.radians(uptilt_deg)
    values = (0.0, -1.0, 0.0, -math.sin(tilt), 0.0, math.cos(tilt))
    # + 0.0 turns -0.0 into 0.0, so an untilted camera reads "0 -1 0 0 0 1".
    return " ".join(f"{value + 0.0:.12g}" for value in values)


def uptilt_from_xyaxes(xyaxes: list[float]) -> float | None:
    """The uptilt of a forward camera's xyaxes, or None for any other orientation."""
    if len(xyaxes) != 6:
        return None
    right, up = xyaxes[:3], xyaxes[3:]
    if any(abs(a - b) > 1e-6 for a, b in zip(right, (0.0, -1.0, 0.0))) or abs(up[1]) > 1e-6:
        return None
    if abs(math.hypot(up[0], up[2]) - 1.0) > 1e-6 or up[2] <= 0:
        return None
    return math.degrees(math.atan2(-up[0], up[2]))
