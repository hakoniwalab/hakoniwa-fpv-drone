# Catalog Showroom

`tools/fpv-catalog.py` turns the FPV component Catalog into lightweight visual assets for demonstrations, inspection, and future browser composition.

The Catalog YAML remains the source of truth. The normal `fpv-drone` vehicle-generation CLI remains separate.

## Workflow

```text
prepare -> doctor -> open-viewer
                  -> export-glb
```

### Prepare

```bash
python3 tools/fpv-catalog.py prepare
```

The repository-local environment is created at `build/catalog-showroom/.venv` and installs `.[showroom]`. The global Python environment is not modified.

### Doctor

```bash
python3 tools/fpv-catalog.py doctor
```

`doctor` validates Catalog loading, generates and loads the MuJoCo showroom, exports all GLB assets, and loads one generated GLB back through trimesh.

### Open Viewer

```bash
python3 tools/fpv-catalog.py open-viewer
python3 tools/fpv-catalog.py open-viewer motor
python3 tools/fpv-catalog.py open-viewer motor generic_2207_1850kv
```

### Export GLB

Export every Catalog component as an individual browser-ready GLB asset:

```bash
python3 tools/fpv-catalog.py export-glb
```

Filter by kind or item with the same selection syntax used by `open-viewer`:

```bash
python3 tools/fpv-catalog.py export-glb motor
python3 tools/fpv-catalog.py export-glb motor generic_2207_1850kv
```

Default output:

```text
build/catalog-showroom/glb/
├── manifest.json
├── frame/generic_5inch_x.glb
├── motor/generic_2207_1850kv.glb
├── propeller/generic_5inch_3blade.glb
└── ...
```

Choose another destination with `--output-dir`.

`manifest.json` is intended as the browser-side Catalog index. Each entry contains the Catalog kind/id/name, description, relative GLB path, selected engineering specs, metadata, and generated bounds/extents.

The GLB contains only the component in its Catalog-local frame. Showroom floors and pedestals are not exported, so browser code can position parts freely.

## Additional Catalog roots

`doctor`, `open-viewer`, and `export-glb` accept repeatable `--catalogs` arguments for public/private Catalog composition.

## Rendering rules

MuJoCo showroom and GLB export share the same display-geometry resolution:

1. `geometry.visual` when explicitly defined.
2. Derived display geometry from semantic Catalog fields where useful.
   - frame: `wheelbase_m`, `dimensions_m`, optional `motor_mount_positions_m`
   - propeller: `diameter_m`, `blade_count`
3. `geometry.inertial` as a presentation proxy.
4. `dimensions_m` or a small generic box as the final fallback.

This keeps the browser asset and MuJoCo preview tied to the same Catalog source data.

## Scope

These are presentation assets, not physical-model truth. The normal `fpv-drone generate` path remains responsible for executable Hakoniwa/MuJoCo vehicle packages.
