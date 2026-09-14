# Assembly Interface Specification v1

This specification defines the composition boundary used by a future FPV Drone
Composer. It deliberately does not change the existing Vehicle Recipe,
physics resolver, or Drone PRO generated-artifact contract.

```text
Interface definition
  -> Interface variant
  -> Component port instance
  -> Interface-level connection rule
  -> Assembly graph / Vehicle Recipe projection
```

The Catalog remains the source of truth. A browser consumes generated Composer
data; it must not independently decide physical compatibility or recreate
physics calculations.

## 1. Interface definition

An interface definition is a reusable type contract. It declares its domain,
the allowed roles, and named parameter definitions. It does not identify a
specific product or mounting position.

Examples: `motor-mount`, `propeller-shaft`, `battery-mount`, and
`camera-mount`.

```yaml
schema_version: 1
kind: assembly-interface-definition
items:
  - id: motor-mount
    name: Motor mounting face
    description: Mechanical bolted interface between a frame and a motor.
    domain: mechanical
    roles: [provider, consumer]
    parameters:
      - id: bolt_pattern_mm
        schema: {type: array, minItems: 2, maxItems: 2, items: {type: number}}
      - id: bolt_diameter_mm
        schema: {type: number, exclusiveMinimum: 0}
```

## 2. Interface variant

An interface variant instantiates one interface definition with concrete,
reusable values. For example, a `16x16 mm, M2` motor mount is a variant of
`motor-mount`; it is not a Frame- or Motor-specific declaration.

```yaml
schema_version: 1
kind: assembly-interface-variant
items:
  - id: fpv.motor-mount.16x16-m2
    name: FPV 16x16 M2 motor mount
    description: Four-hole 16x16 mm motor mount using M2 fasteners.
    interface: motor-mount
    parameters:
      bolt_pattern_mm: [16, 16]
      bolt_diameter_mm: 2
    evidence_status: declared
```

`evidence_status` prevents a generic example or missing manufacturer data from
being represented as verified compatibility.

## 3. Component port instance

Every Catalog item emitted as a Composer part declares one or more
`assembly_ports`. A port instance maps one concrete position on that component
to one interface variant. A non-assemblable or virtual entry is not a Composer
part and must not be emitted as a draggable component.

```yaml
assembly_ports:
  - id: motor_mount_1
    role: provider
    interface: fpv.motor-mount.16x16-m2
    pose:
      position_m: [0.08, -0.08, 0.02]
      rpy_deg: [0, 0, 0]
    capacity: 1
```

`pose` is always in the component-local FLU coordinate system: +X forward,
+Y left, +Z up; length is metre and RPY is degree. It is a port coordinate,
not a world coordinate. A consumer port also has a local pose, usually its
mounting origin. A port may be occupied at most `capacity` times.

The component Catalog schema references `schemas/assembly-port.schema.json`.
The shipped generic Catalog has been migrated to this representation.

When a connection is resolved, the component pose is calculated as a rigid
transform, not by adding position or RPY values:

```text
T_component = T_provider_port × T_adjustment × inverse(T_consumer_port)
```

This keeps a non-zero or rotated consumer port correct for both browser display
and Recipe projection.

## 4. Connection rules

A connection rule is defined between a provider interface variant and a
consumer interface variant, never by component ID. A rule returns the initial
snap relation and the degrees of freedom that the Composer may expose.

```yaml
schema_version: 1
kind: assembly-connection-rule
items:
  - id: fpv.motor-mount.16x16-m2.to.fpv.motor-mount.16x16-m2
    provider_interface: fpv.motor-mount.16x16-m2
    consumer_interface: fpv.motor-mount.16x16-m2
    status: compatible
    adjustment:
      translation_axes: []
      rotation_axes: []
```

For a battery tray, a rule can allow `[x, y, z]` and `yaw`, with limits. The
Composer displays translation in centimetres but stores and exports metres.
It displays and stores RPY in degrees.

`compatible` means the variant data supports the match. `incompatible` means
the declared data conflicts. `unknown` means that the data is insufficient;
the UI may show a warning but must not claim that the connection is sound.

## 5. What rules do not decide

Local port compatibility is not whole-vehicle validation. The Assembly Resolver
separately verifies constraints such as motor/propeller count, occupied-port
cardinality, frame mount count, rotor order/direction, collision warnings, and
electrical compatibility. The existing Vehicle Recipe and Python Generator
remain authoritative for generated mass properties, thrust, MuJoCo, and Drone
PRO configuration.

Each motor node also owns an explicit `rotor` assignment: `index`, `name`, and
`rotation_direction`. This is an Assembly Graph property, rather than an
inference from port names, so `quad_x` and variable-count `multirotor` graphs
share the same deterministic Drone PRO rotor-layout projection.

## v1 boundary

The shipped generic Catalogs use the `hakoniwa.generic.*` variants. They define
the connection graph required by the simulation Composer, but deliberately make
no statement about real bolt patterns, shaft diameters, fastening, electrical
ratings, or airworthiness. Every supplied connection rule is marked
`scope: simulation_only` for that reason.

v1 includes a typed Assembly Graph loader and deterministic projection to the
existing Recipe v2 shape. It does not modify Recipe schema versions or expose a
browser UI. The graph is a Composer-side input; the existing Vehicle Recipe and
Generator remain the source of executable vehicle artifacts.

## Reference assembly projection

`recipes/examples/utility-quad-with-skid.assembly.yaml` is the reference
complete assembly graph. Its node and connection structure is validated, then
projected into the existing schema v2 Vehicle Recipe. The regular resolver and
Generator produce the final `drone.xml` and `drone_config.json`; the assembly
layer does not render MJCF itself.

The graph contract is published as
[`schemas/assembly-graph.schema.json`](../schemas/assembly-graph.schema.json).
