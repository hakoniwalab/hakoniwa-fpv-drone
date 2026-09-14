# Browser Composer MVP

The Browser Composer lives in this repository because it edits the FPV Catalog
selection and Assembly Graph owned here. It is separate from
`hakoniwa-threejs-drone`, which remains the PDU-driven runtime viewer.

## Start

Generate Catalog GLB assets and their assembly contract first:

```bash
python3 tools/fpv-catalog.py prepare
python3 tools/fpv-catalog.py export-glb
python3 tools/fpv-composer.py --open
```

The Composer loads these generated files; they are not source artifacts:

```text
build/catalog-showroom/glb/
├── manifest.json
├── assembly-contract.json
└── <kind>/<part>.glb
```

`fpv-composer.py` serves the repository root at `http://127.0.0.1:8010/` so
the Composer can load both its static files and generated Catalog assets. Stop
it with `Ctrl-C`. Use `--port <number>` when port 8010 is unavailable.

## Manual smoke check

1. Add one Frame, then add four Motors and four Propellers.
2. Add one Battery, Camera, and Controller. Click a cyan port before a drop to
   select a preferred compatible target.
3. Select a mounted Battery or Camera and change its local pose in the right
   panel. Position inputs are centimetres; RPY inputs are degrees.
4. Export the Assembly Graph, reload the page, then import the exported JSON.
5. Confirm that an incompatible or fully occupied port cannot accept another
   component and that singleton parts replace their preceding selection.

## Data flow and boundary

```text
Catalog YAML + assembly-interfaces
  -> fpv-catalog.py export-glb
  -> visual manifest + assembly contract + GLB
  -> Browser Composer edits Assembly Graph
  -> Python Assembly Resolver projects Vehicle Recipe
  -> existing Generator emits MJCF / Drone PRO artifacts
```

The browser renders GLB assets, applies already-declared connection rules, and
stores an Assembly Graph. It does not calculate mass, inertia, thrust, physical
compatibility, MJCF, or Drone PRO configuration.

## MVP scope

- drag a Catalog part to the central Composer, or click its Catalog card;
- click a cyan provider port to make it the preferred connection target;
- snap only to a compatible, unoccupied port declared in `assembly-contract.json`;
- replacing Battery, Camera, Controller, or Landing Gear removes the previous
  singleton node and its connection before adding the replacement;
- edit connection-relative position in centimetres and RPY in degrees;
- save a local draft, import a graph, and export graph JSON.

The current MVP creates a `quad_x` draft and assigns a display-oriented rotor
sequence to newly added motors. A production Composer should obtain vehicle
profile and rotor-assignment policy from a generated Assembly Contract rather
than introduce new compatibility or control policy in JavaScript.
