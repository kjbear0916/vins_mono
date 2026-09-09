"""One-shot pipeline: VO test -> validation gate -> validation figure.

Usage:
  python run_clean_seq_check.py --video vi/seq_clean_01.avi
      [--out-prefix vo/seq_clean_01]
      [--meta vo/seq_clean_01_meta.json]
      [--skip-gate]   plot even when the gate FAILs

Steps wrapped (subprocess, so exit codes propagate):
  1. test_incr_pnp.py --video <video> --out <prefix>_traj.csv
  2. validate_traj_pass.py --traj <prefix>_traj.csv --meta <meta>
  3. plot_validate_trajectory.py --traj <prefix>_traj.csv
       --out <prefix>_validation.png

Exit code 0 only if validation passed (or --skip-gate).
"""

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VO = r"D:\Things\vo"


def run(cmd):
    print("\n>> %s" % " ".join(cmd))
    r = subprocess.run(cmd, cwd=HERE)
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out-prefix", required=True)
    ap.add_argument("--meta", default=None)
    ap.add_argument("--skip-gate", action="store_true")
    ap.add_argument("--min-flow", type=float, default=12.0,
                    help="forwarded to test_incr_pnp.py (default 12.0)")
    a = ap.parse_args()

    traj = a.out_prefix + "_traj.csv"

    rc = run([sys.executable, os.path.join(VO, "test_incr_pnp.py"),
              "--video", a.video, "--out", traj,
              "--min-flow", str(a.min_flow)])
    if rc != 0:
        print("test_incr_pnp failed (rc=%d)" % rc)
        return rc

    gate_args = [sys.executable, os.path.join(VO, "validate_traj_pass.py"),
                 "--traj", traj]
    if a.meta:
        gate_args += ["--meta", a.meta]
    if not a.skip_gate:
        rc = run(gate_args)
        if rc != 0:
            print("VALIDATION FAILED -- plot anyway & inspect")
        else:
            print("VALIDATION PASSED")

    run([sys.executable, os.path.join(VO, "plot_validate_trajectory.py"),
         "--traj", traj,
         "--out", a.out_prefix + "_validation.png",
         "--title", os.path.basename(a.video)])

    print("\nvalidation figure:", a.out_prefix + "_validation.png")
    return rc


if __name__ == "__main__":
    sys.exit(main())