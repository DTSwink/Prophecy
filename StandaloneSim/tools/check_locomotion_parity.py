from __future__ import annotations

import argparse
import csv
import io
import math
import subprocess
import sys
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare the native root mover to its Python source.")
    parser.add_argument("--stepper-root", type=Path, required=True)
    parser.add_argument("--trace-exe", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sys.path.insert(0, str(args.stepper_root.resolve()))
    from training.slashes2 import build_walk_mover_viewer as mover

    output = subprocess.check_output([str(args.trace_exe.resolve())], text=True)
    rows = list(csv.DictReader(io.StringIO(output)))
    samples: dict[str, list[object]] = {}
    state_position = np.zeros((2,), dtype=np.float64)
    state_velocity = np.zeros((2,), dtype=np.float64)
    previous_yaw = 0.0
    current_yaw = 0.0
    dt = 1.0 / 30.0
    max_error = {name: 0.0 for name in ("position", "velocity", "yaw")}
    response_mismatches: list[str] = []

    for row in rows:
        mode = row["mode"]
        config = mover.apply_mode_config(mode)
        if mode not in samples:
            samples[mode] = mover.load_speed_samples(config["omni_dir"], config.get("speed_sample_tokens"))
        local_direction = float(row["direction"])
        amplitude = float(row["amplitude"])
        target_yaw = float(row["target_yaw"])
        speed = mover.circular_lerp_speed(samples[mode], local_direction) * amplitude
        target_velocity = mover.direction_from_angle(current_yaw + local_direction) * speed
        preferred_yaw_delta = mover.signed_angle_delta(current_yaw, target_yaw)
        state_velocity, new_yaw, response = mover.step_mover_velocity_yaw(
            state_velocity,
            current_yaw,
            previous_yaw,
            target_velocity,
            target_yaw,
            preferred_yaw_delta,
            dt,
            True,
            True,
        )
        state_position = state_position + state_velocity * dt
        previous_yaw, current_yaw = current_yaw, new_yaw

        native_position = np.asarray([float(row["pos_x"]), float(row["pos_z"])])
        native_velocity = np.asarray([float(row["vel_x"]), float(row["vel_z"])])
        max_error["position"] = max(max_error["position"], float(np.max(np.abs(native_position - state_position))))
        max_error["velocity"] = max(max_error["velocity"], float(np.max(np.abs(native_velocity - state_velocity))))
        max_error["yaw"] = max(max_error["yaw"], abs(float(row["yaw"]) - current_yaw))
        if row["response"] != response:
            response_mismatches.append(f"frame {row['frame']}: C++={row['response']} Python={response}")

    print(
        "frames={} max_position_error={:.12g} max_velocity_error={:.12g} "
        "max_yaw_error={:.12g} response_mismatches={}".format(
            len(rows), max_error["position"], max_error["velocity"], max_error["yaw"], len(response_mismatches)
        )
    )
    if response_mismatches:
        print("\n".join(response_mismatches[:12]))
    tolerance = 2.0e-6
    if any(error > tolerance for error in max_error.values()) or response_mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
