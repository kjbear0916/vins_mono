"""Mechanism refinement: is the 20mm blind-spot ATE gauge, or deformation?

ATESort (run_gt_ate.py) aligns VO trajectory to GT with Umeyama Sim3 BEFORE
measuring error, so a pure global similarity (3R + 3t + 1s -- the mono BA
gauge freedoms) is removed before ATE is computed.  If ATEpost is therefore
*still* large on the sway blind case, the error cannot be a gauge drift: it
must be a spatial, non-rigid deformation of the trajectory that survived
alignment.

Protocol:
  1. Reconstruct the analytic GT camera path for a generator configuration
     (step, sway-amp, sway-cycles, seed) -- pure translation along -z plus a
     lateral sine on x, matching gen_synth_seq's renderer exactly.
  2. Control: take GT, apply an ARBITRARY global (s,R,t), then align back
     with umeyama_sim3.  Residual must be ~0 -- proves Sim3 alignment erases
     global similarity.
  3. Case: take the VO post-BA trajectory (same frames), align to GT, measure
     ATE after alignment.
  4. Per-segment scale ratio post/pre-optimization: a trajectory reconstructed
     by BA is a local deformation if the implied instantaneous scale varies
     along the path.

Run:  python shape_gauge_probe.py  (_adv/sway_s25_n25_a70_j0_traj.csv)
"""
import csv
import sys

import numpy as np

sys.path.insert(0, r"D:\Things\vo")
from run_gt_ate import umeyama_sim3, center_of

HOLD0F = 48   # 3 s at 16 fps
MOVEF = 96    # 6 s at 16 fps


def gt_path(step, sway_amp, cycles):
    """Analytic per-frame camera origin from gen_synth_seq's renderer."""
    n = HOLD0F + MOVEF
    pts = []
    z = 0.0
    for f in range(n):
        k = f - HOLD0F
        if k >= 0:
            z = -(k + 1) * step
        x = sway_amp * np.sin(2.0 * np.pi * cycles * k /
                              max(1, MOVEF - 1)) if k >= 0 else 0.0
        pts.append([x, 0.0, z])
    return np.array(pts), np.arange(n)


def main():
    traj = sys.argv[1] if len(sys.argv) > 1 else \
        r"D:\Things\vo\_adv\sway_s25_n25_a70_j0_traj.csv"
    step = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25
    amp = float(sys.argv[3]) if len(sys.argv) > 3 else 0.70
    cycles = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0

    rows = list(csv.DictReader(open(traj, newline="")))
    frames = np.array([int(r["frame"]) for r in rows])
    post = np.array([[float(r["post_x"]), float(r["post_y"]),
                      float(r["post_z"])] for r in rows])
    gt, gt_all = gt_path(step, amp, cycles)
    G = gt[frames]

    # --- control: global similarity removed by Sim3 alignment ---
    rng = np.random.default_rng(0)
    R = np.eye(3)
    th = 0.4
    R = np.array([[np.cos(th), -np.sin(th), 0],
                  [np.sin(th), np.cos(th), 0], [0, 0, 1.0]])
    s = 1.7
    t = np.array([3.0, -2.0, 5.0])
    G2 = s * (R @ G.T).T + t
    cs, Rs, ts = umeyama_sim3(G, G2)
    ali = (cs * Rs @ G.T).T + ts
    control_rmse = float(np.linalg.norm(ali - G2, axis=1).mean())

    # --- case: VO post-BA aligned to GT ---
    cs, Rs, ts = umeyama_sim3(G, post)
    post_ali = (cs * Rs @ post.T).T + ts
    case_rmse = float(np.linalg.norm(post_ali - G, axis=1).mean())

    # --- per-segment instantaneous scale of VO frame vs GT frame ---
    gd = np.linalg.norm(np.diff(G, axis=0), axis=1)
    pd = np.linalg.norm(np.diff(post, axis=0), axis=1)
    # match nearest frames when kf gaps differ
    ratio = []
    for i in range(len(gd)):
        ratio.append(float(pd[min(i, len(pd) - 1)] /
                           max(gd[i], 1e-9)))
    ratio = np.array(ratio)
    print("frames: %d VO kfs -> %.1f%% of GT density" %
          (len(frames), 100.0 * len(frames) / MOVEF))
    print("CONTROL (global sim removed):      post-align rmse = %.6f  (expect ~0)"
          % control_rmse)
    print("CASE    (VO->GT, post-BA rmse):    post-align rmse = %.4f" % case_rmse)
    print("per-segment scale ratio:  mean %.3f  min %.3f  max %.3f  "
          "range %.3f" % (ratio.mean(), ratio.min(), ratio.max(),
                          ratio.max() - ratio.min()))
    if case_rmse > 100 * control_rmse and \
            (ratio.max() - ratio.min()) / max(ratio.mean(), 1e-9) > 0.2:
        print("VERDICT: error is NON-RIGID spatial deformation (survives Sim3,"
              " scale varies along path), not global gauge drift.")
    else:
        print("VERDICT: heterogeneous signatures -- inspect")
    return 0


if __name__ == "__main__":
    sys.exit(main())