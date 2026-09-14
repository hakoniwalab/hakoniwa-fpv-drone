# Catalog Showroom

`tools/fpv-catalog.py` turns the FPV component Catalog into a lightweight MuJoCo showroom for demonstrations and visual inspection.

The Catalog YAML remains the source of truth. The showroom does not introduce a second 3D asset catalog, and it is intentionally kept separate from the normal `fpv-drone` vehicle-generation CLI.

## Workflow

The showroom follows a small staged workflow:

```text
prepare -> doctor -> open-viewer
```

### 1. Prepare

Create the showroom-managed Python environment and install this repository plus the optional MuJoCo viewer dependency:

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

Validate the Catalog, generate a showroom MJCF, and load that MJCF with MuJoCo:

```bash
python3 tools/fpv-catalog.py doctor
```

This verifies more than Python imports: the generated showroom must be accepted by `mujoco.MjModel.from_xml_path()`.

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

`doctor` and `open-viewer` automatically delegate to the Python environment created by `prepare`.

## Additional Catalog roots

`doctor` and `open-viewer` accept repeatable `--catalogs` arguments so public and private Catalog roots can be composed without changing the showroom generator:

```bash
python3 tools/fpv-catalog.py open-viewer motor \
  --catalogs catalogs \
  --catalogs /path/to/private-catalogs
```

## Rendering rules

The showroom intentionally uses simple MuJoCo primitives instead of external mesh assets.

Rendering is resolved in this order:

1. Use `geometry.visual` when the Catalog item defines it.
2. Derive a presentation shape from semantic Catalog fields where useful.
   - frames: `wheelbase_m`, `dimensions_m`, and optional `motor_mount_positions_m`
   - propellers: `diameter_m` and `blade_count`
3. Fall back to `geometry.inertial` as a visual proxy.
4. Fall back to `dimensions_m` or a small generic box when no other geometry is available.

This keeps the visualization connected to the same Catalog data used by the physical model generator while avoiding a separate asset-maintenance workflow.

## Scope

This is a presentation and inspection view, not a replacement for the generated vehicle model.

- components are static display objects
- showroom geoms do not participate in contact
- primitive appearance is intentionally approximate unless `geometry.visual` is explicitly provided
- the normal `fpv-drone generate` path remains responsible for the executable Hakoniwa/MuJoCo vehicle package
