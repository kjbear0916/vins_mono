"""ATE harness validation against KNOWN synthetic camera truth.

Pipeline under test (EXACTLY what real usage does):
  1. gen_synth_seq renders a clean forward translation with camera centres
     recorded in a sidecar CSV (KNOWN truth).
  2. test_incr_pnp.py (the official gate pipeline) produces *_traj.csv with
     per-keyframe pre/post camera centres.
  3. run_gt_ate's alignment helpers (center_of, umeyama_sim3) are applied
     here to compare VO output against the known truth.

Success = small ATE AND post-BA differs from pre-BA (BA actually moved).

No chessboard is needed: the VO scene is the clean point cloud, and truth is
known analytically. This isolates the ATE ALIGNMENT MATH from visual-detect
and from VO health.

Usage: python test_ate_harness.py [--step 0.16]
"""
import argparse
import csv
import os
import subprocess
import sys

import numpy as np

from run_gt_ate import umeyama_sim3

VO = os.path.dirname(os.path.abspath(__file__))
CALIB = os.path.join(VO, "calibration_esp32_qvga.npz")
HOLD_S = 3.0
MOVE_S = 6.0
FPS = 16.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=float, default=0.16)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--noise", type=float, default=1.5)
    a = ap.parse_args()

    d = np.load(CALIB)
    K = d["camera_matrix"]
    n_move = int(MOVE_S * FPS)
    n_hold = int(HOLD_S * FPS)

    # ---- 1. render + record truth (analytic camera centre per frame) ----
    out = os.path.join(VO, "_cov", "ate_harness.avi")
    truth_csv = os.path.join(VO, "_cov", "ate_harness_truth.csv")
    import cv2
    from gen_synth_seq import make_scene, render

    rng = np.random.default_rng(a.seed)
    scene = make_scene(rng)
    gray = np.zeros((240, 320), np.float32)
    t_wc = np.zeros(3)
    writer = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"MJPG"),
                             FPS, (320, 240), False)
    with open(truth_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame", "x", "y", "z"])
        for i in range(n_hold + n_move + n_hold):
            if n_hold <= i < n_hold + n_move:
                t_wc[2] -= a.step
            render(K, gray, scene, t_wc, rng, a.noise)
            writer.write(np.clip(gray, 0, 255).astype(np.uint8))
            w.writerow([i] + list(-t_wc))  # camera centre = -world offset
    writer.release()
    truth = {int(r["frame"]): np.array([float(r["x"]), float(r["y"]),
                                         float(r["z"])]) for r in
             csv.DictReader(open(truth_csv))}

    # ---- 2. run the OFFICIAL gate pipeline ----
    traj = os.path.join(VO, "_cov", "ate_harness_traj.csv")
    subprocess.run([sys.executable, os.path.join(VO, "test_incr_pnp.py"),
                    "--video", out, "--out", traj], cwd=VO, check=True)

    rows = list(csv.DictReader(open(traj)))
    frames = np.array([int(r["frame"]) for r in rows])
    pre = np.array([[float(r["pre_x"]), float(r["pre_y"]), float(r["pre_z"])]
                    for r in rows])
    post = np.array([[float(r["post_x"]), float(r["post_y"]),
                      float(r["post_z"])] for r in rows])
    gt = np.array([truth[i] for i in frames])

    def ates(P):
        c, R, t = umeyama_sim3(P, gt)
        ali = (c * R @ P.T).T + t
        e = np.linalg.norm(ali - gt, axis=1)
        return float(np.sqrt(np.mean(e ** 2))), c

    e_pre, sc_pre = ates(pre)
    e_post, sc_post = ates(post)
    print("kfs=%d  truth z %.2f..%.2f (world)" %
          (len(frames), gt[:, 2].min(), gt[:, 2].max()))
    print("scales: pre %.3g post %.3g" % (sc_pre, sc_post))
    print("ATE pre-BA : %.3f" % e_pre)
    print("ATE post-BA: %.3f" % e_post)
    if e_pre > 0:
        print("improvement: %.1f%%" % (100.0 * (1.0 - e_post / e_pre)))
    print("max per-kf err pre: %.3f  post: %.3f" %
          (np.linalg.norm((umeyama_sim3(pre, gt)[0] * umeyama_sim3(pre, gt)[1] @ pre.T).T + umeyama_sim3(pre, gt)[2] - gt, axis=1).max(),
           np.linalg.norm((umeyama_sim3(post, gt)[0] * umeyama_sim3(post, gt)[1] @ post.T).T + umeyama_sim3(post, gt)[2] - gt, axis=1).max()))

    ok_ate = e_post < 2.0
    ok_improve = (e_post - e_pre) < -1e-6 or e_post < e_pre
    ok_move = abs(e_post - e_pre) > 1e-9
    print("\nATE SMALL (post<2):", ok_ate)
    print("BA IMPROVED        :", ok_improve)
    print("BA ACTUALLY MOVED  :", ok_move)
    print("RESULT:", "PASS" if (ok_ate and ok_improve and ok_move) else "FAIL")
    return 0 if (ok_ate and ok_improve and ok_move) else 1


if __name__ == "__main__":
    sys.exit(main())