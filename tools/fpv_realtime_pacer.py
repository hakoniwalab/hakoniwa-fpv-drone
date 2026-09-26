#!/usr/bin/env python3
"""Hakoniwa asset that keeps simulation time in step with wall-clock time.

The Conductor advances world time only while every asset is less than
max_delay behind it, so an asset whose own time follows the wall clock bounds
world time to wall time + max_delay (+ the Core delta). The drone service can
then run with --real-sleep-msec 0 on every OS.

Deadlock-freedom requires this asset's delta to be at most the Conductor's
max_delay (max_i dT_i <= M).
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    result.add_argument("config_path", help="Hakoniwa asset config declaring no robots or PDUs")
    result.add_argument("--asset-name", default="FpvRealtimePacer")
    result.add_argument("--delta-msec", type=int, default=10)
    result.add_argument(
        "--max-delay-msec", type=int, default=20,
        help="Conductor max_delay; the drone service's built-in Conductor uses 20 ms",
    )
    result.add_argument("--report-sec", type=float, default=5.0)
    return result


def main() -> int:
    args = parser().parse_args()
    if not 0 < args.delta_msec <= args.max_delay_msec:
        print(
            f"ERROR: --delta-msec must be in (0, {args.max_delay_msec}] to avoid a time-guard deadlock",
            file=sys.stderr,
        )
        return 2
    delta_usec = args.delta_msec * 1000

    import hakopy

    def on_manual_timing_control(context) -> int:
        # hakopy discards exceptions raised in callbacks; log them explicitly.
        try:
            return pace()
        except Exception:
            traceback.print_exc()
            sys.stderr.flush()
            return 1

    def pace() -> int:
        print("[pacer] manual timing control started", flush=True)
        start = time.monotonic()
        next_report = start + args.report_sec
        while True:
            now = time.monotonic()
            # Follow elapsed wall time rather than counting sleeps, so coarse
            # OS sleep granularity (notably on Windows) does not slow the run.
            wall_usec = int((now - start) * 1_000_000)
            while hakopy.asset_current_time() + delta_usec <= wall_usec:
                # hakopy.usleep returns True after advancing, False once the
                # simulation stops (not an errno-style 0 on success).
                if not hakopy.usleep(delta_usec):
                    print("[pacer] simulation stopped", flush=True)
                    return 0
            if now >= next_report:
                sim_sec = hakopy.simulation_time() / 1_000_000
                wall_sec = now - start
                print(
                    f"[pacer] wall={wall_sec:.1f}s sim={sim_sec:.1f}s rtf={sim_sec / wall_sec:.3f}",
                    flush=True,
                )
                next_report += args.report_sec
            time.sleep(delta_usec / 1_000_000)

    callbacks = {
        "on_initialize": lambda context: 0,
        "on_simulation_step": None,
        "on_manual_timing_control": on_manual_timing_control,
        "on_reset": lambda context: 0,
    }
    if not hakopy.asset_register(
        args.asset_name, args.config_path, callbacks, delta_usec, hakopy.HAKO_ASSET_MODEL_CONTROLLER
    ):
        print("ERROR: hakopy.asset_register() failed", file=sys.stderr)
        return 1
    print(f"[pacer] registered {args.asset_name}: delta={args.delta_msec} ms", flush=True)
    result = hakopy.start()
    print(f"[pacer] finished: hakopy.start() returned {result}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
