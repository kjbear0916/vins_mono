import argparse
import csv
import sys

import cv2
import numpy as np

sys.path.insert(0, r"D:\Things\vo")
import vo_bundle


def center_of(R, t):
    c = -R.T @ t.reshape(3, 1)
    return c[0, 0], c[1, 0], c[2, 0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=r"D:\Things\vo\real_seq.avi")
    ap.add_argument("--calib", default=r"D:\Things\vo\calibration_esp32_qvga.npz")
    ap.add_argument("--out", default=r"D:\Things\vo\real_ba.csv")
    ap.add_argument("--stride", type=int, default=10)
    ap.add_argument("--max-kfs", type=int, default=60)
    ap.add_argument("--max-iter", type=int, default=60)
    ap.add_argument("--robust", type=float, default=10.0)
    ap.add_argument("--min-obs", type=int, default=3)
    ap.add_argument("--max-span", type=int, default=5)
    ap.add_argument("--min-z", type=float, default=0.05)
    ap.add_argument("--err-max", type=float, default=120.0)
    args = ap.parse_args()

    d = np.load(args.calib)
    K = d["camera_matrix"]

    cap = cv2.VideoCapture(args.video)
    frames = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
                      if len(fr.shape) == 3 else fr)
    cap.release()
    print("loaded %d frames" % len(frames))
    if len(frames) < 10:
        print("too few frames")
        return

    lk = dict(winSize=(21, 21), maxLevel=3,
              criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.02))

    # ---- 1. poses at every frame from mono VO (world->cam) ----
    from vo_core import KeyframeMonoVO
    vo = KeyframeMonoVO(K, max_corners=200, min_track=4, min_inliers=6,
                        keyframe_disp=4.0)
    poses = []          # (R_w2c, t_w2c) per frame
    updated = [False] * len(frames)
    for i, g in enumerate(frames):
        u, R, t, info = vo.step(g, lk)
        poses.append((R.copy(), t.copy()))
        updated[i] = u
    n_ok = sum(updated)
    print("VO keyframes: %d of %d frames" % (n_ok, len(frames)))
    if n_ok < 3:
        print("VO produced too few keyframes")
        return

    # ---- 2. select BA keyframes from VO updated (keyframe) frames ----
    vo_kfs = [i for i, u in enumerate(updated) if u]
    if len(vo_kfs) < 4:
        print("VO produced too few keyframes")
        return
    if len(vo_kfs) > args.max_kfs:
        stride = max(1, len(vo_kfs) // args.max_kfs)
        vo_kfs = vo_kfs[::stride]
    kf_frames = vo_kfs
    Miss = len(kf_frames)
    print("BA keyframes: %d (from %d VO kfs, stride %d)"
          % (Miss, sum(updated), stride if len(vo_kfs) != sum(updated) else 1))

    # ---- 3. chained multi-view feature tracks over the BA keyframes ----
    tracks = []                     # each: {'obs': [(kf_i, u, v)], 'cur': (u, v)}
    for i, fno in enumerate(kf_frames):
        g = frames[fno]
        if i == 0:
            p = cv2.goodFeaturesToTrack(g, maxCorners=250, qualityLevel=0.01,
                                        minDistance=8)
            if p is not None:
                for pt in p.reshape(-1, 2):
                    tracks.append({"obs": [(0, float(pt[0]), float(pt[1]))],
                                   "cur": (float(pt[0]), float(pt[1]))})
        else:
            g_prev = frames[kf_frames[i - 1]]
            cur = np.array([t["cur"] for t in tracks],
                           dtype=np.float32).reshape(-1, 1, 2) if tracks else \
                np.empty((0, 1, 2), np.float32)
            if len(cur):
                nxt, st, _ = cv2.calcOpticalFlowPyrLK(g_prev, g, cur, None, **lk)
                keep = [k for k in range(len(cur)) if st.ravel()[k] == 1]
                surv = [tracks[k] for k in keep]
                for k, t in zip(keep, surv):
                    uv = nxt[k].ravel()
                    t["obs"].append((i, float(uv[0]), float(uv[1])))
                    t["cur"] = (float(uv[0]), float(uv[1]))
                tracks = surv
            # replenish
            nroom = 250 - len(tracks)
            if nroom > 30 and len(g_prev):
                p = cv2.goodFeaturesToTrack(g, maxCorners=nroom,
                                            qualityLevel=0.01, minDistance=8)
                if p is not None:
                    for pt in p.reshape(-1, 2):
                        tracks.append({"obs": [(i, float(pt[0]), float(pt[1]))],
                                       "cur": (float(pt[0]), float(pt[1]))})
        if not len(tracks):
            p = cv2.goodFeaturesToTrack(g, maxCorners=250, qualityLevel=0.01,
                                        minDistance=8)
            if p is not None:
                for pt in p.reshape(-1, 2):
                    tracks.append({"obs": [(i, float(pt[0]), float(pt[1]))],
                                   "cur": (float(pt[0]), float(pt[1]))})
        print("  kf %d/%d: %d live tracks" % (i + 1, Miss, len(tracks)))

    # ---- 4. triangulate each track from best-parallax pair, filter ----
    kf_R = [poses[f][0] for f in kf_frames]
    kf_t = [poses[f][1].reshape(3, 1) for f in kf_frames]

    sel_tr = []                     # (X, obs list)
    killed = 0
    import statistics
    errs_all = []
    blens = []
    for tr in tracks:
        obs = tr["obs"]
        if len(obs) < args.min_obs:
            continue
        span = obs[-1][0] - obs[0][0]
        if span > args.max_span:
            continue
        best = None
        best_bl = -1.0
        for a in range(len(obs)):
            for b in range(a + 1, len(obs)):
                bl = np.linalg.norm(kf_t[obs[a][0]] - kf_t[obs[b][0]])
                if bl > best_bl:
                    best_bl = bl
                    best = (a, b)
        if best is None:
            continue
        a, b = best
        ka, ua, va = obs[a]
        kb, ub, vb = obs[b]
        X = vo_bundle.triangulate(K, kf_R[ka], kf_t[ka].ravel(),
                                  kf_R[kb], kf_t[kb].ravel(),
                                  np.array([[ua], [va]]),
                                  np.array([[ub], [vb]]))
        z = float((kf_R[ka] @ X + kf_t[ka].ravel())[2])
        # reproj on the parallax pair
        e = 0.0
        for (k_, u_, v_) in (obs[a], obs[b]):
            pr, pv, zz = vo_bundle.project(K, kf_R[k_], kf_t[k_], X)
            e += (float(np.asarray(pr).ravel()[0]) - u_) ** 2 \
                + (float(np.asarray(pv).ravel()[0]) - v_) ** 2
        errs_all.append(e)
        blens.append(best_bl)
        if z < args.min_z or e > args.err_max ** 2:
            killed += 1
            continue
        sel_tr.append((X.copy(), obs))
    if errs_all:
        n_obs_tot = sum(len(t["obs"]) for t in tracks if len(t["obs"]) >= args.min_obs)
        print("  tri-pair err: mean %.1f  med %.1f  p90 %.1f  max %.1f  (n=%d)"
              % (np.mean(errs_all), np.median(errs_all),
                 np.percentile(errs_all, 90), np.max(errs_all), len(errs_all)))
        print("  tri-pair baseline: mean %.2f  min %.2f  max %.2f"
              % (np.mean(blens), np.min(blens), np.max(blens)))
    print("tracks with >=%d obs: %d, triangulated+kept: %d, killed: %d"
          % (args.min_obs, len([t for t in tracks if len(t["obs"]) >=
              args.min_obs]), len(sel_tr), killed))
    if len(sel_tr) < 8:
        print("too few good tracks")
        return

    # ---- 5. build BA problem ----
    obs_rows = []
    pt_idx = []
    X_init = []
    for pi, (X, obs) in enumerate(sel_tr):
        pt_idx.append(pi)
        X_init.append(X)
        for (k_, u_, v_) in obs:
            obs_rows.append((k_, pi, u_, v_))
    obs_arr = np.array(obs_rows, np.float64)

    ba = vo_bundle.BundleAdjuster(K, kf_R, kf_t, obs_arr, pt_idx,
                                  max_iter=args.max_iter,
                                  fixed=set(range(6)), rho=args.robust)
    for j in range(len(X_init)):
        ba.X[j] = X_init[j]
    ba.solve()

    def ba_error(Rs, ts):
        tot = 0.0
        n = 0
        behind = 0
        for (k_, p, u_, v_) in obs_arr:
            k_ = int(round(k_))
            p = int(round(p))
            pr, pv, zz = vo_bundle.project(K, Rs[k_], ts[k_], ba.X[p])
            zz = float(np.asarray(zz).ravel()[0])
            if zz < 0.1:
                behind += 1
            else:
                tot += (float(pr) - u_) ** 2 + (float(pv) - v_) ** 2
            n += 1
        return float(np.sqrt(tot / max(n - behind, 1))), behind

    r_pre, beh_pre = ba_error(kf_R, kf_t)
    print("reproj pre-BA : %.3f px  (behind %d)" % (r_pre, beh_pre))
    r_post, beh_post = ba_error(ba.Rs, ba.ts)
    print("reproj post-BA: %.3f px  (behind %d)" % (r_post, beh_post))

    def path_len(Rs, ts):
        pts = np.array([center_of(R, t) for R, t in zip(Rs, ts)])
        return float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())

    print("path len: pre %.3f  post %.3f" % (path_len(kf_R, kf_t),
                                             path_len(ba.Rs, ba.ts)))

    with open(args.out, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["kf", "frame", "pre_x", "pre_y", "pre_z",
                     "post_x", "post_y", "post_z"])
        for i, f_ in enumerate(kf_frames):
            wr.writerow([i, f_] + list(center_of(kf_R[i], kf_t[i])) +
                        list(center_of(ba.Rs[i], ba.ts[i])))
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()