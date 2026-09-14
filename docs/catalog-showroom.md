# Catalog Showroom

`tools/fpv-catalog.py` turns the FPV component Catalog into a lightweight MuJoCo showroom for demonstrations and visual inspection.

The Catalog YAML remains the source of truth. The showroom does not introduce a second 3D asset catalog, and it is intentionally kept separate from the normal `fpv-drone` vehicle-generation CLI.

## Workflow

The showroom follows a small staged workflow:

```text
prepare -> doctor -> open-viewer
                  -> export-glb
```

### 1. Prepare

Create the showroom-managed Python environment and install this repository plus the optional MuJoCo viewer and GLB export dependencies:

```bash
python3 tools/fpv-catalog.py prepare
```

The default managed environment is created under:

```text
build/catalog-showroom/.venv
```

`prepare` installs the repository in editable mode with the `showroom` optional dependency. It does not install into the global Python environment.

To rebuild the managed environment from scratch:

```bash
python3 tools/fpv-catalog.py prepare --recreate
```

### 2. Doctor

Validate the Catalog, generate a showroom MJCF, load that MJCF with MuJoCo, export all Catalog GLBs, and load one exported GLB back through trimesh:

```bash
python3 tools/fpv-catalog.py doctor
```

This verifies more than Python imports: both the MuJoCo showroom and the browser asset path must be structurally usable.

### 3. Open Viewer

Show all catalog components:

```bash
python3 tools/fpv-catalog.py open-viewer
```

Show one component kind:

```bash
python3 tools/fpv-catalog.py open-viewer motor
python3 tools/fpv-catalog.py open-viewer propeller
python3 tools/fpv-catalog.py open-viewer battery
```

Show one catalog item:

```bash
python3 tools/fpv-catalog.py open-viewer motor generic_2207_1850kv
```

Choose an output path:

```bash
python3 tools/fpv-catalog.py open-viewer motor \
  --output build/showroom-motors.xml
```

The default output is:

```text
build/catalog-showroom/catalog-showroom.xml
```

### 4. Export GLB

Export every Catalog component as an individual browser-ready GLB asset:

```bash
python3 tools/fpv-catalog.py export-glb
```

Show the same selection granularity as `open-viewer`:

```bash
python3 tools/fpv-catalog.py export-glb motor
python3 tools/fpv-catalog.py export-glb motor generic_2207_1850kv
```

The default output is:

```text
build/catalog-showroom/glb/
├── manifest.json
├── frame/generic_5inch_x.glb
├── motor/generic_2207_1850kv.glb
├── propeller/generic_5inch_3blade.glb
└── ...
```

Choose another destination with:

```bash
python3 tools/fpv-catalog.py export-glb \
  --output-dir build/browser-assets
```

`manifest.json` is intended as the browser-side Catalog index. Each item records the Catalog kind/id/name, description, relative GLB path, selected engineering specs, metadata, and generated bounds/extents.

The GLB contains only the component in its Catalog-local frame. Showroom floor and pedestal geometry are not exported, so a browser composer can position the part freely.

`doctor`, `open-viewer`, and `export-glb` automatically delegate to the Python environment created by `prepare`.

## Additional Catalog roots

`doctor`, `open-viewer`, and `export-glb` accept repeatable `--catalogs` arguments so public and private Catalog roots can be composed without changing the showroom or GLB exporter:

```bash
python3 tools/fpv-catalog.py export-glb motor \
  --catalogs catalogs \
  --catalogs /path/to/private-catalogs
```

## Rendering rules

The MuJoCo showroom and GLB exporter intentionally share the same display-geometry resolution instead of maintaining separate model definitions.

Rendering is resolved in this order:

1. Use `geometry.visual` when the Catalog item defines it.
2. Derive a presentation shape from semantic Catalog fields where useful.
   - frames: `wheelbase_m`, `dimensions_m`, and optional `motor_mount_positions_m`
   - propellers: `diameter_m` and `blade_count`
3. Fall back to `geometry.inertial` as a visual proxy.
4. Fall back to `dimensions_m` or a small generic box when no other geometry is available.

This keeps MuJoCo preview and browser GLB assets connected to the same Catalog data used by the physical model generator while avoiding a separate asset-maintenance workflow.

## Scope

This is a presentation and inspection/export layer, not a replacement for the generated vehicle model.

- showroom components are static display objects
- showroom geoms do not participate in contact
- GLB assets are presentation geometry, not collision/inertial truth
- primitive appearance is intentionally approximate unless `geometry.visual` is explicitly provided
- the normal `fpv-drone generate` path remains responsible for the executable Hakoniwa/MuJoCo vehicle package
