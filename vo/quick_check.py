"""Fast gate check for a freshly recorded real sequence.

One command: run the incremental-PnP VO, then validate only the gates that
matter for real hand-pushed footage -- P2 (reproj), P6 (structure) and P7
(static tails). Tuned to min-flow 8 default for rest-only / real sequences.

Usage:
  python quick_check.py --video seq_real_10.avi --meta seq_real_10_meta.json
      [--out-prefix seq_real_10] [--min-flow 8.0] [--gates P2,P6,P7]
Exit 0 = selected gates all PASS, 1 = any FAIL.
"""

import argparse
import os
import subprocess
import sys

VO = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    print(">> %s" % " ".join(cmd))
    return subprocess.run(cmd, cwd=VO).returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--meta", default=None)
    ap.add_argument("--out-prefix", default=None)
    ap.add_argument("--min-flow", type=float, default=8.0,
                    help="flow threshold forwarded to test_incr_pnp.py "
                         "(default 8.0 for real rest-only)")
    ap.add_argument("--gates", default="P2,P6,P7",
                    help="comma-separated subset to validate (default P2,P6,P7)")
    a = ap.parse_args()

    prefix = a.out_prefix or os.path.splitext(a.video)[0] + "_qc"
    traj = prefix + "_traj.csv"

    rc = run([sys.executable, os.path.join(VO, "test_incr_pnp.py"),
              "--video", a.video, "--out", traj,
              "--min-flow", str(a.min_flow)])
    if rc != 0:
        print("test_incr_pnp failed (rc=%d)" % rc)
        return rc

    gate_args = [sys.executable, os.path.join(VO, "validate_traj_pass.py"),
                 "--traj", traj, "--gates", a.gates]
    if a.meta:
        gate_args += ["--meta", a.meta]
    rc = run(gate_args)
    print("\nQUICK CHECK ->", "PASS" if rc == 0 else "FAIL",
          "(%s)" % a.gates)
    return rc


if __name__ == "__main__":
    sys.exit(main())