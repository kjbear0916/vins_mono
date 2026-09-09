import argparse
import csv
import sys

import cv2
import numpy as np

sys.path.insert(0, r"D:\Things\vo")
import vo_bundle
from vo_local_map import LocalMapVO

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=r"D:\Things\vo\real_seq.avi")
    ap.add_argument("--calib", default=r"D:\Things\vo\calibration_esp32.npz")
    ap.add_argument("--out", default=r"D:\Things\vo\real_ba.csv")
    ap.add_argument("--kf-disp", type=float, default=4.0)
    ap.add_argument("--min-track", type=int, default=8)
    ap.add_argument("--min-pnp", type=int, default=8)
    ap.add_argument("--robust", type=float, default=20.0)
    ap.add_argument("--max-iter", type=int, default=50)
    ap.add_argument("--min-kfs", type=int, default=10)
    args = ap.parse_args()

    d = np.load(args.calib)
    K = d["camera_matrix"]
    cap = cv2.VideoCapture(args.video)

    lk = dict(winSize=(21, 21), maxLevel=3,
              criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.02))
    lm = LocalMapVO(K, max_corners=200, quality=0.012, min_distance=8,
                    block_size=5, min_track=args.min_track,
                    keyframe_disp=args.kf_disp, min_pnp=args.min_pnp,
                    min_parallax=0.5, covis_frac=0.5,
                    pnp_thresh=3.0, pnp_min_obs=2, pnp_min_par=0.0)

    frame_no = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if len(fr.shape) == 3:
            g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        else:
            g = fr
        info = lm.step(frame_no, g, lk)
        if frame_no % 20 == 0:
            print("f%03d tracked %d kfs %d npts %d" %
                  (frame_no, info["tracked"], len(lm.kf_idx), len(lm.map)))
        frame_no += 1
    cap.release()

    print("done: %d frames, %d keyframes, %d map points" %
          (frame_no, len(lm.kf_idx), len(lm.map)))
    if len(lm.Rs) < args.min_kfs or len(lm.map) < 15:
        print("too few kfs/map. collected kfs=%d pts=%d" %
              (len(lm.Rs), len(lm.map)))
        return

    obs = []
    mp_list = [pid for pid in sorted(lm.map.keys())
               if lm.map[pid].get("X") is not None]
    pid2idx = {pid: j for j, pid in enumerate(mp_list)}
    for pid in mp_list:
        mp = lm.map[pid]
        for (slot, u, v) in mp["obs"]:
            obs.append((slot, pid2idx[pid], u, v))
    obs_arr = np.array(obs, dtype=np.float64)
    pt_idx = np.arange(len(mp_list), dtype=np.int32)

    print("BA input: obs %d, pts %d, kfs %d" %
          (len(obs_arr), len(pt_idx), len(lm.Rs)))

    def ba_error(Rs, ts):
        tot = 0.0
        n = 0
        for (slot, pidx, u, v) in obs:
            R = Rs[slot]
            t = ts[slot].reshape(3, 1)
            X = lm.map[mp_list[pidx]]["X"]
            pr, pv, z = vo_bundle.project(K, R, t, X)
            if float(np.asarray(z).ravel()[0]) < 0.01:
                continue
            tot += float(np.asarray(pr - u).ravel()[0]) ** 2 + \
                float(np.asarray(pv - v).ravel()[0]) ** 2
            n += 1
        return float(np.sqrt(tot / max(n, 1)))

    print("reproj err pre-BA : %.3f px" % ba_error(lm.Rs, lm.ts))
    ba = vo_bundle.BundleAdjuster(K, lm.Rs, lm.ts, obs_arr, pt_idx,
                                  max_iter=args.max_iter,
                                  fixed=set(range(6)), rho=args.robust)
    ba.solve()
    print("reproj err post-BA: %.3f px" % ba_error(ba.Rs, ba.ts))

    def center(R, t):
        c = -R.T @ t.reshape(3, 1)
        return c[0, 0], c[1, 0], c[2, 0]

    def path_len(Rs, ts):
        pts = np.array([center(R, t) for R, t in zip(Rs, ts)])
        return float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())

    print("path len: pre %.3f  post %.3f" %
          (path_len(lm.Rs, lm.ts), path_len(ba.Rs, ba.ts)))

    with open(args.out, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["idx", "pre_x", "pre_y", "pre_z",
                     "post_x", "post_y", "post_z"])
        for i, (R0, t0, R1, t1) in enumerate(zip(lm.Rs, lm.ts, ba.Rs, ba.ts)):
            wr.writerow([i] + list(center(R0, t0)) + list(center(R1, t1)))
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()