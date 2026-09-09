import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vo_core

IMG_W, IMG_H = 640, 480
FX = 680.0
K = np.array([[FX, 0.0, IMG_W / 2.0],
              [0.0, FX, IMG_H / 2.0],
              [0.0, 0.0, 1.0]])

LK_PARAMS = dict(winSize=(25, 25), maxLevel=3,
                 criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                           30, 0.01))


def make_scene(rng):
    n = 1200
    z = np.exp(rng.uniform(np.log(2.2), np.log(30), n))
    u = rng.uniform(0, IMG_W, n)
    v = rng.uniform(0, IMG_H, n)
    x = (u - K[0, 2]) / K[0, 0] * z
    y = (v - K[1, 2]) / K[1, 1] * z
    return np.stack([x, y, z], axis=1).T


def render(gray, pts_world, R_wc, t_wc, rng, noise_sigma):
    X_c = R_wc @ pts_world + t_wc
    z = X_c[2, :]
    keep = z > 0.4
    if np.count_nonzero(keep) < 20:
        gray[:] = 0
        return
    u = K[0, 0] * (X_c[0, keep] / z[keep]) + K[0, 2]
    v = K[1, 1] * (X_c[1, keep] / z[keep]) + K[1, 2]
    vis = (u >= 0) & (u < IMG_W) & (v >= 0) & (v < IMG_H)
    uv = np.round(np.stack([u[vis], v[vis]], axis=1)).astype(int)
    gray[:] = 0
    for k in range(len(uv)):
        px, py = uv[k]
        glow = int(rng.integers(120, 256))
        rad = int(max(1, round(rng.uniform(2, 5))))
        cv2.circle(gray, (int(px), int(py)), rad, glow, -1, cv2.LINE_AA)
    cv2.GaussianBlur(gray, (5, 5), 0, gray)
    if rng is not None:
        gray += rng.normal(0.0, noise_sigma, gray.shape).astype(np.float32)
    return gray


def ryaw(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, 0.0, s],
                     [0.0, 1.0, 0.0],
                     [-s, 0.0, c]])


def rotation_error_deg(R_est, R_gt):
    cos = (np.trace(R_gt.T @ R_est) - 1.0) / 2.0
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def umeyama(src, dst):
    n = max(src.shape[0], 2)
    mu_s = src.mean(axis=0)
    mu_d = dst.mean(axis=0)
    S_mat = (dst - mu_d).T @ (src - mu_s) / n
    U, D, Vt = np.linalg.svd(S_mat)
    sign = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        sign[2, 2] = -1.0
    R = U @ sign @ Vt
    denom = np.mean(np.sum((src - mu_s) ** 2, axis=1)) + 1e-9
    scale = np.trace(np.diag(D) @ sign) / denom
    t = mu_d - scale * R @ mu_s
    return scale, R, t


