#!/usr/bin/env python3
"""rerun_pair.py — same-session two-arm comparison on the 2 suspect cells.

Cells flagged in the imu161 (#12) analysis:
  - high/0.5/circle     (imu161 r2 ATE 1.30 m bump vs ~0.21/0.36 at 50 Hz)
  - medium/3.0/figure8  (imu161 r3 Sim3 scale 0.9472 out of the [0.96,1.03] gate)

Each cell x 3 reps runs on BOTH arms in the same session, rep-major with arms
interleaved per rep, so host load / clock drift hit both arms equally:
  arm 50Hz   -> RUN_TAG=ctl50   IMU_HZ=50   /data/results_ctl50
  arm ~125Hz -> RUN_TAG=imu161r IMU_HZ=200  /data/results_imu161r

Each trial spawns batch_run_54.py single-cell (filter args) so every trial gets
a pristine env plus the full summary / metrics / timeout / cleanup machinery.
"""

import os
import subprocess
import sys
import time

REPO = "/root/catkin_ws/src/vins_research"
CELLS = [("high", "0.5", "circle"), ("medium", "3.0", "figure8")]
ARMS = [
    ("200", "imu161r", "/data/results_imu161r"),   # noted first: the arm under test
    ("50", "ctl50", "/data/results_ctl50"),
]


def main():
    order = []
    for rep in (1, 2, 3):
        for (hz, tag, outdir) in ARMS:
            for (l, s, t) in CELLS:
                order.append((l, s, t, rep, hz, tag, outdir))

    print(f"rerun_pair: {len(order)} trials "
          f"(2 cells x 3 reps x {len(ARMS)} arms), rep-major arms-interleaved")

    for idx, (l, s, t, r, hz, tag, outdir) in enumerate(order, 1):
        os.makedirs(outdir, exist_ok=True)
        env = dict(os.environ)
        env["VINS_RESULTS_DIR"] = outdir
        env["VINS_SUMMARY_CSV"] = os.path.join(outdir, "summary_54.csv")
        env["RUN_TAG"] = tag
        env["IMU_HZ"] = hz
        cmd = [sys.executable, os.path.join(REPO, "scripts/ops/batch_run_54.py"),
               "--light", l, "--speed", s, "--traj", t,
               "--repeat", str(r), "--cleanup"]
        print(f"\n>>> [{idx}/{len(order)}] {l}/{s}/{t}/r{r} arm={tag}({hz}Hz) -> {outdir}")
        sys.stdout.flush()
        subprocess.run(cmd, env=env, cwd=REPO)
        time.sleep(3)

    print("\nrerun_pair complete.")


if __name__ == "__main__":
    main()