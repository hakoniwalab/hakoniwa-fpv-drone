# Commercial FPV Catalog data

For the required photos, dimensions, mounting information and visual acceptance
criteria, see [外観再現の入力要件](catalog-visual-input-requirements.md).

## Master3X visual model

Master3X, the SpeedyBee 1507 motor and HQProp T3.5X2.5X3 use explicit
`geometry.visual` from their product YAML. These are photo-informed approximations,
not manufacturer CAD: layered plates, standoffs, yellow frame fittings, vented
motor bells and three rounded blades. The reference accessories are listed at
https://www.speedybee.com/accessories-for-speedybee-master-3x/ .
The frame deck and side rails have open slots. Camera, transmitter and antennas
are grouped into the removable `master3x_demo_camera_head` demo component.
`generic_4s_850mah` adds a top-mounted battery with straps and a power lead.
Both are illustrative, unbranded simulation parts; their mass, dimensions and
electrical/optical values are estimates, not identified commercial specifications.
The battery's consumer port is on its underside so the resolver places it above
the frame deck without a browser-only positioning offset.

Import `recipes/examples/master3x-visual-demo.assembly.json` in Composer to view
the assembled example, or select these parts at the camera and battery ports.
The example includes the Hakoniwa controller. It does not reproduce exact
manufacturer CAD or validate the flight characteristics of the commercial drone.

Visual ellipsoids use full `dimensions_m`, just like boxes. GLB and MuJoCo
both consume these definitions; collision and inertial proxies remain separate.
After changing product geometry, run `python3 tools/fpv-catalog.py export-glb`
and reload Composer to replace previously generated assets.

The Catalog may contain real commercial parts, but a product page rarely publishes every value needed by a physics simulator. Commercial entries therefore keep provenance in `metadata.value_origin` and never present an estimated simulation value as a manufacturer specification.

Commercial products use the Source / Product boundary documented in [catalog-source-product-boundary.md](catalog-source-product-boundary.md):

- `catalogs/sources/**` records external manufacturer product/manual URLs;
- `catalogs/products/**` stores one normalized digital product per file;
- every commercial product fragment has a mandatory `source_ref` back to its source file.

The first reference build is `recipes/examples/speedybee-master5-commercial.assembly.yaml` and combines:

- SpeedyBee Master 5 V2 Frame
- iFlight XING2 2207 1855KV motors
- HQProp 5X4.3X3V2S propellers
- Tattu R-Line V5 1200mAh 6S battery
- RunCam Phoenix 2 camera
- Hakoniwa initial controller profile

## Provenance convention

Typical origins are:

- `manufacturer`: published by the product manufacturer;
- `derived_*`: calculated from a published value, for example `Kt = 60 / (2*pi*Kv)`;
- `estimated_*`: a simulation value not published for the product;
- `simulation_assumption`: an explicit model assumption.

The product fragment's `source_ref` identifies the external evidence record. Source URLs are evidence for published product values only; estimated dynamics remain Hakoniwa simulation data.

## First dimensional Assembly Interface variants

This reference build also exercises concrete interface variants instead of generic simulation-only interfaces:

- `fpv.motor-mount.16x16`: 16 x 16 mm motor mounting pattern;
- `fpv.propeller-shaft.5mm`: 5 mm motor shaft / propeller bore;
- `fpv.camera-mount.19mm-m2`: 19 mm camera body with nominal M2 side mounting.

The corresponding connection rules express local mechanical compatibility. They do not claim complete aircraft compatibility, electrical compatibility, airworthiness, or validated flight performance.

## Important modeling boundary

Several values are intentionally approximate in this first commercial build:

- the frame `dimensions_m` is a conservative simulation envelope derived from the published wheelbase because a complete manufacturer-local frame envelope is not published in the product specification;
- frame port positions are derived/estimated from the published True-X wheelbase and mounting capabilities;
- XING2 `rotor_inertia_kg_m2` is an estimate based on the existing generic 2207 model;
- XING2 `resistance_ohm` currently maps the published 50 mOhm interphase resistance into the model field and is tagged accordingly;
- HQProp thrust and torque coefficients reuse the generic 5-inch initial estimate until bench data or a fitted thrust curve is available.

These distinctions are deliberate. The Catalog is intended to make evidence and assumptions visible so later measurements can replace estimates without changing the Assembly Graph.
