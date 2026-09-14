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

The Composer vendors the exact Three.js release it uses (`0.169.0`) under
`composer/vendor/three/`. It therefore needs no CDN or Internet connection
after the repository has been checked out.

## Manual smoke check

1. Select one Frame from the initial Catalog candidates.
2. Select a Frame provider port in the right panel. Confirm that the left
   panel lists only compatible parts, each with its GLB preview.
3. Add four Motors and four Propellers by selecting each relevant provider
   port, then clicking a compatible part card. Add one Battery, Camera, and
   Controller in the same way.
4. Select a mounted Battery or Camera and change its local pose in the right
   panel. Position inputs are centimetres; RPY inputs are degrees. Confirm
   that the fixed Motor mount fields are disabled, and adjustable fields stay
   within the limits declared by the connection rule.
5. Export the Assembly Graph, reload the page, then import the exported JSON.
6. Confirm that an incompatible port cannot accept another component, that a
   full port requests replacement confirmation, and that singleton parts
   replace their preceding selection.
7. Confirm that the right-side Assembly Parts list follows the current graph;
   delete a part from it and confirm that dependent parts are also removed.

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

- select a Frame as the first part, then select a provider port as the
  connection target;
- show only Catalog cards compatible with that port, with a GLB preview;
- click a Catalog card to snap it to the selected port;
- snap only to a compatible port declared in `assembly-contract.json`, with a
  confirmation before replacing a full port;
- replacing Battery, Camera, Controller, or Landing Gear removes the previous
  singleton node and its connection before adding the replacement;
- edit only the connection-relative axes permitted by the contract, in
  centimetres and degrees; the declared symmetric limits are enforced by the
  inputs;
- inspect the current Assembly as a parts list, select an item from it, and
  remove an item (including any parts connected beneath it);
- save a local draft, import a graph, and export graph JSON.

The current MVP creates a `quad_x` draft and assigns a display-oriented rotor
sequence to newly added motors. A production Composer should obtain vehicle
profile and rotor-assignment policy from a generated Assembly Contract rather
than introduce new compatibility or control policy in JavaScript.
