# Verified example 5-inch Angle configuration

This directory freezes the three files that must remain consistent when reproducing the reviewed sample aircraft:

- `drone-config/drone.xml`: generated MuJoCo vehicle and FPV course
- `drone-config/drone_config_0.json`: portable Drone PRO runtime configuration
- `drone-config/control-param.txt`: reviewed controller parameters, including the 55 degree Roll/Pitch Angle limit

The configuration was regenerated and reviewed on 2026-08-29. Hover and Angle auto-tuning completed with all reported hard gates passing, followed by PS5 Angle-mode flight confirmation. Auto-tuning requires a valid Hakoniwa Drone PRO license. Drone PRO tuning profiles, search spaces, trial data, and logs are intentionally excluded.

The default Recipe and World apply this exact set automatically during `configure`:

```bash
python3.12 tools/fpv.py configure
python3.12 tools/fpv.py start
```

Use `configure --generated-defaults` only to inspect the untuned generator output. `restore-verified-config` remains available as an explicit maintenance command. The tracked `modelPath` is relative for portability; application rewrites it to the selected runtime directory.
