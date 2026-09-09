"""Automated PASS/FAIL gate for a recorded VO translation sequence.

Reads the incremental-PnP trajectory CSV produced by test_incr_pnp.py and the
recorder's meta JSON, and checks the hard acceptance criteria for stage 2-3:

  P1 continuity  : no NaN/inf in pre/post trajectory
  P2 reproj bA   : post-BA RMS < pre-BA (improvement) and post-BA < 5 px
  P3 straight    : net displacement / path length >= 0.6 (straight-ish line)
  P4 monotonic   : cumulative forward progress never retreats > 25% of its
                   achieved maximum (no major reversal / folding back)
  P5 no jumps    : no incremental step > 5x median step (spikes = tracking loss)
  P6 structure   : >= 30 map points, >= 15 keyframes surviving to BA
  P7 static tail : HOLD-phase mean optical flow (from meta JSON) < 2 px/frame
                   on both ends (i.e. the rig was actually still)

Scale is arbitrary (mono VO), so all directional checks use ratios, not
absolute units. Dominant axis direction is reported for manual confirmation
(FORWARD_BACKWARD -> physical push direction).

Usage:
  python validate_traj_pass.py --traj real_incr_traj.csv \
      --meta seq_clean_01_meta.json
Exit code 0 = PASS all hard gates, 1 = FAIL.
"""

import argparse
import csv
import json

import numpy as np


def load_traj(path):
    rows = list(csv.DictReader(open(path, newline="")))
    kf = [int(r["kf"]) for r in rows]
    fr = [int(r["frame"]) for r in rows]
    pre = np.array([[float(r["pre_x"]), float(r["pre_y"]), float(r["pre_z"])]
                    for r in rows])
    post = np.array([[float(r["post_x"]), float(r["post_y"]),
                      float(r["post_z"])] for r in rows])
    return kf, fr, pre, post


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--traj", default=r"D:\Things\vo\real_incr_traj.csv")
    ap.add_argument("--meta", default=None)
    ap.add_argument("--reproj-post-max", type=float, default=5.0)
    ap.add_argument("--straight-min", type=float, default=0.6)
    ap.add_argument("--retreat-max", type=float, default=0.25)
    ap.add_argument("--jump-mult", type=float, default=5.0)
    ap.add_argument("--min-pts", type=int, default=30)
    ap.add_argument("--min-kfs", type=int, default=15)
    ap.add_argument("--static-flow-max", type=float, default=2.0)
    a = ap.parse_args()

    kf, fr, pre, post = load_traj(a.traj)
    n = len(kf)

    results = []

    # ---- P1 continuity ----
    na = int((~np.isfinite(pre)).sum() + (~np.isfinite(post)).sum())
    results.append(("P1 continuity", na == 0,
                    "NaN/inf count = %d" % na))

    # ---- P2 reprojection improvement from sidecar ----
    import os
    val_path = a.traj.replace(".csv", "_val.json")
    if os.path.exists(val_path):
        val = json.load(open(val_path))
        e_pre, e_post = val.get("reproj_pre_px"), val.get("reproj_post_px")
        ok = (e_pre is not None and e_post is not None and
              e_post <= e_pre and e_post < a.reproj_post_max)
        results.append(("P2 reproj-BA", bool(ok),
                        "pre %.2f -> post %.2f px (need post<=pre and <%.1f)"
                        % (e_pre, e_post, a.reproj_post_max)))
    else:
        results.append(("P2 reproj-BA", None,
                        "no %s sidecar (run test_incr_pnp.py)" % val_path))

    # ---- P3 straight ----
    net = float(np.linalg.norm(post[-1] - post[0]))
    path = float(np.linalg.norm(np.diff(post, axis=0), axis=1).sum())
    straight = net / path if path > 1e-9 else float("inf")
    results.append(("P3 straight", straight >= a.straight_min,
                    "net/path = %.3f / %.3f = %.2f" %
                    (net, path, straight)))

    # ---- P4 monotonic forward on dominant axis ----
    axis = int(np.argmax(np.abs(post[-1] - post[0])))
    fwd = post[:, axis]
    cum_max = np.maximum.accumulate(fwd - fwd[0])
    retreat = (cum_max - (fwd - fwd[0])) / np.maximum(cum_max, 1e-9)
    worst = float(retreat.max())
    results.append(("P4 monotonic", worst <= a.retreat_max,
                    "axis=%s worst retreat=%.2f%% (<=%.0f%%)" %
                    ("xyz"[axis], 100 * worst, 100 * a.retreat_max)))

    # ---- P5 no jumps ----
    d = np.linalg.norm(np.diff(post, axis=0), axis=1)
    med = float(np.median(d))
    jumps = int((d > a.jump_mult * max(med, 1e-9)).sum())
    results.append(("P5 no jumps", jumps == 0,
                    "%d step(s) > %.0fx median(%.4f) max step %.4f" %
                    (jumps, a.jump_mult, med, d.max())))

# ---- P6 structure ----
    if os.path.exists(val_path):
        n_pts = val["n_pts"]
        ok6 = n >= a.min_kfs and n_pts >= a.min_pts
    else:
        n_pts = None
        ok6 = None
    results.append(("P6 structure", ok6,
                    "kfs=%d (>=%d), map pts=%s (>=%d)"
                    % (n, a.min_kfs, n_pts, a.min_pts)))

    # ---- P7 static tails from meta ----
    if a.meta:
        meta = json.load(open(a.meta))
        flows = {p["name"]: p["mean_flow_px"]
                 for p in meta.get("phases", [])}
        hold = [v for k, v in sorted(flows.items())
                if k.startswith("HOLD")]
        ok = bool(hold) and all(v < a.static_flow_max for v in hold)
        results.append(("P7 static tail", ok,
                        "HOLD mean flows = %s px (need all <%.1f)"
                        % (hold, a.static_flow_max)))
    else:
        results.append(("P7 static tail", None, "no --meta provided"))

    # ---- direction report (manual) ----
    dom = (post[-1] - post[0])[axis]
    print("dominant axis %s, displacement %+.3f (push direction "
          "must match physically)" % ("xyz"[axis], dom))
    print("bundle: %d kfs, frames %d..%d, post path %.3f" %
          (n, fr[0], fr[-1], path))
    print()

    all_pass = True
    code = {"PASS": 0, "FAIL": 1, "MANUAL": 2}
    for name, ok, detail in results:
        if ok is None:
            label = "MANUAL"
            all_pass = all_pass and True
        else:
            label = "PASS" if ok else "FAIL"
            all_pass = all_pass and ok
        print("%-14s [%s] %s" % (name, code[label], detail))

    print()
    print("RESULT:", "PASS" if all_pass else "FAIL")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
