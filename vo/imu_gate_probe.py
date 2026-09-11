"""IMU-external-reference gate prototype (IMU gate probe).

The gate story so far (VO_METHODOLOGY_ABSTRACTION.md 2-3/2-4): trajectory-
intrinsic statistics cannot see the off-axis blind spot because mono BA can
absorb lateral energy into a non-rigid deformation; the only orthogonal
checks are external references (ATE chessboard, IMU).  ATE is demonstrated.
This probe demonstrates the IMU side: synthesise a yaw-drifting flight
(--yaw-drift in gen_synth_seq.py writes a _imu.json gyro log alongside the
video), run the SAME frontend VO the Blackwell pipeline uses
(KeyframeMonoVO), and compare the VO-accumulated relative rotation to the
gyro-integrated angle.  The comparison is done on the RELATIVE rotation
angle between first MOVE kf and last MOVE kf, so VO's arbitrary world
frame cancels.

  gate IMU:  |VO_angle_deg - gyro_angle_deg| < IMU_ROT_TOL_DEG (default 5)
             (1.0 => under 45 mm equivalent lateral drift on a 2.6 m
              approach room if the whole error were scale-free lateral)

Usage (generated rotation-free + yaw cases, gates + IMU verdicts):
  python gen_synth_seq.py --out _adv/imu_baseline.avi --board \
      --yaw-drift 0.0    --out-imu _adv/imu_baseline_imu.json
  python gen_synth_seq.py --out _adv/imu_yaw15.avi   --board \
      --yaw-drift 0.15   --out-imu _adv/imu_yaw15_imu.json   (deg/s)
  python imu_gate_probe.py --video _adv/imu_yaw15.avi \
      --gyro _adv/imu_yaw15_imu.json
"""
import argparse
import json
import math

import cv2
import numpy as np

VO = r"D:\Things\vo"
import sys
sys.path.insert(0, VO)


def rel_rot_angle_deg(R0, R1):
    """Angle of the relative rotation R1 @ R0^T (frame-independent)."""
    dR = R1 @ R0.T
    cos = (np.trace(dR) - 1.0) / 2.0
    return float(math.degrees(math.acos(max(-1.0, min(1.0, cos)))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--gyro", required=True,
                    help="synthetic IMU json written by gen_synth_seq")
    ap.add_argument("--calib", default=r"D:\Things\vo\calibration_esp32_qvga.npz")
    ap.add_argument("--tol-deg", type=float, default=5.0,
                    help="gate PASS tolerance for |VO - gyro| rotation angle")
    a = ap.parse_args()

    d = np.load(a.calib)
    K = d["camera_matrix"]

    cap = cv2.VideoCapture(a.video)
    frames = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
                      if len(fr.shape) == 3 else fr)
    cap.release()
    print("loaded %d frames" % len(frames))

    g = json.load(open(a.gyro))
    fps = float(g["fps"])
    yaw_drift = float(g.get("yaw_drift", 0.0))
    gyro = g["gyro"]
    n_move = sum(1 for e in gyro if abs(e["gy"]) > 1e-9)
    # integrated gyro angle over the MOVE phase (rad -> deg)
    gyro_angle_deg = math.degrees(yaw_drift * n_move / fps)
    print("gyro: %d MOVE frames @ yaw %.3f rad/s -> integrated %.2f deg"
          % (n_move, yaw_drift, gyro_angle_deg))

    lk = dict(winSize=(21, 21), maxLevel=3,
              criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.02))
    from vo_core import KeyframeMonoVO
    vo = KeyframeMonoVO(K, max_corners=200, min_track=4, min_inliers=6,
                        keyframe_disp=4.0)
    kf_R = []           # rotation per keyframe (world->cam)
    kf_frames = []
    for i, g_ in enumerate(frames):
        u, R, t, info = vo.step(g_, lk)
        if u:
            kf_R.append(R.copy())
            kf_frames.append(i)
    print("VO keyframes: %d of %d frames" % (len(kf_R), len(frames)))
    if len(kf_R) < 4:
        print("VO: too few keyframes -- cannot run IMU gate")
        return 1

    # MOVE band from the generator's own meta (HOLD0+HOLD1 frame counts),
    # so the probe works even when yaw_drift == 0 (no gyro marker).
    import os
    meta_path = a.video.replace(".avi", "_meta.json")
    n_hold = 0
    if os.path.exists(meta_path):
        meta = json.load(open(meta_path))
        n_hold = int(meta.get("frames", {}).get("HOLD0", 48))
    move_lo, move_hi = n_hold, min(len(gyro), len(gyro) - 1)

    # restrict to MOVE keyframes (skip HOLD0 clamp; simple: from kf after
    # HOLD0 length = first gyro sample == 0 skip). We use gyro to define
    # MOVE: kf_frames i is in MOVE if gyro[kf_frames[i]] has gy != 0.
    move_idx = [i for i, f_ in enumerate(kf_frames)
                if (gyro[f_]["gy"] != 0.0
                    if any(abs(e["gy"]) > 1e-9 for e in gyro)
                    else move_lo <= f_ <= move_hi)]
    if len(move_idx) < 2:
        print("too few MOVE keyframes for the rotation comparison")
        return 1
    i0, i1 = move_idx[0], move_idx[-1]
    vo_angle_deg = rel_rot_angle_deg(kf_R[i0], kf_R[i1])
    err_deg = abs(vo_angle_deg - gyro_angle_deg)
    print("VO MOVE kfs: %d..%d (frames %d..%d)"
          % (i0, i1, kf_frames[i0], kf_frames[i1]))
    print("VO   relative rotation over MOVE: %.2f deg" % vo_angle_deg)
    print("gyro integrated rotation over MOVE: %.2f deg" % gyro_angle_deg)
    print("|VO - gyro| = %.2f deg  (tol %.1f)" % (err_deg, a.tol_deg))

    ok = err_deg <= a.tol_deg + 1e-9
    if ok:
        print("RESULT: PASS  (gyro-rotation consistency gate  %.2f <= %.1f)"
              % (err_deg, a.tol_deg))
    else:
        print("RESULT: FAIL  (gyro-rotation consistency gate  %.2f > %.1f)"
              % (err_deg, a.tol_deg))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())