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
import subprocess
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
    # The portable package runs the embedded Python, whose ._pth file keeps
    # neither the cwd nor the script directory on sys.path, so `-m rc-custom`
    # (and its sibling `rc_utils` import) would fail there.  Put rc_root on
    # sys.path explicitly and then run the module exactly as `-m` would.
    runner = (
        "import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); "
        "runpy.run_module('rc-custom', run_name='__main__', alter_sys=True)"
    )
    command = [
        sys.executable, "-u", "-c", runner, str(rc_root), args.config_path, args.rc_config_path,
    ]
    if os.name == "nt":
        # Windows exec* starts a new process and exits this one, which the
        # Launcher treats as the asset terminating; keep this process alive.
        return subprocess.call(command)
    os.execv(sys.executable, command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
