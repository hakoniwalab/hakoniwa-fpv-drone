from __future__ import annotations

import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from .catalog import CatalogStore, CatalogType, Frame, GeometryPrimitive, Propeller
from .errors import FpvDroneError, ResolutionError


SHOWROOM_KINDS = (
    "frame",
    "motor",
    "propeller",
    "battery",
    "camera",
    "controller",
    "landing_gear",
    "attachment",
)

_GROUP_ATTR = {
    "frame": "frames",
    "motor": "motors",
    "propeller": "propellers",
    "battery": "batteries",
    "camera": "cameras",
    "controller": "controllers",
    "landing_gear": "landing_gears",
    "attachment": "attachments",
}

_KIND_RGBA = {
    "frame": (0.20, 0.24, 0.28, 1.0),
    "motor": (0.16, 0.17, 0.19, 1.0),
    "propeller": (0.18, 0.48, 0.50, 1.0),
    "battery": (0.16, 0.16, 0.18, 1.0),
    "camera": (0.24, 0.26, 0.28, 1.0),
    "controller": (0.20, 0.32, 0.42, 1.0),
    "landing_gear": (0.28, 0.30, 0.32, 1.0),
    "attachment": (0.38, 0.32, 0.22, 1.0),
}

_ITEM_SPACING_M = 0.42
_ROW_SPACING_M = 0.52
_PEDESTAL_HALF_SIZE = (0.15, 0.15, 0.012)
_COMPONENT_Z_M = 0.055


@dataclass(frozen=True)
class ShowroomItem:
    kind: str
    component: CatalogType


@dataclass(frozen=True)
class DisplayPrimitive:
    primitive_type: str
    center_m: tuple[float, float, float]
    rpy_deg: tuple[float, float, float]
    rgba: tuple[float, float, float, float]
    dimensions_m: tuple[float, float, float] | None = None
    radius_m: float | None = None
    length_m: float | None = None


def _fmt(values) -> str:
    return " ".join(f"{float(value):.6g}" for value in values)


def _from_catalog_primitive(
    primitive: GeometryPrimitive,
    fallback_rgba: tuple[float, float, float, float],
) -> DisplayPrimitive:
    return DisplayPrimitive(
        primitive_type=primitive.primitive_type,
        center_m=primitive.center_m,
        rpy_deg=primitive.rpy_deg,
        rgba=primitive.rgba if primitive.rgba[3] > 0.0 else fallback_rgba,
        dimensions_m=primitive.dimensions_m,
        radius_m=primitive.radius_m,
        length_m=primitive.length_m,
    )


def _display_geometry(component: CatalogType, kind: str) -> list[DisplayPrimitive]:
    rgba = _KIND_RGBA[kind]
    geometry = component.geometry
    if geometry is not None and geometry.visual:
        return [_from_catalog_primitive(primitive, rgba) for primitive in geometry.visual]

    if isinstance(component, Propeller):
        result = [
            DisplayPrimitive(
                "cylinder",
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 0.0),
                rgba,
                radius_m=max(component.diameter_m * 0.045, 0.004),
                length_m=0.006,
            )
        ]
        blade_length = component.diameter_m * 0.42
        blade_width = max(component.diameter_m * 0.055, 0.004)
        radial_center = component.diameter_m * 0.24
        for index in range(component.blade_count):
            yaw = 360.0 * index / component.blade_count
            angle = math.radians(yaw)
            result.append(
                DisplayPrimitive(
                    "box",
                    (
                        radial_center * math.cos(angle),
                        radial_center * math.sin(angle),
                        0.0,
                    ),
                    (0.0, 0.0, yaw),
                    rgba,
                    dimensions_m=(blade_length, blade_width, 0.003),
                )
            )
        return result

    if isinstance(component, Frame):
        arm_length = max(
            component.wheelbase_m * 0.92,
            max(component.dimensions_m[:2]) * 0.80,
        )
        arm_width = max(
            min(component.dimensions_m[0], component.dimensions_m[1]) * 0.055,
            0.008,
        )
        thickness = max(component.dimensions_m[2] * 0.25, 0.004)
        result = [
            DisplayPrimitive(
                "box",
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 45.0),
                rgba,
                dimensions_m=(arm_length, arm_width, thickness),
            ),
            DisplayPrimitive(
                "box",
                (0.0, 0.0, 0.0),
                (0.0, 0.0, -45.0),
                rgba,
                dimensions_m=(arm_length, arm_width, thickness),
            ),
            DisplayPrimitive(
                "box",
                (0.0, 0.0, thickness * 0.65),
                (0.0, 0.0, 0.0),
                rgba,
                dimensions_m=(
                    component.dimensions_m[0] * 0.35,
                    component.dimensions_m[1] * 0.35,
                    max(component.dimensions_m[2] * 0.45, 0.006),
                ),
            ),
        ]
        mount_positions = component.motor_mount_positions_m
        if mount_positions is None:
            offset = component.wheelbase_m * 0.5 / math.sqrt(2.0)
            mount_positions = (
                (offset, -offset, 0.0),
                (offset, offset, 0.0),
                (-offset, offset, 0.0),
                (-offset, -offset, 0.0),
            )
        for x, y, z in mount_positions:
            result.append(
                DisplayPrimitive(
                    "cylinder",
                    (x, y, z + thickness * 0.5),
                    (0.0, 0.0, 0.0),
                    rgba,
                    radius_m=max(arm_width * 0.8, 0.006),
                    length_m=max(thickness, 0.004),
                )
            )
        return result

    if geometry is not None and geometry.inertial:
        return [_from_catalog_primitive(primitive, rgba) for primitive in geometry.inertial]

    dimensions = getattr(component, "dimensions_m", None)
    if dimensions is not None:
        return [
            DisplayPrimitive(
                "box",
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 0.0),
                rgba,
                dimensions_m=dimensions,
            )
        ]

    return [
        DisplayPrimitive(
            "box",
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            rgba,
            dimensions_m=(0.04, 0.04, 0.015),
        )
    ]


