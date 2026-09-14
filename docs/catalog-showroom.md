# Catalog Showroom

`catalog-view` turns the FPV component Catalog into a lightweight MuJoCo showroom for demonstrations and visual inspection.

The Catalog YAML remains the source of truth. The showroom does not introduce a second 3D asset catalog.

## Usage

Show all catalog components:

```bash
fpv-drone catalog-view
```

Show one component kind:

```bash
fpv-drone catalog-view motor
fpv-drone catalog-view propeller
fpv-drone catalog-view battery
```

Show one catalog item:

```bash
fpv-drone catalog-view motor generic_2207_1850kv
```

Generate the MJCF without launching MuJoCo Viewer:

```bash
fpv-drone catalog-view --no-open
```

Choose an output path:

```bash
fpv-drone catalog-view motor \
  --output build/showroom-motors.xml \
  --no-open
```

The default output is:

```text
build/catalog-showroom.xml
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
- the normal `generate` command remains responsible for the executable Hakoniwa/MuJoCo vehicle package

MuJoCo's Python package is required only when opening the viewer. `--no-open` can be used in CI or on systems without a GUI.
