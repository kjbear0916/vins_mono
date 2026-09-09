import cv2
import numpy as np

from vo_core import good_features, track_points, estimate_pose


def exp_so3(w):
    R, _ = cv2.Rodrigues(w)
    return R


def triangulate(K, R1, t1, R2, t2, o1, o2):
    P1 = K @ np.hstack([R1, t1.reshape(3, 1)])
    P2 = K @ np.hstack([R2, t2.reshape(3, 1)])
    X4 = cv2.triangulatePoints(P1, P2, o1.astype(np.float64),
                               o2.astype(np.float64))
    if X4[3] == 0:
        return None
    X = (X4[:3] / X4[3]).ravel()
    if (R1 @ X + t1)[2] < 0.1 or (R2 @ X + t2)[2] < 0.1:
        return None
    if not np.all(np.isfinite(X)) or abs(X[2]) > 1e4:
        return None
    return X


class LocalMapVO:
    """Gauge-stable sparse monocular local-map visual odometry.

    World frame is anchored at keyframe 0 (identity). Keyframe 1 closes the
    first baseline with an essential-matrix estimate; every later keyframe is
    localised by (robust) PnP against the already-triangulated map. Map points
    are held fixed by multi-view obs so poses cannot run away in scale the way
    per-frame E composition does.

    A short LK tracker is anchored at the most recent keyframe. When a frame
    can no longer keep the minimum track (or tracked flow never reaches the
    threshold) a new map segment begins; within a segment, tracked point ids
    accumulate per-keyframe 2D observations that triangulation consumes.

    Convention: world->cam, X_cam = R @ X_world + t; camera centre = -R.T @ t.
    """

    def __init__(self, K, max_corners=200, quality=0.01, min_distance=8,
                 block_size=5, min_track=10, keyframe_disp=4.0,
                 min_pnp=8, min_parallax=2.0, covis_frac=0.5,
                 pnp_thresh=3.0, pnp_min_obs=2, pnp_min_par=0.0):
        self.K = K
        self.max_corners = max_corners
        self.quality = quality
        self.min_distance = min_distance
        self.block_size = block_size
        self.min_track = min_track
        self.keyframe_disp = keyframe_disp
        self.min_pnp = min_pnp
        self.min_parallax = min_parallax
        self.covis_frac = covis_frac
        self.pnp_thresh = pnp_thresh
        self.pnp_min_obs = pnp_min_obs
        self.pnp_min_par = pnp_min_par

        self.kf_idx = []
        self.Rs = []
        self.ts = []

        self.map = {}          # pid -> {'X': np.array(3), 'obs': [(slot,u,v)]}

        self._kf_gray = None
        self._kf_pts = None
        self._track_id = []    # pid per tracked point
        self._seg0_slot = 0
        self._cur_slot = 0

    def _new_ids(self, n):
        base = self._next_pid()
        return list(range(base, base + n))

    def _next_pid(self):
        if self.map:
            return max(self.map) + 1
        return 0

    def _reset_tracker(self, gray):
        pts = good_features(gray, self.max_corners, self.quality,
                            self.min_distance, self.block_size)
        if pts is None:
            pts = np.empty((0, 1, 2), np.float32)
        self._kf_pts = pts
        self._kf_gray = gray
        self._track_id = self._new_ids(len(pts))
        return len(pts)

    def step(self, frame_no, gray, lk_params):
        info = {"kf": False, "tracked": 0, "pnp": 0, "nseg": 0, "newpts": 0,
                "frame": frame_no}
        if self._kf_gray is None:
            self._start_map(gray, frame_no)
            info["kf"] = True
            info["tracked"] = len(self._track_id)
            return info

        if self._kf_pts is None or len(self._kf_pts) == 0:
            self._begin_segment(gray, frame_no)
            info["kf"] = True
            info["nseg"] = 1
            return info

        old = self._kf_pts
        ids = self._track_id
        good_old, good_new = track_points(self._kf_gray, old, gray, lk_params)
        info["tracked"] = len(good_old)
        surv_ids = self._surviving_ids(old, good_old)
        if len(good_old) == 0:
            self._begin_segment(gray, frame_no)
            info["kf"] = True
            info["nseg"] = 1
            return info
        if len(good_old) < self.min_track:
            self._replenish_features(old, good_old, good_new, gray)
            return info

        disp = float(np.linalg.norm(good_new - good_old, axis=1).mean())
        info["disp"] = disp
        if disp < self.keyframe_disp:
            return info

        # current frame becomes a new keyframe
        if self._tri_map_count() < self.min_pnp or len(self.Rs) < 2:
            ok = self._first_baseline(good_old, good_new, surv_ids)
        else:
            ok = self._localise_pnp(good_new[:, 0, :], surv_ids)
        if not ok:
            self._kf_pts = good_new.copy()
            self._track_id = surv_ids
            self._kf_gray = gray.copy()
            info["pose_bad"] = True
            return info

        # pose secured: promote current frame to a keyframe
        self._cur_slot += 1
        for i, n in enumerate(good_new):
            pid = surv_ids[i]
            uv = n.ravel()
            mp = self.map.get(pid)
            if mp is not None:
                mp["obs"].append((self._cur_slot, uv[0].item(), uv[1].item()))
            else:
                self.map[pid] = {"X": None, "obs": [
                    (self._cur_slot, uv[0].item(), uv[1].item())], "par": 0.0}

        info["kf"] = True
        self.kf_idx.append(frame_no)
        info["newpts"] = self._triangulate_new()
        self._kf_pts = good_new.copy()
        self._track_id = surv_ids
        self._kf_gray = gray.copy()
        return info

    def _surviving_ids(self, old_pts, good_old):
        op = old_pts.reshape(-1, 2)
        go = good_old.reshape(-1, 2)
        out = []
        for gi in range(len(go)):
            u, v = go[gi]
            best = -1
            bd = 1e9
            for oi in range(len(op)):
                d = float(np.abs(op[oi, 0] - u) + np.abs(op[oi, 1] - v))
                if d < bd:
                    bd = d
                    best = oi
            if bd < 1.0 and best >= 0:
                out.append(self._track_id[best])
        return out

    def _start_map(self, gray, frame_no):
        self.Rs = [np.eye(3)]
        self.ts = [np.zeros(3)]
        self.kf_idx = [frame_no]
        self._cur_slot = 0
        n = self._reset_tracker(gray)
        for i in range(n):
            pid = self._track_id[i]
            uv = self._kf_pts[i].ravel()
            self.map[pid] = {"X": None, "obs": [
                (0, uv[0].item(), uv[1].item())], "par": 0.0}

    def _begin_segment(self, gray, frame_no):
        self.Rs.append(self.Rs[-1].copy())
        self.ts.append(self.ts[-1].copy())
        self.kf_idx.append(frame_no)
        self._cur_slot += 1
        self._reset_tracker(gray)

    def _replenish_features(self, old_pts, good_old, good_new, gray):
        op = old_pts.reshape(-1, 2)
        go = good_old.reshape(-1, 2)
        surv_ids = []
        for gi in range(len(go)):
            u, v = go[gi]
            best = -1
            bd = 1e9
            for oi in range(len(op)):
                d = float(np.abs(op[oi, 0] - u) + np.abs(op[oi, 1] - v))
                if d < bd:
                    bd = d
                    best = oi
            if bd < 1.0 and best >= 0:
                surv_ids.append(self._track_id[best])
        surv = good_new.reshape(-1, 1, 2).astype(np.float32)
        self._kf_pts = surv.copy()
        self._track_id = surv_ids
        self._kf_gray = gray.copy()
        if len(surv) < self.max_corners:
            new_pts = self._mask_detections(gray, surv,
                                            self.max_corners - len(surv))
            if new_pts is not None and len(new_pts):
                self._kf_pts = np.vstack([surv, new_pts]).astype(np.float32)
                self._track_id = self._track_id + self._new_ids(len(new_pts))
        self._kf_pts = self._kf_pts.reshape(-1, 1, 2)

    def _mask_detections(self, gray, survivors, n_room):
        if n_room <= 0:
            return None
        candidates = cv2.goodFeaturesToTrack(
            gray, maxCorners=n_room * 3, qualityLevel=self.quality,
            minDistance=self.min_distance,
            blockSize=self.block_size)
        if candidates is None or len(candidates) == 0:
            return None
        cand_xy = candidates.reshape(-1, 2)
        if survivors is not None and len(survivors):
            surv_xy = survivors.reshape(-1, 2)
            dist = np.linalg.norm(cand_xy[:, None, :] - surv_xy[None, :, :],
                                  axis=2)
            keep = dist.min(axis=1) >= self.min_distance
            cand_xy = cand_xy[keep]
            if len(cand_xy) == 0:
                return None
        return cand_xy[:n_room].reshape(-1, 1, 2).astype(np.float32)

    def _tri_map_count(self):
        return sum(1 for m in self.map.values() if m["X"] is not None)

    def _first_baseline(self, old, new, ids):
        res, _ = estimate_pose(old, new, self.K)
        if res is None:
            return False
        R_rel, t_rel, old_in, new_in = res
        t_rel = t_rel.ravel()
        # estimate_pose returns a cam->world motion (R_rel, t_rel).
        # LocalMap stores world->cam poses (X_cam = R X + t, C = -R.T t).
        # Convert: absolute new world->cam from current world->cam pose.
        R_old = self.Rs[-1]
        t_old = self.ts[-1]
        R_wc_old = R_old.T
        t_wc_old = -R_old.T @ t_old
        R_wc_new = R_rel @ R_wc_old
        t_wc_new = t_rel + R_rel @ t_wc_old
        R1 = R_wc_new.T
        t1 = (-R_wc_new.T @ t_wc_new).ravel()
        self.Rs.append(R1)
        self.ts.append(t1.copy())
        return True

    def _localise_pnp(self, new_uv, ids):
        obj = []
        img = []
        for i, uv in enumerate(new_uv):
            mp = self.map.get(ids[i])
            if mp is not None and mp["X"] is not None:
                if len(mp["obs"]) < self.pnp_min_obs:
                    continue
                if mp["par"] < self.pnp_min_par:
                    continue
                obj.append(mp["X"])
                img.append(uv)
        if len(obj) < self.min_pnp:
            info_getattr = getattr(self, "_dbg", None)
            if info_getattr is not None:
                info_getattr.append("pmiss:%d:%d" % (len(new_uv), len(obj)))
            return False
        obj = np.array(obj, np.float64).reshape(-1, 3)
        img = np.array(img, np.float64).reshape(-1, 1, 2)
        ok, rvec, tvec, inl = cv2.solvePnPRansac(
            obj, img, self.K, None, iterationsCount=100,
            reprojectionError=self.pnp_thresh, confidence=0.999,
            flags=cv2.SOLVEPNP_ITERATIVE)
        if not ok or inl is None or len(inl) < self.min_pnp:
            return False
        inliers = np.zeros(len(obj), bool)
        inliers[inl] = True
        R = exp_so3(rvec)
        t = tvec.ravel()
        ok2, rvec2, tvec2 = cv2.solvePnP(
            obj[inliers], img[inliers], self.K, None,
            flags=cv2.SOLVEPNP_ITERATIVE)
        if ok2:
            R = exp_so3(rvec2)
            t = tvec2.ravel()
        self.Rs.append(R)
        self.ts.append(t)
        return True

    def _triangulate_new(self):
        ntri = 0
        Rs = self.Rs
        ts = self.ts
        for pid, mp in self.map.items():
            if mp["X"] is not None:
                continue
            obs = mp["obs"]
            if len(obs) < 2:
                continue
            best = None
            best_par = -1.0
            for i in range(len(obs)):
                for j in range(i + 1, len(obs)):
                    s0, u0, v0 = obs[i]
                    s1, u1, v1 = obs[j]
                    if s0 == s1 or s0 >= len(Rs) or s1 >= len(Rs):
                        continue
                    X = triangulate(self.K, Rs[s0], ts[s0], Rs[s1], ts[s1],
                                    np.array([[u0], [v0]]),
                                    np.array([[u1], [v1]]))
                    if X is None:
                        continue
                    C0 = -Rs[s0].T @ ts[s0]
                    C1 = -Rs[s1].T @ ts[s1]
                    r0 = X - C0
                    r1 = X - C1
                    n0 = np.linalg.norm(r0)
                    n1 = np.linalg.norm(r1)
                    if n0 < 1e-9 or n1 < 1e-9:
                        continue
                    cos = float(np.dot(r0, r1) / (n0 * n1))
                    par = float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))
                    if par > best_par:
                        best_par = par
                        best = (X, par)
            if best is None or best_par < self.min_parallax:
                continue
            mp["X"] = best[0]
            mp["par"] = best[1]
            ntri += 1
        return ntri
