import csv
import sys

import cv2
import numpy as np

sys.path.insert(0, r"D:\Things\vo")
import vo_bundle


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="incremental PnP + BA on a recorded VO sequence")
    ap.add_argument("--video",
                    default=r"D:\Things\vo\real_seq.avi")
    ap.add_argument("--out", default=r"D:\Things\vo\real_incr_traj.csv")
    args = ap.parse_args()

    K = np.load(r"D:\Things\vo\calibration_esp32_qvga.npz")["camera_matrix"]
    cap = cv2.VideoCapture(args.video)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
    cap.release()
    print("loaded %d frames" % len(frames))

    lk = dict(winSize=(21, 21), maxLevel=3,
              criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.02))
    MIN_FLOW = 12.0
    MIN_PNP = 8
    MAX_PTS = 300

    kfs = [0]
    Rs = [np.eye(3)]
    ts = [np.zeros((3, 1))]
    mapp = {}
    next_pid = 0

    kf_gray = frames[0].copy()
    cur_pts = cv2.goodFeaturesToTrack(kf_gray, MAX_PTS, 0.01, 8)
    cur_pts = cur_pts.reshape(-1, 1, 2).astype(np.float32) if cur_pts is not None \
        else np.empty((0, 1, 2), np.float32)
    cur_ids = list(range(next_pid, next_pid + len(cur_pts)))
    next_pid += len(cur_ids)
    stage = "two_view"
    pnp_try = pnp_fail = pnp_ok = 0

    for fno in range(1, len(frames)):
        g = frames[fno]
        if fno % 50 == 0:
            print("  frame %d stage=%s" % (fno, stage), flush=True)
        if fno % 25 == 0:
            import time
            print("  @frame %d pts=%d kfs=%d" % (fno, len(mapp), len(kfs)),
                  flush=True)
        if len(cur_pts) == 0:
            Rs.append(Rs[-1].copy())
            ts.append(ts[-1].copy())
            kfs.append(fno)
            cur_pts = cv2.goodFeaturesToTrack(g, MAX_PTS, 0.01, 8)
            cur_pts = cur_pts.reshape(-1, 1, 2).astype(np.float32) \
                if cur_pts is not None else np.empty((0, 1, 2), np.float32)
            cur_ids = list(range(next_pid, next_pid + len(cur_pts)))
            next_pid += len(cur_ids)
            kf_gray = g.copy()
            stage = "two_view"
            continue
        # track against the HELD keyframe reference
        nxt, st, _ = cv2.calcOpticalFlowPyrLK(kf_gray, g, cur_pts, None, **lk)
        ok = st.ravel() == 1
        old = cur_pts[ok].reshape(-1, 2)
        new = nxt[ok].reshape(-1, 2)
        ids = [cur_ids[i] for i in range(len(ok)) if ok[i]]
        if len(old) < MIN_PNP:
            # reference too stale; add an anchor keyframe for the new
            # reference image so two-view obs (k-1, k) stay self-consistent
            Rs.append(Rs[-1].copy())
            ts.append(ts[-1].copy())
            kfs.append(fno)
            cur_pts = cv2.goodFeaturesToTrack(g, MAX_PTS, 0.01, 8)
            cur_pts = cur_pts.reshape(-1, 1, 2).astype(np.float32) \
                if cur_pts is not None else np.empty((0, 1, 2), np.float32)
            cur_ids = list(range(next_pid, next_pid + len(cur_pts)))
            next_pid += len(cur_ids)
            kf_gray = g.copy()
            stage = "two_view"
            continue
        flow = float(np.linalg.norm(new - old, axis=1).mean())
        if flow < MIN_FLOW:
            continue
        # ---- frame reaches the flow threshold; decide its pose ----
        if stage == "two_view":
            E, m = cv2.findEssentialMat(old, new, K, cv2.RANSAC, 0.999, 1.0)
            if E is None:
                continue
            m = m.ravel() == 1
            oo, nn = old[m], new[m]
            _, R_rel, t_rel, _ = cv2.recoverPose(E, oo, nn, K)
            t_rel = t_rel.ravel()
            # reference camera = the held kf_gray; if re-seeded after a
            # tracking loss we approximate its pose with the last keyframe.
            if len(Rs) > 1:
                R_ref, t_ref = Rs[-1], ts[-1].ravel()
            else:
                R_ref, t_ref = np.eye(3), np.zeros(3)

            def zcount(tt):
                c = 0
                Rn = R_rel @ R_ref
                tn = R_rel @ t_ref + tt
                for i in range(len(old)):
                    X = vo_bundle.triangulate(
                        K, R_ref, t_ref, Rn, tn,
                        np.array([[old[i, 0]], [old[i, 1]]]),
                        np.array([[new[i, 0]], [new[i, 1]]]))
                    if np.isfinite(X).all() and 0.01 < X[2] < 1e4:
                        c += 1
                return c
            best_s, best_c = 1.0, -1
            for sc in (1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, 1.0, 3.0, 1e1, 3e1, 1e2, 3e2, 1e3):
                c = zcount(t_rel * sc)
                if c > best_c:
                    best_c, best_s = c, sc
            R_new = R_rel @ R_ref
            t_new = R_rel @ t_ref + t_rel * best_s
            allp, sels = [], []
            for i in range(len(old)):
                X = vo_bundle.triangulate(
                    K, R_ref, t_ref, R_new, t_new,
                    np.array([[old[i, 0]], [old[i, 1]]]),
                    np.array([[new[i, 0]], [new[i, 1]]]))
                if not np.isfinite(X).all():
                    continue
                if X[2] > 0.001 and abs(X[2]) < 1e5:
                    allp.append(X)
                    sels.append(i)
            if len(allp) < 4 or best_c < 4:
                print("  two_view rejected at frame %d (inl %d)" % (fno, best_c))
                continue
            Rs.append(R_new)
            ts.append(t_new.reshape(3, 1))
            kfs.append(fno)
            k = len(Rs) - 1
            for i, idx in enumerate(sels):
                pid = ids[idx]
                if pid in mapp:
                    continue
                Xs = allp[i]
                if Xs[2] <= 0.05 or abs(Xs[2]) > 1e4:
                    continue
                mapp[pid] = {"X": Xs.ravel(),
                             "obs": [(k - 1, float(old[idx, 0]), float(old[idx, 1])),
                                     (k, float(new[idx, 0]), float(new[idx, 1]))]}
            # hold survivors as the new reference, top up with fresh pts
            surv = new.reshape(-1, 1, 2).astype(np.float32)
            p = cv2.goodFeaturesToTrack(g, MAX_PTS - len(surv), 0.01, 8) \
                if len(surv) < MAX_PTS else None
            if p is not None and len(p):
                p = p.reshape(-1, 1, 2)
                dist = np.linalg.norm(p[:, 0, :][:, None, :]
                                      - surv[:, 0, :][None, :, :], axis=2)
                p = p[dist.min(axis=1) > 8.0]
            if p is not None and len(p):
                cur_pts = np.vstack([surv, p])
                cur_ids = ids + list(range(next_pid, next_pid + len(p)))
                next_pid += len(p)
            else:
                cur_pts = surv
                cur_ids = ids
            kf_gray = g.copy()
            stage = "pnp"
            print("kf %d frame %d: 2-view init, %d map pts (best_s %.3f)"
                  % (k, fno, len(mapp), best_s))
            continue

        # pnp localization against map
        obj, img, used = [], [], []
        pnp_try += 1
        for pid, (u, v) in zip(ids, new):
            if pid in mapp:
                obj.append(mapp[pid]["X"])
                img.append((float(u), float(v)))
                used.append(pid)
        if len(img) < MIN_PNP:
            pnp_fail += 1
            # keep tracking; more frames will accumulate
            continue
        okp, rvec, tvec, inl = cv2.solvePnPRansac(
            np.array(obj), np.array(img), K, None, iterationsCount=200,
            reprojectionError=5.0, confidence=0.995)
        if not okp or len(inl) < MIN_PNP:
            pnp_fail += 1
            continue
        inl = inl.ravel().tolist()
        R, _ = cv2.Rodrigues(rvec)
        t = tvec.reshape(3, 1)
        zs = [(R @ mapp[used[j]]["X"] + t.ravel())[2] for j in inl]
        if float(np.median(zs)) < 0.05:
            pnp_fail += 1
            continue
        k = len(Rs)
        pnp_ok += 1
        Rs.append(R)
        ts.append(t)
        kfs.append(fno)
        for j in inl:
            pid = used[j]
            mapp[pid]["obs"].append((k, img[j][0], img[j][1]))
        added = 0
        for i, pid in enumerate(ids):
            if pid in mapp or pid >= next_pid:
                continue
            X = vo_bundle.triangulate(K, Rs[-2], ts[-2].ravel(),
                                      R, t.ravel(),
                                      np.array([[old[i, 0]], [old[i, 1]]]),
                                      np.array([[new[i, 0]], [new[i, 1]]]))
            if not np.isfinite(X).all():
                continue
            z = float((R @ X + t.ravel())[2])
            if z < 0.05 or abs(X[2]) > 200:
                continue
            mapp[pid] = {"X": X.ravel(),
                         "obs": [(k - 1, float(old[i, 0]), float(old[i, 1])),
                                 (k, float(new[i, 0]), float(new[i, 1]))]}
            added += 1
        print("kf %d frame %d: map %d pts, +%d, pnp inl %d"
              % (k, fno, len(mapp), added, len(inl)))
        # hold survivors + top up
        surv = new.reshape(-1, 1, 2).astype(np.float32)
        p = cv2.goodFeaturesToTrack(g, MAX_PTS - len(surv), 0.01, 8) \
            if len(surv) < MAX_PTS else None
        if p is not None and len(p):
            p = p.reshape(-1, 1, 2)
            dist = np.linalg.norm(p[:, 0, :][:, None, :]
                                  - surv[:, 0, :][None, :, :], axis=2)
            p = p[dist.min(axis=1) > 8.0]
        if p is not None and len(p):
            cur_pts = np.vstack([surv, p])
            cur_ids = ids + list(range(next_pid, next_pid + len(p)))
            next_pid += len(p)
        else:
            cur_pts = surv
            cur_ids = ids
        kf_gray = g.copy()

    print("---- result ----")
    print("pnp try=%d fail=%d ok=%d" % (pnp_try, pnp_fail, pnp_ok))
    print("keyframes:", len(Rs), "frames:", kfs)
    print("map points:", len(mapp))
    if len(Rs) < 4 or not mapp:
        print("not enough structure")
        return

    obs_rows = []
    kf_stride = max(1, len(Rs) // 40 + 1)
    if kf_stride > 1:
        submask = list(range(0, len(Rs), kf_stride))
        if len(submask) < 6:
            submask = list(range(0, len(Rs)))
        Rs = [Rs[i] for i in submask]
        ts = [ts[i] for i in submask]
        kfs = [kfs[i] for i in submask]
        sremap = {old: new for new, old in enumerate(submask)}
    else:
        sremap = {i: i for i in range(len(Rs))}
    for pid, mp in mapp.items():
        for (k, u, v) in mp["obs"]:
            if k in sremap:
                obs_rows.append((sremap[k], pid, u, v))
    from collections import Counter
    cnt = Counter(int(r[1]) for r in obs_rows)
    keep_ids = [p for p, c in cnt.most_common(150)]
    pid_to_j = {pid: j for j, pid in enumerate(keep_ids)}
    obs_arr = np.array([(int(k), pid_to_j[int(pid)], u, v)
                        for (k, pid, u, v) in obs_rows if int(pid) in pid_to_j],
                       np.float64)
    obs_arr[:, 0] = obs_arr[:, 0].astype(int)
    obs_arr[:, 1] = obs_arr[:, 1].astype(int)
    pt_idx = np.unique(obs_arr[:, 1].astype(np.int32))
    print("BA after subsample: kfs=%d obs=%d pts=%d"
          % (len(Rs), len(obs_arr), len(pt_idx)))
    if len(obs_arr) < 30 or len(pt_idx) < 5:
        print("too few obs for BA")
        return

    def ba_error_sub(Rs2, ts2, oa, Xl):
        tot = 0.0
        ci = 0
        per_kf = {}
        nz = 0
        for (k, j, u, v) in oa:
            X = Xl[int(j)]
            pr, pv, z = vo_bundle.project(K, Rs2[int(k)], ts2[int(k)], X)
            z = float(np.asarray(z).ravel()[0])
            if z < 0.01:
                nz += 1
                continue
            rr = (float(np.asarray(pr).ravel()[0]) - u) ** 2
            rr += (float(np.asarray(pv).ravel()[0]) - v) ** 2
            tot += rr
            per_kf.setdefault(int(k), []).append(np.sqrt(rr))
            ci += 1
        worst = sorted(per_kf.items(),
                       key=lambda kv: float(np.median(kv[1])), reverse=True)[:6]
        print("  per-kf med px:", ", ".join("kf%d:%.1f" % (k, np.median(v))
                                            for k, v in worst))
        print("    (bad-z obs=%d, len(Xl)=%d)" % (nz, len(Xl)))
        return float("inf") if ci == 0 else float(np.sqrt(tot / ci))

    print("reproj pre-BA (raw): %.2f px"
          % ba_error_sub(Rs, ts, obs_arr, [mapp[keep_ids[int(j)]]["X"]
                                           for j in pt_idx]))

    resid = []
    for (k, j, u, v) in obs_arr:
        X = mapp[keep_ids[int(j)]]["X"]
        pr, pv, z = vo_bundle.project(K, Rs[int(k)], ts[int(k)], X)
        z = float(np.asarray(z).ravel()[0])
        dj = ((float(np.asarray(pr).ravel()[0]) - u) ** 2
              + (float(np.asarray(pv).ravel()[0]) - v) ** 2) ** 0.5
        resid.append(float(dj))
    resid = np.array(resid)
    print("  raw obs resid: median %.2f  p90 %.2f  max %.2f  (n=%d)"
          % (np.median(resid), np.percentile(resid, 90), resid.max(),
             len(resid)))
    THR = 30.0
    zok = []
    for (k, j, u, v) in obs_arr:
        X = mapp[keep_ids[int(j)]]["X"]
        _, _, z = vo_bundle.project(K, Rs[int(k)], ts[int(k)], X)
        zok.append(float(np.asarray(z).ravel()[0]) >= 0.01)
    keep = (resid <= THR) & np.array(zok)
    oa_clean = obs_arr[keep]
    print("  dropping %d/%d obs (resid>%.0fpx or z<0.01) -> %d obs, %d pts"
          % (int((~keep).sum()), len(obs_arr), THR, len(oa_clean),
             len(np.unique(oa_clean[:, 1].astype(np.int32)))))
    if len(oa_clean) < 30 or len(np.unique(oa_clean[:, 1])) < 5:
        print("too few clean obs for BA")
        return
    pt_idx_clean = np.unique(oa_clean[:, 1].astype(np.int32))
    Xp0 = {int(j): mapp[keep_ids[int(j)]]["X"] for j in pt_idx_clean}
    e_pre = ba_error_sub(Rs, ts, oa_clean, Xp0)
    print("reproj pre-BA (clean): %.2f px" % e_pre)

    ba = vo_bundle.BundleAdjuster(K, Rs, ts, oa_clean, pt_idx_clean,
                                  max_iter=60, fixed=set(range(6)), rho=6.0)
    for pid, j in pid_to_j.items():
        ba.X[j] = mapp[pid]["X"].copy()
    cost = ba.solve()
    e_post = ba_error_sub(ba.Rs, ba.ts, oa_clean, ba.X)
    print("reproj post-BA: %.2f px" % e_post)
    print("  BA internal: cost=%.3f -> rms=%.2f px over %d obs"
          % (cost, float(np.sqrt(cost / (2 * len(oa_clean)))),
             len(oa_clean)))

    # ---- trajectory output (pre/post BA camera centers) ----
    def center(R, t):
        c = -R.T @ np.asarray(t).reshape(3, 1)
        return c[0, 0], c[1, 0], c[2, 0]

    with open(args.out, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["kf", "frame", "pre_x", "pre_y", "pre_z",
                     "post_x", "post_y", "post_z"])
        for i, (R0, t0, R1, t1) in enumerate(
                zip(Rs, ts, ba.Rs, ba.ts)):
            wr.writerow([i, kfs[i]] + list(center(R0, t0)) + list(center(R1, t1)))
    print("wrote %s" % args.out)

    # ---- validation sidecar: reproj errors for validate_traj_pass.py ----
    import json
    val = {"reproj_pre_px": float(e_pre),
           "reproj_post_px": float(e_post),
           "n_obs": int(len(oa_clean)),
           "n_pts": int(len(pt_idx_clean))}
    val_path = args.out.replace(".csv", "_val.json")
    with open(val_path, "w") as f:
        json.dump(val, f, indent=2)
    print("wrote %s" % val_path)


if __name__ == "__main__":
    main()