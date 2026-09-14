from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from . import catalog_core as _core
from .catalog_core import (
    AssemblyPort,
    Attachment,
    Battery,
    Camera,
    CatalogGroup,
    CatalogStore,
    CatalogType,
    Common,
    Controller,
    Frame,
    GeometryAssembly,
    GeometryPrimitive,
    LandingGear,
    Motor,
    Propeller,
    Vector3,
    Vector4,
)
from .errors import ValidationError
from .yaml_io import load_yaml


_PRODUCT_DIRS = {
    kind: filename.removesuffix(".yaml")
    for kind, (filename, _factory) in _core._LOADERS.items()
}


def _insert_item(items: dict[str, Any], factory: Any, entry: Any, entry_path: str, kind: str) -> None:
    if not isinstance(entry, dict):
        raise ValidationError(f"{entry_path} must be an object")
    item = factory(entry, entry_path)
    if item.id in items:
        raise ValidationError(f"duplicate {kind} catalog id across catalog roots: {item.id}")
    items[item.id] = item


def _load_source_ref(root: Path, fragment_path: Path, kind: str, item_id: str, source_ref: Any) -> dict[str, Any]:
    if not isinstance(source_ref, str) or not source_ref:
        raise ValidationError(f"{fragment_path}.source_ref must be a non-empty string")
    root = root.resolve()
    source_path = (root / source_ref).resolve()
    if not source_path.is_relative_to(root):
        raise ValidationError(f"{fragment_path}.source_ref must stay inside the catalog root")
    if not source_path.is_file():
        raise ValidationError(f"{fragment_path}.source_ref does not exist: {source_ref}")
    source = load_yaml(source_path)
    if source.get("schema_version") != 1 or source.get("kind") != "catalog-source":
        raise ValidationError(f"{source_path} must declare schema_version: 1 and kind: catalog-source")
    if source.get("product_id") != item_id:
        raise ValidationError(f"{source_path}.product_id must match {item_id}")
    if source.get("product_kind") != kind:
        raise ValidationError(f"{source_path}.product_kind must be {kind}")
    sources = source.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValidationError(f"{source_path}.sources must be a non-empty array")
    for index, entry in enumerate(sources):
        if not isinstance(entry, dict) or not isinstance(entry.get("url"), str) or not entry["url"]:
            raise ValidationError(f"{source_path}.sources[{index}].url must be a non-empty string")
    return source


def _with_source_metadata(entry: dict[str, Any], source_ref: str, source: dict[str, Any]) -> dict[str, Any]:
    result = dict(entry)
    metadata = dict(result.get("metadata", {}))
    metadata["source_ref"] = source_ref
    metadata["source_urls"] = [source_entry["url"] for source_entry in source["sources"]]
    result["metadata"] = metadata
    return result


def _load_group(roots: tuple[Path, ...], kind: str) -> CatalogGroup[Any]:
    filename, factory = _core._LOADERS[kind]
    items: dict[str, Any] = {}
    found = False
    for root in roots:
        catalog_path = root / filename
        if catalog_path.is_file():
            found = True
            raw = load_yaml(catalog_path)
            if raw.get("schema_version") != 1 or raw.get("kind") != kind:
                raise ValidationError(f"{catalog_path} must declare schema_version: 1 and kind: {kind}")
            entries = raw.get("items")
            if not isinstance(entries, list):
                raise ValidationError(f"{catalog_path}.items must be an array")
            for index, entry in enumerate(entries):
                _insert_item(items, factory, entry, f"{catalog_path}.items[{index}]", kind)

        fragment_root = root / "products" / _PRODUCT_DIRS[kind]
        if fragment_root.is_dir():
            fragment_paths = sorted(path for path in fragment_root.rglob("*.yaml") if path.is_file())
            if fragment_paths:
                found = True
            for fragment_path in fragment_paths:
                raw = load_yaml(fragment_path)
                if raw.get("schema_version") != 1 or raw.get("kind") != kind:
                    raise ValidationError(f"{fragment_path} must declare schema_version: 1 and kind: {kind}")
                entry = raw.get("item")
                if not isinstance(entry, dict):
                    raise ValidationError(f"{fragment_path}.item must be an object")
                item_id = entry.get("id")
                if not isinstance(item_id, str) or not item_id:
                    raise ValidationError(f"{fragment_path}.item.id must be a non-empty string")
                source_ref = raw.get("source_ref")
                source = _load_source_ref(root, fragment_path, kind, item_id, source_ref)
                entry = _with_source_metadata(entry, source_ref, source)
                _insert_item(items, factory, entry, f"{fragment_path}.item", kind)

    if not found:
        raise ValidationError(
            f"missing {filename} and products/{_PRODUCT_DIRS[kind]}/ fragments in catalog roots"
        )
    return CatalogGroup(kind, items)


def load_catalogs(root: Path | Iterable[Path]) -> CatalogStore:
    roots = (root.resolve(),) if isinstance(root, Path) else tuple(path.resolve() for path in root)
    if not roots:
        raise ValidationError("at least one catalog root is required")
    return CatalogStore(
        root=roots[0],
        roots=roots,
        frames=_load_group(roots, "frame"),
        motors=_load_group(roots, "motor"),
        propellers=_load_group(roots, "propeller"),
        batteries=_load_group(roots, "battery"),
        cameras=_load_group(roots, "camera"),
        controllers=_load_group(roots, "controller"),
        landing_gears=_load_group(roots, "landing_gear"),
        attachments=_load_group(roots, "attachment"),
    )
