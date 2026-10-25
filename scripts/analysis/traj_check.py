#!/usr/bin/env python3
"""Empirical clock-jump check for specific trials: are the GT and VINS
trajectory timestamps monotonic and does their span match the expected
record duration? Bags were cleaned after successful trials, so this is the
persistent evidence available (trajectories + per-trial logs).

Usage: traj_check.py <tree> <tid> [<tid> ...]   (tree like /data/results_rerun54)
Expected record duration: 95 s at 0.5 m/s, 85 s at 1.5/3.0 m/s.
"""
import os
import sys


def check(path):
    ts = []
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            ts.append(float(parts[0]))
        except ValueError:
            continue
    if len(ts) < 10:
        return len(ts), 0, 0, 0.0, 0.0, 0.0, "too_few_rows"
    n_equal = sum(1 for i in range(1, len(ts)) if ts[i] == ts[i - 1])
    back = [ts[i - 1] - ts[i] for i in range(1, len(ts)) if ts[i] < ts[i - 1]]
    span = ts[-1] - ts[0]
    return len(ts), len(back), n_equal, (max(back) if back else 0.0), span, ts[0], ts[-1]


def main():
    tree = sys.argv[1]
    tids = sys.argv[2:]
    for tid in tids:
        d = os.path.join(tree, "trial_%s" % tid, "trajectories")
        exp = 95 if "_0.5ms_" in tid else 85
        print("=== %s (expected sim span ~%ds) ===" % (tid, exp))
        for label, fn in (("gt", tid + "_gt.tum"), ("vins", tid + "_vins.txt")):
            p = os.path.join(d, fn)
            if not os.path.isfile(p):
                print("  %s: MISSING (%s)" % (label, p))
                continue
            n, nb, ne, maxb, span, t0, t1 = check(p)
            ok = nb == 0 and 0.5 <= span / exp <= 1.5
            print("  %s: rows=%d back_steps=%d equal=%d max_back=%.3fs span=%.1fs [%.1f,%.1f] %s" % (
                label, n, nb, ne, maxb, span, t0, t1, "PASS" if ok else "FAIL"))


if __name__ == "__main__":
    main()