def _append_geom(
    parent: ET.Element,
    name_prefix: str,
    primitive: DisplayPrimitive,
    index: int,
) -> None:
    attrs = {
        "name": f"{name_prefix}__visual_{index}",
        "type": primitive.primitive_type,
        "pos": _fmt(primitive.center_m),
        "euler": _fmt(primitive.rpy_deg),
        "rgba": _fmt(primitive.rgba),
        "contype": "0",
        "conaffinity": "0",
        "group": "1",
    }
    if primitive.primitive_type in ("box", "ellipsoid"):
        assert primitive.dimensions_m is not None
        attrs["size"] = _fmt(value * 0.5 for value in primitive.dimensions_m)
    elif primitive.primitive_type in ("cylinder", "capsule"):
        assert primitive.radius_m is not None and primitive.length_m is not None
        attrs["size"] = _fmt((primitive.radius_m, primitive.length_m * 0.5))
    elif primitive.primitive_type == "sphere":
        assert primitive.radius_m is not None
        attrs["size"] = _fmt((primitive.radius_m,))
    ET.SubElement(parent, "geom", attrs)


def _selected_items(
    catalogs: CatalogStore,
    kind: str | None,
    item_id: str | None,
) -> list[ShowroomItem]:
    if item_id is not None and kind is None:
        raise ResolutionError("catalog-view item id requires a component kind")

    kinds = (kind,) if kind is not None else SHOWROOM_KINDS
    result: list[ShowroomItem] = []
    for selected_kind in kinds:
        group = getattr(catalogs, _GROUP_ATTR[selected_kind])
        if item_id is not None:
            result.append(ShowroomItem(selected_kind, group.get(item_id)))
        else:
            result.extend(
                ShowroomItem(selected_kind, component)
                for component in group.items.values()
            )
    return result


def generate_catalog_showroom(
    catalogs: CatalogStore,
    output_path: Path,
    kind: str | None = None,
    item_id: str | None = None,
) -> Path:
    if kind is not None and kind not in SHOWROOM_KINDS:
        raise ResolutionError(f"unsupported catalog kind: {kind}")

    items = _selected_items(catalogs, kind, item_id)
    if not items:
        raise ResolutionError("catalog selection is empty")

    rows: dict[str, list[CatalogType]] = {}
    for item in items:
        rows.setdefault(item.kind, []).append(item.component)

    max_columns = max(len(components) for components in rows.values())
    center_y = -0.5 * (len(rows) - 1) * _ROW_SPACING_M
    half_width = 0.5 * (max_columns - 1) * _ITEM_SPACING_M
    half_height = 0.5 * (len(rows) - 1) * _ROW_SPACING_M
    extent = max(0.8, half_width + 0.35, half_height + 0.35)

    root = ET.Element("mujoco", {"model": "hakoniwa_fpv_catalog_showroom"})
    ET.SubElement(root, "compiler", {"angle": "degree"})
    ET.SubElement(
        root,
        "statistic",
        {"center": _fmt((0.0, center_y, 0.20)), "extent": f"{extent:.6g}"},
    )
    visual = ET.SubElement(root, "visual")
    ET.SubElement(
        visual,
        "headlight",
        {
            "ambient": "0.45 0.45 0.45",
            "diffuse": "0.8 0.8 0.8",
            "specular": "0.15 0.15 0.15",
        },
    )
    worldbody = ET.SubElement(root, "worldbody")
    ET.SubElement(
        worldbody,
        "geom",
        {
            "name": "showroom_floor",
            "type": "plane",
            "size": "4 4 0.1",
            "rgba": "0.92 0.92 0.92 1",
            "friction": "1 0.01 0.001",
        },
    )
    ET.SubElement(
        worldbody,
        "light",
        {
            "name": "key_light",
            "pos": _fmt((0.0, center_y, 3.0)),
            "dir": "0 0 -1",
            "diffuse": "0.8 0.8 0.8",
        },
    )

    for row_index, (row_kind, components) in enumerate(rows.items()):
        y = -row_index * _ROW_SPACING_M
        x0 = -0.5 * _ITEM_SPACING_M * (len(components) - 1)
        for column_index, component in enumerate(components):
            x = x0 + column_index * _ITEM_SPACING_M
            name_prefix = f"{row_kind}__{component.id}"
            body = ET.SubElement(
                worldbody,
                "body",
                {"name": name_prefix, "pos": _fmt((x, y, _COMPONENT_Z_M))},
            )
            ET.SubElement(
                body,
                "geom",
                {
                    "name": f"{name_prefix}__pedestal",
                    "type": "box",
                    "pos": _fmt(
                        (
                            0.0,
                            0.0,
                            -_COMPONENT_Z_M + _PEDESTAL_HALF_SIZE[2],
                        )
                    ),
                    "size": _fmt(_PEDESTAL_HALF_SIZE),
                    "rgba": "0.30 0.31 0.33 1",
                    "contype": "0",
                    "conaffinity": "0",
                    "group": "2",
                },
            )
            for primitive_index, primitive in enumerate(
                _display_geometry(component, row_kind)
            ):
                _append_geom(body, name_prefix, primitive, primitive_index)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return output_path


def open_catalog_showroom(path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "mujoco.viewer", f"--mjcf={path}"],
        check=False,
    )
    if result.returncode != 0:
        raise FpvDroneError(
            "MuJoCo Viewer failed to start. Install the optional 'mujoco' Python package "
            "or rerun catalog-view with --no-open."
        )
