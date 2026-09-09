import argparse
import csv
import time

import cv2
import numpy as np

import vo_bundle
import vo_core
from vo_local_map import LocalMapVO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://192.168.1.125:81/stream")
    ap.add_argument("--calib", default=r"D:\Things\vo\calibration_esp32.npz")
    ap.add_argument("--max-frames", type=int, default=120)
    ap.add_argument("--max-track", type=int, default=8)
    ap.add_argument("--kf-disp", type=float, default=4.0)
    ap.add_argument("--min-pnp", type=int, default=8)
    ap.add_argument("--out", default=r"D:\Things\vo\real_ba.csv")
    ap.add_argument("--robust", type=float, default=20.0)
    ap.add_argument("--max-iter", type=int, default=50)
    ap.add_argument("--save-video", default=r"D:\Things\vo\real_seq.avi", help="optional video out")
    args = ap.parse_args()

    d = np.load(args.calib)
    K = d["camera_matrix"]
    dist = d["dist_coeffs"].ravel()

    cap = cv2.VideoCapture(args.url)

    def grab():
        t0 = time.time()
        while time.time() - t0 < 6:
            ok, fr = cap.read()
            if ok and fr is not None:
                return fr
        return None

    f0 = grab()
    if f0 is None:
        print("stream down")
        return
    h, w = f0.shape[:2]
    map1, map2 = cv2.initUndistortRectifyMap(
        K, dist, None, K, (w, h), cv2.CV_32FC1)

    out = None
    if args.save_video:
        out_vid = cv2.VideoWriter(args.save_video, cv2.VideoWriter_fourcc(*"MJPG"),
                                  10.0, (w, h), False)

    lk = dict(winSize=(21, 21), maxLevel=3,
              criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.02))

    lm = LocalMapVO(K, max_corners=200, quality=0.012, min_distance=8,
                    block_size=5, min_track=args.max_track,
                    keyframe_disp=args.kf_disp, min_pnp=args.min_pnp,
                    min_parallax=0.5, covis_frac=0.5,
                    pnp_thresh=3.0, pnp_min_obs=2, pnp_min_par=0.0)

    frame_no = 0
    start = time.time()
    local_traj = []   # (frame_no, center x,y,z)
    prev_center = None
    last_rot = None

    print("collecting real keyframes... move camera slowly, steadily")
    while frame_no < args.max_frames:
        fr = grab()
        if fr is None:
            print("stream dropped at frame", frame_no)
            break
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        g = cv2.remap(g, map1, map2, cv2.INTER_LINEAR)

        info = lm.step(frame_no, g, lk)
        if info.get("kf"):
            kf = lm.kf_idx[-1] if len(lm.kf_idx) else frame_no
            R = lm.Rs[-1]
            t = lm.ts[-1]
            center = -R.T @ t.reshape(3, 1)
            local_traj.append((kf, center[0, 0], center[1, 0], center[2, 0]))

        if frame_no % 15 == 0:
            print("frame %d  tracked %d  kfs %d  npts %d" %
                  (frame_no, info["tracked"], len(lm.kf_idx), len(lm.map)))
        frame_no += 1
        if out_vid is not None:
            out_vid.write(g)

    cap.release()
    if out_vid is not None:
        out_vid.release()

    print("collected %d keyframes, %d map points" % (len(lm.kf_idx), len(lm.map)))
    if len(lm.Rs) < 4 or len(lm.map) < 10:
        print("too few keyframes/map for BA. try moving more / lower kf-disp")
        return

    # build obs for BA from map
    obs = []
    for pid, mp in lm.map.items():
        if mp.get("X") is None:
            continue
        for (slot, u, v) in mp["obs"]:
            obs.append((slot, pid, u, v))
    obs_arr = np.array(obs, dtype=np.float64)
    pt_idx = np.array(sorted(lm.map.keys()), dtype=np.int32)
    kf_Rs = lm.Rs
    kf_ts = lm.ts

    print("obs %d, pts %d, kfs %d" % (len(obs_arr), len(pt_idx), len(kf_Rs)))

    def ba_error(kf_Rs, kf_ts):
        tot = 0.0
        n = 0
        for (slot, pid, u, v) in obs:
            R = kf_Rs[slot]
            t = kf_ts[slot].reshape(3, 1)
            X = lm.map[pid]["X"]
            pr, pv, _ = vo_bundle.project(K, R, t, X)
            tot += (pr - u) ** 2 + (pv - v) ** 2
            n += 1
        return np.sqrt(tot / max(n, 1))

    print("reproj err (pre-BA): %.3f px" % ba_error(kf_Rs, kf_ts))

    fixed = set(range(6))
    ba = vo_bundle.BundleAdjuster(K, kf_Rs, kf_ts, obs_arr, pt_idx,
                                  max_iter=args.max_iter, fixed=fixed,
                                  rho=args.robust)
    ba.solve()

    print("reproj err (post-BA): %.3f px" % ba_error(ba.Rs, ba.ts))

    # before/after traj
    def to_center(R, t):
        c = -R.T @ t.reshape(3, 1)
        return c[0, 0], c[1, 0], c[2, 0]

    def path_len(Rs, ts):
        pts = np.array([to_center(R, t) for R, t in zip(Rs, ts)])
        return float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())

    print("path length: pre %.3f  post %.3f" % (
        path_len(lm.Rs, lm.ts), path_len(ba.Rs, ba.ts)))

    with open(args.out, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["idx", "pre_x", "pre_y", "pre_z", "post_x", "post_y", "post_z"])
        for i, (R0, t0, R1, t1) in enumerate(zip(lm.Rs, lm.ts, ba.Rs, ba.ts)):
            c0 = to_center(R0, t0)
            c1 = to_center(R1, t1)
            wr.writerow([i] + list(c0) + list(c1))
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()