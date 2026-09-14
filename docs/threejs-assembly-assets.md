# Assembly Graph to Three.js assets

`tools/fpv-threejs-assets.py` materializes the visual half of a resolved FPV
Assembly Graph for `hakoniwa-threejs-drone`.  It deliberately does not generate
MuJoCo, calculate physics, or run Drone PRO.

```bash
python3 tools/fpv-threejs-assets.py \
  recipes/examples/master3x-visual-demo.assembly.json \
  --output-dir build/master3x/threejs-assets
```

The output is self-contained:

```text
threejs-assets/
├── body.glb          # Frame, motors, battery, controller and fixed accessories
├── propeller.glb     # One source propeller model; the viewer instantiates it per rotor
├── camera.glb        # Camera housing model, separate from the body
├── drone-types.json  # hakoniwa-threejs-drone type configuration
└── manifest.json
```

The tool resolves every node from the one frame root using the Assembly
contract's rigid transform:

```text
T_child = T_parent × T_provider_port × T_adjustment × inverse(T_consumer_port)
```

`drone-types.json` uses the resolved propeller poses, explicit rotor names and
`rotation_direction` values.  Therefore the existing viewer can instantiate
four propeller GLBs and spin them from Drone PRO PWM without reimplementing
Catalog compatibility or Assembly rules in JavaScript.  Its coordinate system
is Catalog FLU metres/degrees, which is also the viewer's ROS FLU input frame.
The GLB mesh vertices themselves are converted to the viewer's Three.js
right/up/back basis during export; this is why a Catalog-horizontal propeller
is horizontal in the browser and rotates around the viewer's vertical axis.

The camera entry initially has the resolved Catalog camera pose and Catalog FOV
so its visible housing is correct.  At runtime, the eventual `fpv.py --threejs`
adapter must take the attached render camera's final pose and FOV from generated
MuJoCo `camera name="fpv"`; MuJoCo remains the source of truth for simulation
viewpoint parameters.

Current constraints are intentional: there must be exactly one frame and
camera, every motor must have exactly one propeller, motor indices must be
contiguous from one, and all propellers must use one Catalog product.  This is
the common PWM-driven multirotor contract.  Supporting mixed propeller models
requires an explicit multi-asset viewer contract rather than silently choosing
one model.

## Run it with Drone PRO and the Three.js viewer

The normal runtime tool can generate these assets into its runtime directory
and point the existing `hakoniwa-threejs-drone` viewer at them:

```bash
python3.12 tools/fpv.py configure --threejs \
  --assembly recipes/examples/master3x-visual-demo.assembly.json
python3.12 tools/fpv.py start
python3.12 tools/fpv.py open-viewer
```

`configure` projects the Assembly Graph into a generated Recipe before calling
the existing Python Generator.  It then writes the three GLBs and a
`drone-types.json` under `build/<name>/runtime/threejs/assets/`.  The viewer
keeps consuming the existing `DroneVisualStateArray`, including per-rotor PWM,
so only visual assets are changed.  A user-provided `--assembly` intentionally
requires `--threejs`; without it, use the normal Recipe-only runtime path.
