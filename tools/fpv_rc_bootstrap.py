#!/usr/bin/env python3
"""Initialize the RC PDU, then hand control to Drone PRO's stock RC client.

This adapter belongs to the FPV package.  Drone PRO's rc-custom client expects
GameControllerOperation to have already been materialized in shared memory;
the FPV launcher can otherwise race its first gamepad button event against
that initialization.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Bootstrap FPV RC PDU")
    result.add_argument("config_path")
    result.add_argument("rc_config_path")
    result.add_argument("--rc-root", required=True, type=Path)
    result.add_argument("--timeout-sec", default=10.0, type=float)
    return result


def main() -> int:
    args = parser().parse_args()

    from hakoniwa_pdu.apps.drone.hakosim import MultirotorClient
    from hakoniwa_pdu.pdu_msgs.hako_msgs.pdu_pytype_GameControllerOperation import (
        GameControllerOperation,
    )

    client = MultirotorClient(args.config_path)
    client.default_drone_name = "Drone"
    client.confirmConnection()

    neutral = GameControllerOperation()
    neutral.axis = [0.0] * 6
    neutral.button = [False] * 15

    deadline = time.monotonic() + args.timeout_sec
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            client.run_nowait()
            client.putGameJoystickData(neutral)
            client.run_nowait()
            state = client.getGameJoystickData()
            if len(list(state.axis)) >= 6 and len(list(state.button)) >= 15:
                print("FPV RC PDU initialized with neutral input.", flush=True)
                break
        except Exception as error:  # PDU may not exist during the first ticks.
            last_error = error
        time.sleep(0.02)
    else:
        detail = f": {last_error}" if last_error else ""
        print(f"ERROR: FPV RC PDU initialization timed out{detail}", file=sys.stderr)
        return 1

    rc_root = args.rc_root.resolve()
    if not (rc_root / "rc-custom.py").is_file():
        print(f"ERROR: Drone PRO RC client not found: {rc_root}", file=sys.stderr)
        return 1

    os.chdir(rc_root)
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-u",
            "-m",
            "rc-custom",
            args.config_path,
            args.rc_config_path,
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