def run_consistent_map(gt_Rs, gt_ts, scene, n_frames, K, lk_params,
                       disp_thresh, max_corners, min_track):
    """Self-consistent monocular local-map frontend.

    Runs its own LK tracking, picks keyframes by accumulated flow from the
    previous keyframe, and solves each keyframe's pose from the SAME matched
    correspondences it uses to build the 3D map (essential matrix for the
    first baseline, then PnP to the accumulated map). Bundle adjustment fed
    from here therefore sees poses and observations that agree.

    Returns kf_idx (frame indices), kf_pose (world->cam R, t), and obs dict
    track_id -> [(keyframe_slot, u, v), ...].
    """
    rng = np.random.default_rng(12345)
    import vo_bundle
    gray = np.zeros((IMG_H, IMG_W), np.float32)
    prev_gray = None
    prev_pts = None
    kf_idx = []
    kf_pose = []          # (R_cur2w, t_cur2w) in current frontend's frame
    active = []           # list of track ids currently tracked
    track_xy = []         # track id -> latest 2D pos
    track_kf = []         # track id -> list of (keyframe_slot, u, v)
    R_acc = np.eye(3)
    t_acc = np.zeros((3, 1))
    map_X = []            # world 3D points
    map_track = []        # track id for each map point

    def kf_snap(slot):
        for t in active:
            track_kf[t].append((slot, track_xy[t][0], track_xy[t][1]))

    def triangulate_active():
        added = 0
        for t in active:
            if t in map_track:
                continue
            if len(track_kf[t]) >= 2:
                s0, u0, v0 = track_kf[t][0]
                s1, u1, v1 = track_kf[t][1]
                Rs0, ts0 = kf_pose[s0][0], kf_pose[s0][1]
                Rs1, ts1 = kf_pose[s1][0], kf_pose[s1][1]
                X = vo_bundle.triangulate(
                    K, Rs0, ts0, Rs1, ts1,
                    np.array([[u0], [v0]]),
                    np.array([[u1], [v1]]))
                map_X.append(X)
                map_track.append(t)
                added += 1
        return added

    slot = 0
    for i in range(n_frames):
        render(gray, scene, gt_Rs[i], gt_ts[i].reshape(3, 1), rng, 0.0)
        frame_u8 = np.clip(gray, 0, 255).astype(np.uint8)
        if prev_gray is None or prev_pts is None or len(active) < min_track:
            new_pts = vo_core.good_features(frame_u8, max_corners, 0.01, 8, 5)
            if new_pts is None or len(new_pts) < min_track:
                prev_gray = frame_u8.copy()
                continue
            new_pts = new_pts.reshape(-1, 2)
            if not active:
                active = list(range(len(new_pts)))
                track_xy = list(new_pts)
                track_kf = [[] for _ in new_pts]
            else:
                keep = active
                track_xy = [track_xy[t] for t in keep]
                track_kf = [track_kf[t] for t in keep]
                active = list(range(len(track_xy)))
                for p in new_pts:
                    track_xy.append(p)
                    track_kf.append([])
                    active.append(len(track_xy) - 1)
            prev_gray = frame_u8.copy()
            prev_pts = new_pts.copy().reshape(-1, 1, 2)
            if not kf_pose:
                kf_idx.append(i)
                kf_pose.append((np.eye(3), np.zeros(3)))
                kf_snap(0)
                slot = 1
            continue

        good_old, good_new = vo_core.track_points(prev_gray, prev_pts,
                                                  frame_u8, lk_params)
        next_active = []
        for a, (o, n) in enumerate(zip(good_old, good_new)):
            if np.linalg.norm(n - o) < 150:
                tid = active[a]
                track_xy[tid] = n.ravel().copy()
                next_active.append(tid)
        active = next_active
        if not active:
            prev_gray = frame_u8.copy()
            prev_pts = None
            prev_pts = None
            continue

        lastslot = slot - 1
        lastxy = {}
        for t in active:
            for (s, u, v) in track_kf[t]:
                if s == lastslot:
                    lastxy[t] = (u, v)
        disp = 0.0
        cnt = 0
        for t in active:
            if t in lastxy:
                disp += np.linalg.norm(np.array(track_xy[t]) -
                                       np.array(lastxy[t]))
                cnt += 1
        disp = disp / max(cnt, 1)

        if disp < disp_thresh:
            prev_gray = frame_u8.copy()
            prev_pts = good_new.copy()
            continue

        if len(kf_pose) == 1:
            shared = [(lastxy[t], track_xy[t]) for t in active if t in lastxy]
            if len(shared) >= 5:
                old_2d = np.array([p[0] for p in shared], np.float32)
                new_2d = np.array([p[1] for p in shared], np.float32)
                res, _info = vo_core.estimate_pose(old_2d, new_2d, K)
                if res is not None:
                    R_rel, t_rel, old_in, new_in = res
                    R_acc, t_acc = vo_core.update_pose(R_acc, t_acc, R_rel,
                                                       t_rel, 1.0)
                    kf_idx.append(i)
                    kf_pose.append((R_acc.copy(), t_acc.copy().ravel()))
                    kf_snap(slot)
                    slot += 1
                    triangulate_active()
                else:
                    prev_gray = frame_u8.copy()
            else:
                prev_gray = frame_u8.copy()
        else:
            # PnP to the accumulated map, then triangulate new tracks
            obj = []
            img = []
            for t in active:
                if t in map_track:
                    mi = map_track.index(t)
                    obj.append(map_X[mi])
                    img.append(track_xy[t])
            if len(obj) >= 6:
                obj = np.array(obj, np.float64).reshape(-1, 3)
                img = np.array(img, np.float64).reshape(-1, 1, 2)
                ok, rvec, tvec = cv2.solvePnP(obj, img, K, None,
                                              flags=cv2.SOLVEPNP_ITERATIVE)
                if ok:
                    R_cur, _ = cv2.Rodrigues(rvec)
                    t_cur = tvec.ravel()
                    kf_idx.append(i)
                    kf_pose.append((R_cur, t_cur))
                    kf_snap(slot)
                    slot += 1
                    triangulate_active()
            else:
                prev_gray = frame_u8.copy()

        prev_gray = frame_u8.copy()
        prev_pts = good_new.copy()

    obs = {}
    for t in range(len(track_kf)):
        if len(track_kf[t]) >= 2:
            obs[t] = list(track_kf[t])
    return kf_idx, kf_pose, obs, map_X




