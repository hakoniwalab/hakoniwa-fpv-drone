# Verified Master3X Angle configuration

This directory freezes the three files that must remain consistent when reproducing the tuned SpeedyBee Master3X sample aircraft:

- `drone-config/drone.xml`: generated MuJoCo vehicle and FPV course
- `drone-config/drone_config_0.json`: portable Drone runtime configuration
- `drone-config/control-param.txt`: generated controller parameters with the 21 flight-gate-approved Hover/Angle PID values applied

The Vehicle Recipe `recipes/examples/master3x.yaml` is the projection of `recipes/examples/master3x-visual-demo.assembly.json`. Hover and Angle auto-tuning used Hakoniwa Drone PRO with the FPV flight-gate-v5 policy: Hover selected trial_0034, Angle selected trial_0052, and the post-Angle Hover check passed. The generated vehicle files were byte-identical to the tuning input. Auto-tuning requires a valid Hakoniwa Drone PRO license. Tuning profiles, search spaces, trial data, and logs are intentionally excluded.

On 2026-09-25 PS5 Angle-mode lift-off and stable hover were confirmed on Hakoniwa Drone Core v4.1.1. With the generic Catalog PIDs instead, the aircraft lifts off but does not settle into a hover.

The Master3X Recipe and the default World apply this exact set automatically during `configure`:

```bash
python3.12 tools/fpv.py configure --recipe recipes/examples/master3x.yaml --output build/master3x
python3.12 tools/fpv.py start --output build/master3x
```

Use `configure --generated-defaults` only to inspect the untuned generator output.