def main():
    parser = argparse.ArgumentParser(
        description="Synthetic VO test: renders a virtual camera touring a known "
                    "trajectory and checks vo_core's math against ground truth.")
    parser.add_argument("--frames", type=int, default=130)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--noise", type=float, default=3.0)
    parser.add_argument("--maxCorners", type=int, default=300)
    parser.add_argument("--minTrack", type=int, default=40)
    parser.add_argument("--minInliers", type=int, default=12)
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--no-lk", action="store_true",
                        help="use exact projected correspondences instead of "
                             "optical flow, to isolate LK error from math error")
    parser.add_argument("--keyframe", action="store_true",
                        help="drive vo_core.KeyframeMonoVO (baseline between "
                             "keyframes) instead of the per-frame loop")
    parser.add_argument("--kf-disp", type=float, default=4.0,
                        help="keyframe flow threshold in pixels")
    parser.add_argument("--bundle", action="store_true",
                        help="run bundle adjustment over the keyframes after "
                             "the sequential pass (uses scene-projected "
                             "observations, isolating the optimizer from the "
                             "frontend)")
    parser.add_argument("--bundle-points", type=int, default=120,
                        help="max 3D points used in the bundle adjustment")
    parser.add_argument("--bundle-noise", type=float, default=0.6,
                        help="pixel Gaussian noise added to the bundled "
                             "observations, mimicking frontend LK noise")
    parser.add_argument("--inject-scale-drift", type=float, default=0.0,
                        help="fractional scale drift per keyframe applied to "
                             "the frontend translations before bundle "
                             "adjustment, i.e. |t_k| *= (1+drift)^k. Simulates "
                             "monocular scale drift that BA should remove.")
    parser.add_argument("--fix-first-pose", action="store_true",
                        help="hold keyframe 0's full pose fixed during bundle "
                             "adjustment, anchoring the otherwise scale-degenerate "
                             "monocular gauge so injected drift is truly penalised")
    parser.add_argument("--anchor-points", type=int, default=0,
                        help="number of scene points treated as known 3D "
                             "landmarks (absolute position anchor) during bundle "
                             "adjustment, giving BA a metric reference to remove "
                             "injected scale drift")
    parser.add_argument("--anchor-w", type=float, default=1.0,
                        help="residual weight on the known-landmark anchor term")
    parser.add_argument("--ba-lk", action="store_true",
                        help="feed bundle adjustment with real multi-view LK "
                             "feature tracks (a local map) instead of "
                             "GT-projected observations. Requires --keyframe.")
    parser.add_argument("--ba-lk2", action="store_true",
                        help="run a self-consistent local-map frontend (its own "
                             "LK tracking + E/PnP posing from the SAME feature "
                             "correspondences) and feed that to bundle "
                             "adjustment, so frontend poses and backend "
                             "observations agree")
    parser.add_argument("--ba-kf-disp", type=float, default=4.0,
                        help="flow threshold used by the consistent local-map "
                             "frontend (--ba-lk2); higher spreads keyframes out "
                             "and speeds up bundle adjustment")
    parser.add_argument("--robust", type=float, default=0.0,
                        help="cauchy robust-loss parameter for the bundle "
                             "adjustment; >0 down-weights gross outlier "
                             "observations (typical value ~ a few pixels)")
    parser.add_argument("--lm", action="store_true",
                        help="run the LocalMapVO local-map frontend (its own "
                             "LK + PnP local map) and feed its map points & "
                             "multi-keyframe observations to bundle adjustment")
    parser.add_argument("--lm-kf-disp", type=float, default=4.0,
                        help="flow threshold for LocalMapVO keyframes")
    parser.add_argument("--lm-min-parallax", type=float, default=0.5,
                        help="minimum triangulation parallax (deg) for the "
                             "LocalMapVO map")
    parser.add_argument("--lm-min-track", type=int, default=10,
                        help="minimum surviving feature count before the "
                             "LocalMapVO starts replenishing (default 10; the "
                             "generic --minTrack default 40 is too aggressive "
                             "for the local-map frontend)")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    scene = make_scene(rng)

    centers = []
    yaws_deg = []
    R_wc_list = []
    t_wc_list = []
    c = np.zeros(3)
    yaw = 0.0
    for i in range(args.frames):
        if i < 50:
            c = c + np.array([0.04, 0.0, 0.06])
        elif i < 110:
            yaw = yaw + 0.005
            c = c + np.array([0.02, 0.0, 0.06])
        else:
            yaw = yaw - 0.002
            c = c + np.array([-0.02, 0.01, 0.06])
        centers.append(c.copy())
        yaws_deg.append(np.degrees(yaw))
        R_wc_list.append(ryaw(yaw))
        t_wc_list.append(-R_wc_list[-1] @ c)

    path_len = 0.0
    for i in range(1, args.frames):
        path_len = path_len + np.linalg.norm(centers[i] - centers[i - 1])

    gt_centers = np.array(centers)
    gt_Rs = R_wc_list
    gt_ts = t_wc_list

    gray = np.zeros((IMG_H, IMG_W), np.float32)
    prev_pts = None
    prev_gray = None
    est_R = np.eye(3)
    est_t = np.zeros((3, 1))
    est_metric = []
    est_shape = []
    rot_errs = []
    diag_t_err = []
    all_disp = []
    e_none = 0
    pose_fail = 0
    last_R_rel = None
    rejected_rot = 0
    rejected_inliers = 0
    rejected_disp = 0
    accepted = 0

    if args.keyframe or args.lm:
        if args.lm:
            import vo_local_map
            lm_vo = vo_local_map.LocalMapVO(
                K, max_corners=args.maxCorners, min_track=args.lm_min_track,
                keyframe_disp=args.lm_kf_disp,
                min_parallax=args.lm_min_parallax)
        else:
            vo = vo_core.KeyframeMonoVO(
                K, scale=1.0, max_corners=args.maxCorners, quality=0.01,
                min_distance=8, block_size=5, min_track=args.minTrack,
                min_inliers=args.minInliers, keyframe_disp=args.kf_disp,
                max_rot_step_deg=10.0)
        kf_idx = []
        kf_poses = []
        prv_R = None
        prv_center = None
        prv_frame = None
        ba_obs = []
        ba_track_pts = []
        ba_track_kf = []
        ba_alive = []
        for i in range(args.frames):
            render(gray, scene, gt_Rs[i], gt_ts[i].reshape(3, 1), rng,
                   args.noise)
            frame_u8 = np.clip(gray, 0, 255).astype(np.uint8)
            if args.ba_lk:
                if len(ba_alive) < args.minTrack:
                    new_pts = vo_core.good_features(
                        frame_u8, args.maxCorners, 0.01, 8, 5).reshape(-1, 2)
                    if not len(ba_alive):
                        ba_track_pts = list(new_pts)
                        ba_track_kf = [[] for _ in new_pts]
                        ba_alive = list(range(len(new_pts)))
                    else:
                        alive_ids = list(ba_alive)
                        ba_track_pts = [ba_track_pts[a] for a in alive_ids]
                        ba_track_kf = [ba_track_kf[a] for a in alive_ids]
                        ba_alive = list(range(len(ba_track_pts)))
                        for p in new_pts:
                            ba_track_pts.append(p)
                            ba_track_kf.append([])
                            ba_alive.append(len(ba_track_pts) - 1)
                    ba_prev_gray = frame_u8.copy()
                else:
                    old_pts = np.array(
                        [ba_track_pts[a] for a in ba_alive],
                        np.float32).reshape(-1, 1, 2)
                    good_old, good_new = vo_core.track_points(
                        ba_prev_gray, old_pts, frame_u8, LK_PARAMS)
                    new_alive = []
                    for a, (o, n) in enumerate(zip(good_old, good_new)):
                        disp = np.linalg.norm(n - o)
                        if disp < 150:
                            tid = ba_alive[a]
                            ba_track_pts[tid] = n.ravel().copy()
                            new_alive.append(tid)
                    ba_alive = new_alive
                    ba_prev_gray = frame_u8.copy()
            if args.lm:
                info = lm_vo.step(i, frame_u8, LK_PARAMS)
                if i == args.frames - 1:
                    import os
                    if os.environ.get("LM_DEBUG"):
                        print("LMDBG kf_idx=%s" % lm_vo.kf_idx)
                all_disp.append(info.get("disp", 0.0))
                if info["kf"] and (not kf_idx or
                                   len(lm_vo.kf_idx) > len(kf_idx)):
                    k = len(lm_vo.kf_idx) - 1
                    R_cw = lm_vo.Rs[k]
                    t_cw = lm_vo.ts[k]
                    kf_idx.append(lm_vo.kf_idx[k])
                    kf_poses.append((R_cw.copy(),
                                     np.asarray(t_cw).ravel().copy()))
                    center = (-R_cw.T @ np.asarray(t_cw).ravel()).ravel()
                    est_metric.append(center)
                    accepted += 1
                    if prv_R is not None:
                        Rstep = R_cw @ prv_R.T
                        Rgt = gt_Rs[i] @ gt_Rs[prv_frame].T
                        rot_errs.append(rotation_error_deg(Rstep, Rgt))
                        te = center - prv_center
                        tg = gt_centers[i] - gt_centers[prv_frame]
                        te = te / max(np.linalg.norm(te), 1e-12)
                        tg = tg / max(np.linalg.norm(tg), 1e-12)
                        diag_t_err.append(float(np.degrees(np.arccos(np.clip(
                            abs(np.dot(te, tg)), 0.0, 1.0)))))
                    prv_R = R_cw.copy()
                    prv_center = center
                    prv_frame = i
                continue
            updated, R_cw, t_cw, info = vo.step(frame_u8, LK_PARAMS)
            all_disp.append(info["disp"])
            if not updated:
                continue
            if args.ba_lk:
                for tid in ba_alive:
                    ba_track_kf[tid].append((i, ba_track_pts[tid][0],
                                             ba_track_pts[tid][1]))
            center = (-R_cw.T @ t_cw).ravel()
            kf_idx.append(i)
            kf_poses.append((R_cw.copy(), t_cw.copy()))
            est_metric.append(center)
            accepted += 1
            if prv_R is not None:
                Rstep = R_cw @ prv_R.T
                Rgt = gt_Rs[i] @ gt_Rs[prv_frame].T
                rot_errs.append(rotation_error_deg(Rstep, Rgt))
                te = center - prv_center
                tg = gt_centers[i] - gt_centers[prv_frame]
                te = te / max(np.linalg.norm(te), 1e-12)
                tg = tg / max(np.linalg.norm(tg), 1e-12)
                diag_t_err.append(float(np.degrees(np.arccos(np.clip(
                    abs(np.dot(te, tg)), 0.0, 1.0)))))
            prv_R = R_cw.copy()
            prv_center = center
            prv_frame = i
            if args.show:
                cv2.imshow("synthetic frame", frame_u8)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        if args.show:
            cv2.destroyAllWindows()
        est_shape = est_metric
        start, stop = 0, 0
    else:
        start = 1 if args.no_lk else 0
        stop = args.frames
    for i in range(start, stop):
        render(gray, scene, gt_Rs[i], gt_ts[i].reshape(3, 1), rng, args.noise)
        frame_u8 = np.clip(gray, 0, 255).astype(np.uint8)

        if args.no_lk:
            Xc1 = gt_Rs[i - 1] @ scene + gt_ts[i - 1].reshape(3, 1)
            Xc2 = gt_Rs[i] @ scene + gt_ts[i].reshape(3, 1)
            vis1 = Xc1[2, :] > 0.4
            vis2 = Xc2[2, :] > 0.4
            uv1 = np.stack([K[0, 0] * Xc1[0, :] / Xc1[2, :] + K[0, 2],
                            K[1, 1] * Xc1[1, :] / Xc1[2, :] + K[1, 2]], axis=1)
            uv2 = np.stack([K[0, 0] * Xc2[0, :] / Xc2[2, :] + K[0, 2],
                            K[1, 1] * Xc2[1, :] / Xc2[2, :] + K[1, 2]], axis=1)
            vis1 &= (uv1[:, 0] > 0) & (uv1[:, 0] < IMG_W) & (uv1[:, 1] > 0) & (uv1[:, 1] < IMG_H)
            vis2 &= (uv2[:, 0] > 0) & (uv2[:, 0] < IMG_W) & (uv2[:, 1] > 0) & (uv2[:, 1] < IMG_H)
            vis = vis1 & vis2
            good_old = uv1[vis].astype(np.float32)[:, None, :]
            good_new = uv2[vis].astype(np.float32)[:, None, :]
            prev_pts = None
            prev_gray = None
        else:
            if prev_pts is None or len(prev_pts) < args.minTrack:
                prev_pts = vo_core.good_features(frame_u8, args.maxCorners, 0.01,
                                                 8, 5)
                prev_gray = frame_u8.copy()
                continue

            good_old, good_new = vo_core.track_points(prev_gray, prev_pts,
                                                      frame_u8, LK_PARAMS)
            if len(good_old) < args.minInliers:
                prev_pts = None
                rejected_inliers += 1
                continue

        res, info = vo_core.estimate_pose(good_old, good_new, K)
        if res is None:
            e_none += info["reset"]
            pose_fail += not info["reset"]
            if info["reset"]:
                prev_pts = None
            continue
        R_rel, t_rel, old_in, new_in = res
        all_disp.append(info["disp"])

        if info["inliers"] < args.minInliers:
            rejected_inliers += 1
            continue
        if info["disp"] < 1.0:
            rejected_disp += 1
            continue
        if not vo_core.motion_consistent(R_rel, last_R_rel, 10.0):
            rejected_rot += 1
            continue
        last_R_rel = R_rel.copy()

        R_gt = gt_Rs[i] @ gt_Rs[i - 1].T
        t_gt = gt_ts[i].reshape(3, 1) - R_gt @ gt_ts[i - 1].reshape(3, 1)
        rot_errs.append(rotation_error_deg(R_rel, R_gt))
        t_hat = t_rel.ravel()
        t_hat = t_hat / max(np.linalg.norm(t_hat), 1e-12)
        t_gt_hat = t_gt.ravel()
        t_gt_hat = t_gt_hat / max(np.linalg.norm(t_gt_hat), 1e-12)
        diag_t_err.append(float(np.degrees(np.arccos(np.clip(
            abs(np.dot(t_hat, t_gt_hat)), 0.0, 1.0)))))

        true_scale = float(np.linalg.norm(t_gt))
        est_R, est_t = vo_core.update_pose(est_R, est_t, R_rel, t_rel,
                                           true_scale)
        cam = (-est_R.T @ est_t).ravel()
        est_metric.append(cam)

        if accepted == 0:
            shape_R = R_rel
            shape_t = t_rel
        else:
            shape_R = R_rel @ shape_R
            shape_t = t_rel + R_rel @ shape_t
        shape_cam = (-shape_R.T @ shape_t).ravel()
        est_shape.append(shape_cam)

        accepted += 1

        prev_gray = frame_u8.copy()
        prev_pts = new_in.reshape(-1, 1, 2)

        if args.show:
            cv2.imshow("synthetic frame", frame_u8)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    if args.show:
        cv2.destroyAllWindows()

    if not est_metric or not rot_errs:
        print("FAILED: no poses accepted by the pipeline")
        raise SystemExit(1)

    est_metric = np.array(est_metric)
    est_shape = np.array(est_shape)
    if args.keyframe or args.lm:
        gt_aligned = gt_centers[kf_idx]
        metric_rmse = float("nan")
    else:
        gt_aligned = gt_centers[:len(est_metric)]

    rot = np.array(rot_errs)
    t_err = np.array(diag_t_err)
    if not (args.keyframe or args.lm):
        metric_rmse = float(np.sqrt(np.mean(np.sum((est_metric - gt_aligned)
                                                   ** 2, axis=1))))
    s, R, t = umeyama(est_shape, gt_aligned)
    aligned = s * est_shape @ R.T + t
    shape_rmse = float(np.sqrt(np.mean(np.sum((aligned - gt_aligned) ** 2,
                                              axis=1))))

    if args.keyframe or args.lm:
        step = (args.frames - 1) / max(accepted - 1, 1)
        print("path length: %.2f m   keyframes: %d (mean step %.1f frames)" %
              (path_len, accepted, step))
    else:
        print("path length: %.2f m   accepted poses: %d / %d (%.1f%%)" %
              (path_len, accepted, args.frames - 1,
               100.0 * accepted / max(args.frames - 1, 1)))
        print("rejected: reset=%d  low-track=%d  low-disp=%d  rotation-gate=%d"
              % (e_none + pose_fail, rejected_inliers, rejected_disp,
                 rejected_rot))
        print("  reset split: findEssentialMat none=%d  recoverPose fail=%d"
              % (e_none, pose_fail))
    if all_disp:
        a = np.array(all_disp)
        print("disp over all frames: min %.2f  mean %.2f  median %.2f  max %.2f"
              % (a.min(), a.mean(), np.median(a), a.max()))
    print("relative rotation error: mean %.2f deg  median %.2f deg  p95 %.2f deg"
          % (rot.mean(), np.median(rot), np.percentile(rot, 95)))
    print("translation direction error: mean %.2f deg  median %.2f deg  p95 %.2f deg"
          % (t_err.mean(), np.median(t_err), np.percentile(t_err, 95)))
    print("no-scale shape RMSE after alignment: %.3f m (%.1f%% of path)"
          % (shape_rmse, 100.0 * shape_rmse / path_len))
    if args.keyframe or args.lm:
        print("metric RMSE: n/a (keyframe scale-injected per step not applied)")
    else:
        print("metric trajectory RMSE (true scale injected), informational: "
              "%.3f m (%.1f%% of path)" % (metric_rmse,
                                           100.0 * metric_rmse / path_len))

    ok = True
    if args.keyframe or args.lm:
        if accepted < 30:
            print("FAIL: fewer than 30 keyframes produced")
            ok = False
    elif accepted < (args.frames - 1) * 0.5:
        print("FAIL: fewer than half the frames accepted")
        ok = False
    if np.percentile(rot, 95) > 2.0:
        print("FAIL: p95 rotation error above 2 deg")
        ok = False
    if shape_rmse / path_len > 0.08:
        print("FAIL: shape RMSE above 8% of path")
        ok = False
    if ok:
        print("PASS")
    elif not args.bundle:
        raise SystemExit(1)

    if args.show:
        import matplotlib.pyplot as plt
        plt.plot(gt_aligned[:, 2], gt_aligned[:, 1], "k-", label="ground truth")
        plt.plot(aligned[:, 2], aligned[:, 1], "b--", label="estimated (shape)")
        if not (args.keyframe or args.lm):
            plt.plot(est_metric[:, 2], est_metric[:, 1], "r-",
                     label="estimated (metric)")
        plt.gca().set_aspect("equal")
        plt.legend()
        plt.title("synthetic VO result, seed %d%s" %
                  (args.seed, " [keyframe]" if (args.keyframe or args.lm)
                   else ""))
        plt.xlabel("z")
        plt.ylabel("x")
        plt.show()

    if args.bundle and (args.keyframe or args.lm) and len(kf_idx) >= 2:
        import vo_bundle

        kf_slot = {fi: k for k, fi in enumerate(kf_idx)}

        candidates = []
        if args.ba_lk2:
            ckf_idx, ckf_pose, cobs, cmap_X = run_consistent_map(
                gt_Rs, gt_ts, scene, args.frames, K, LK_PARAMS,
                args.ba_kf_disp, args.maxCorners, args.minTrack)
            kf_idx = ckf_idx
            kf_poses = [p for p in ckf_pose if p is not None]
            gt_aligned = gt_centers[kf_idx]
            for tid, obs in cobs.items():
                candidates.append((scene[:, 0].copy(), list(obs)))
            print("ba-lk2 consistent map: %d keyframes, %d map tracks, "
                  "%d triangulated points"
                  % (len(kf_idx), len(cobs), len(cmap_X)))
            ba_consistent = True
        else:
            ba_consistent = False
        if args.lm and not args.ba_lk2:
            lm_vo = locals().get("lm_vo")
            if lm_vo is None or not lm_vo.map:
                print("lm: no LocalMapVO run found; cannot bundle")
                ba_consistent = False
            else:
                kf_idx = lm_vo.kf_idx
                kf_poses = [(lm_vo.Rs[k].copy(),
                             np.asarray(lm_vo.ts[k]).ravel().copy())
                            for k in range(len(kf_idx))]
                gt_aligned = gt_centers[kf_idx]
                for pid, m in lm_vo.map.items():
                    if m["X"] is None:
                        continue
                    obs = [(s, u, v) for (s, u, v) in m["obs"]
                           if 0 <= s < len(kf_idx)]
                    if len(obs) >= 2:
                        candidates.append((m["X"].copy(), obs))
                print("lm: LocalMapVO %d keyframes, %d map points, %d "
                      "tri-tracks" % (len(kf_idx), len(candidates),
                                      sum(1 for m in lm_vo.map.values()
                                          if m["X"] is not None)))
                ba_consistent = True
        if args.ba_lk:
            track_map = {}
            for k, i in enumerate(kf_idx):
                for tid in range(len(ba_track_kf)):
                    for (fi, u, v) in ba_track_kf[tid]:
                        if fi == i:
                            track_map.setdefault(tid, []).append((k, u, v))
            for tid, obs in track_map.items():
                if len(obs) >= 2:
                    candidates.append((scene[:, 0].copy(), obs))
            print("ba-lk: %d local-map points across %d keyframes" %
                  (len(candidates), len(kf_idx)))
        for j in range(scene.shape[1]):
            if args.ba_lk or args.ba_lk2:
                break
            Xw = scene[:, j]
            obs = []
            for k, i in enumerate(kf_idx):
                R, t = kf_poses[k]
                Xc = R @ Xw + t.ravel()
                z = Xc[2]
                if z <= 0.4:
                    continue
                u = K[0, 0] * Xc[0] / z + K[0, 2]
                v = K[1, 1] * Xc[1] / z + K[1, 2]
                if 0 <= u < IMG_W and 0 <= v < IMG_H:
                    if args.bundle_noise:
                        u = u + rng.normal(0.0, args.bundle_noise)
                        v = v + rng.normal(0.0, args.bundle_noise)
                    obs.append((k, u, v))
            if len(obs) >= 2:
                candidates.append((Xw.copy(), obs))
        candidates.sort(key=lambda c: -len(c[1]))
        sel = candidates[:args.bundle_points]

        obs_rows = []
        pt_idx = []
        X_init = []
        kf_R = [p[0] for p in kf_poses]
        kf_t = [p[1] for p in kf_poses]
        if args.inject_scale_drift:
            drift = args.inject_scale_drift
            nk = max(len(kf_t) - 1, 1)
            kf_t = [tt * (1.0 + drift) ** (k / nk)
                    for k, tt in enumerate(kf_t)]
            print("scale drift injection: total scale growth %.1f%% "
                  "interpolated across %d keyframes" % (100.0 * drift, nk))

        for pi, (Xw, obs) in enumerate(sel):
            pt_idx.append(pi)
            best_a = best_b = None
            best_bl = -1.0
            for a in range(len(obs)):
                for b in range(a + 1, len(obs)):
                    bl = np.linalg.norm(kf_t[obs[a][0]] - kf_t[obs[b][0]])
                    if bl > best_bl:
                        best_bl = bl
                        best_a, best_b = a, b
            X3 = np.array([0.0, 0.0, 3.0])
            if ba_consistent and np.all(np.isfinite(Xw)) and \
                    abs(Xw[2]) < 1e4:
                X3 = Xw.astype(np.float64)
            elif best_a is not None:
                ka, ua, va = obs[best_a]
                kb, ub, vb = obs[best_b]
                o1 = np.array([[ua], [va]])
                o2 = np.array([[ub], [vb]])
                X3 = vo_bundle.triangulate(K, kf_R[ka], kf_t[ka].ravel(),
                                           kf_R[kb], kf_t[kb].ravel(),
                                           o1, o2)
            X_init.append(X3)
            for k, u, v in obs:
                obs_rows.append((k, pi, u, v))

        obs_arr = np.array(obs_rows, np.float64)

        anchors = None
        if args.anchor_points > 0:
            n_an = min(args.anchor_points, len(sel))
            anchors = [(pi, sel[pi][0].copy())
                       for pi in range(n_an)]

        fixed = set(range(6)) if args.fix_first_pose else None
        ba = vo_bundle.BundleAdjuster(K, kf_R, kf_t, obs_arr, pt_idx,
                                      fixed=fixed, anchors=anchors,
                                      anchor_w=args.anchor_w, rho=args.robust)
        if args.anchor_points > 0:
            print("anchors: %d known 3D landmarks, weight %.2f"
                  % (len(ba.anchors), args.anchor_w))
        X_init = np.array(X_init)
        for j in range(len(X_init)):
            ba.X[j] = X_init[j]
        r0 = ba._residual(ba._pack())
        rms = float(np.sqrt(np.mean(r0 ** 2))) if len(r0) else 0.0
        print("  initial residual: RMS %.2f px over %d observations"
              % (rms, len(r0) // 2))
        cost = ba.solve()

        aft = np.array([(-ba.Rs[i].T @ ba.ts[i]).ravel()
                        for i in range(len(kf_idx))])
        s2, R2, t2 = umeyama(aft, gt_aligned)
        aligned_aft = s2 * aft @ R2.T + t2
        shape_rmse_aft = float(np.sqrt(np.mean(np.sum(
            (aligned_aft - gt_aligned) ** 2, axis=1))))

        shape_rmse_before = shape_rmse
        if args.inject_scale_drift:
            drifted = np.array([(-kf_R[i].T @ kf_t[i]).ravel()
                                for i in range(len(kf_idx))])
            sb, Rb, tb = umeyama(drifted, gt_aligned)
            shape_rmse_before = float(np.sqrt(np.mean(np.sum(
                (sb * drifted @ Rb.T + tb - gt_aligned) ** 2, axis=1))))

        print("bundle adjustment: %d keyframes, %d points, %d observations, "
              "residual %.3f" % (len(kf_idx), len(sel), len(obs_arr), cost))
        print("  shape RMSE before: %.3f m (%.1f%% of path)" %
              (shape_rmse_before, 100.0 * shape_rmse_before / path_len))
        print("  shape RMSE after : %.3f m (%.1f%% of path)" %
              (shape_rmse_aft, 100.0 * shape_rmse_aft / path_len))
        if args.fix_first_pose:
            c0 = gt_aligned[0]
            gt_vec = gt_aligned[-1] - c0
            def_metric = np.linalg.norm(gt_vec)
            met_before = None
            if args.inject_scale_drift:
                drifted = np.array([(-kf_R[i].T @ kf_t[i]).ravel()
                                    for i in range(len(kf_idx))])
                met_before = np.linalg.norm(drifted[-1] - drifted[0])
            met_after = np.linalg.norm(aft[-1] - aft[0])
            line = ("  fixed-kf0 endpoint displacement: GT %.3f m" %
                    def_metric)
            if met_before is not None:
                line += " | before %.3f m (%.1f%%)" % (
                    met_before, 100.0 * met_before / def_metric)
            line += " | after %.3f m (%.1f%%)" % (
                met_after, 100.0 * met_after / def_metric)
            print(line)
        if args.show:
            import matplotlib.pyplot as plt
            plt.figure()
            plt.plot(gt_aligned[:, 2], gt_aligned[:, 1], "k-",
                     label="ground truth")
            plt.plot(aligned_aft[:, 2], aligned_aft[:, 1], "g-",
                     label="after BA")
            plt.gca().set_aspect("equal")
            plt.legend()
            plt.title("bundle adjustment, seed %d" % args.seed)
            plt.xlabel("z")
            plt.ylabel("x")
            plt.show()


if __name__ == "__main__":
    main()