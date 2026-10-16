"""Appearance-based loop closure for the monocular VO pipeline.

Two independent pieces:

* Place recognition -- ORB descriptors per keyframe, brute-force Hamming
  ratio matching, and an essential-matrix geometric verification that
  yields the relative pose of a candidate pair.
* Pose-graph optimisation over SE(3) -- Levenberg-Marquardt with
  numerical Jacobians (same style as vo_bundle.BundleAdjuster).  Nodes are
  keyframe camera poses in the world->cam convention shared by the rest of
  the codebase (X_cam = R @ X_world + t, camera centre C = -R.T @ t).

A loop edge carries the recovered relative rotation, the unit relative
translation direction, and a scale supplied by the caller (monocular
translation magnitude is unobservable from an essential matrix alone).
"""

import numpy as np
import cv2

__all__ = [
    "exp_so3", "log_so3", "relative_pose", "camera_center",
    "orb_features", "match_ratio", "verify_relpose",
    "PlaceRecognizer", "detect_loops", "LoopEdge",
    "PoseGraphSE3", "umeyama_sim3", "align_ate",
]


def exp_so3(w):
    R, _ = cv2.Rodrigues(np.asarray(w, dtype=np.float64).reshape(3, 1))
    return R


def log_so3(R):
    w, _ = cv2.Rodrigues(np.asarray(R, dtype=np.float64))
    return w.ravel()


def relative_pose(R_i, t_i, R_j, t_j):
    """X_j = dR @ X_i + dt  for poses in the world->cam convention."""
    dR = R_j @ R_i.T
    dt = t_j - dR @ t_i
    return dR, dt


def camera_center(R, t):
    return -np.asarray(R, float).T @ np.asarray(t, float).ravel()


def orb_features(gray, nfeatures=500, fast_threshold=12):
    orb = cv2.ORB_create(nfeatures=int(nfeatures), fastThreshold=int(fast_threshold))
    kps, desc = orb.detectAndCompute(gray, None)
    if not kps or desc is None:
        return np.zeros((0, 2), np.float32), None
    pts = np.array([k.pt for k in kps], np.float32)
    return pts, desc


def match_ratio(desc_a, desc_b, ratio=0.75):
    if desc_a is None or desc_b is None or len(desc_a) < 2 or len(desc_b) < 2:
        return []
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    knn = bf.knnMatch(desc_a, desc_b, k=2)
    out = []
    for m in knn:
        if len(m) == 2 and m[0].distance < ratio * m[1].distance:
            out.append((int(m[0].queryIdx), int(m[0].trainIdx)))
    return out


def verify_relpose(pts_a, pts_b, matches, K, ransac_thresh=1.5, conf=0.999):
    """Geometrically verify a_i <-> b_j matches and recover X_b = R X_a + t.

    Returns None when there is no usable estimate, otherwise a dict with
    ``inliers``, ``matches``, ``R`` and unit ``t_dir``.
    """
    if len(matches) < 8:
        return None
    pa = np.array([pts_a[i] for i, _ in matches], np.float32)
    pb = np.array([pts_b[j] for _, j in matches], np.float32)
    E, mask = cv2.findEssentialMat(pa, pb, K, method=cv2.RANSAC,
                                   prob=conf, threshold=ransac_thresh)
    if E is None or mask is None:
        return None
    mask = mask.ravel().astype(bool)
    n_in = int(mask.sum())
    if n_in < 8:
        return {"inliers": n_in, "matches": len(matches), "R": None, "t_dir": None}
    _, R, t, mask2 = cv2.recoverPose(E, pa, pb, K, mask=mask.astype(np.uint8))
    return {"inliers": int(mask2.sum()), "matches": len(matches),
            "R": R, "t_dir": t.ravel()}


class PlaceRecognizer:
    """Incremental keyframe descriptor index with geometric verification."""

    def __init__(self, K, min_inliers=15, min_matches=20, min_gap=10, ratio=0.75):
        self.K = K
        self.min_inliers = int(min_inliers)
        self.min_matches = int(min_matches)
        self.min_gap = int(min_gap)
        self.ratio = float(ratio)
        self.entries = []

    def add(self, frame_no, pts, desc, R, t):
        self.entries.append({"frame": int(frame_no), "pts": pts, "desc": desc,
                             "R": R, "t": t})

    def query(self, frame_no, pts, desc, exclude_radius=None):
        """Return the best verified loop candidate for the current keyframe.

        The current keyframe plays the role of 'b'; the stored entry of
        'a'; the returned R/t_dir satisfy X_b = R X_a + t.
        """
        gap = self.min_gap if exclude_radius is None else int(exclude_radius)
        best = None
        for idx, e in enumerate(self.entries):
            if frame_no - e["frame"] < gap:
                continue
            m = match_ratio(desc, e["desc"], self.ratio)
            if len(m) < self.min_matches:
                continue
            remap = [(t, q) for q, t in m]
            v = verify_relpose(e["pts"], pts, remap, self.K,
                               ransac_thresh=self._thresh)
            if v is None or v["inliers"] < self.min_inliers:
                continue
            if best is None or v["inliers"] > best["inliers"]:
                best = {"index": idx, "frame": e["frame"],
                        "R": v["R"], "t_dir": v["t_dir"],
                        "inliers": v["inliers"], "matches": v["matches"]}
        return best

    _thresh = 1.5


class LoopEdge:
    __slots__ = ("i", "j", "R", "t_dir", "inliers", "frame_i", "frame_j")

    def __init__(self, i, j, R, t_dir, inliers=0, frame_i=None, frame_j=None):
        self.i = i
        self.j = j
        self.R = R
        self.t_dir = np.asarray(t_dir, float).ravel()
        self.inliers = int(inliers)
        self.frame_i = frame_i
        self.frame_j = frame_j


def detect_loops(keyframes, K, min_gap=10, min_inliers=15, min_matches=20):
    """Run place recognition over an ordered list of keyframes.

    Each keyframe is a dict with ``frame``, ``pts``, ``desc``, ``R``, ``t``.
    Returns a list of LoopEdge in detection order.
    """
    rec = PlaceRecognizer(K, min_inliers=min_inliers, min_matches=min_matches,
                          min_gap=min_gap)
    loops = []
    for j, kf in enumerate(keyframes):
        hit = rec.query(kf["frame"], kf["pts"], kf["desc"])
        if hit is not None:
            loops.append(LoopEdge(hit["index"], j, hit["R"], hit["t_dir"],
                                  inliers=hit["inliers"],
                                  frame_i=hit["frame"], frame_j=kf["frame"]))
        rec.add(kf["frame"], kf["pts"], kf["desc"], kf["R"], kf["t"])
    return loops


def umeyama_sim3(P, Q):
    """Least-squares similarity (s, R, t) mapping P -> Q (N x 3 each)."""
    P = np.asarray(P, float)
    Q = np.asarray(Q, float)
    mu_p = P.mean(axis=0)
    mu_q = Q.mean(axis=0)
    Pc = P - mu_p
    Qc = Q - mu_q
    cov = Qc.T @ Pc / len(P)
    U, S, Vt = np.linalg.svd(cov)
    d = np.sign(np.linalg.det(U @ Vt))
    D = np.diag([1.0, 1.0, d])
    R = U @ D @ Vt
    var_p = (Pc ** 2).sum() / len(P)
    s = float((S * np.diag(D)).sum() / var_p) if var_p > 0 else 1.0
    t = mu_q - s * R @ mu_p
    return s, R, t


def align_ate(P, Q):
    """Absolute trajectory error (RMS, metres) after a Sim3 alignment of P->Q."""
    P = np.asarray(P, float)
    Q = np.asarray(Q, float)
    s, R, t = umeyama_sim3(P, Q)
    Pa = (s * (R @ P.T)).T + t
    return float(np.sqrt(((Pa - Q) ** 2).sum(axis=1).mean()))


class PoseGraphSE3:
    """Pose graph over SE(3) keyframe poses.

    Nodes store world->cam poses.  Odometry edges are full relative-pose
    constraints; loop edges constrain the relative rotation exactly and the
    relative translation to ``scale * t_dir``.  Optimisation fixes a set of
    nodes (gauge) and runs Levenberg-Marquardt with central-difference
    Jacobians.
    """

    def __init__(self, w_odom=1.0, w_loop_rot=1.0, w_loop_trans=0.3):
        self.nodes = []
        self.odom = []
        self.loops = []
        self.w_odom = float(w_odom)
        self.w_loop_rot = float(w_loop_rot)
        self.w_loop_trans = float(w_loop_trans)

    def add_node(self, R, t):
        self.nodes.append([np.asarray(R, float), np.asarray(t, float).ravel()])
        return len(self.nodes) - 1

    def add_odom(self, i, j, R_rel, t_rel):
        self.odom.append((int(i), int(j), np.asarray(R_rel, float),
                          np.asarray(t_rel, float).ravel()))

    def add_loop(self, i, j, R_rel, t_dir, scale):
        self.loops.append((int(i), int(j), np.asarray(R_rel, float),
                           np.asarray(t_dir, float).ravel(), float(scale)))

    def _unpack(self, x, fixed):
        poses = []
        k = 0
        for idx in range(len(self.nodes)):
            if idx in fixed:
                poses.append(self.nodes[idx])
            else:
                w = x[k:k + 3]
                t = x[k + 3:k + 6]
                k += 6
                poses.append([exp_so3(w), t])
        return poses

    def _pack(self, fixed):
        x = []
        for idx in range(len(self.nodes)):
            if idx in fixed:
                continue
            R, t = self.nodes[idx]
            x.extend(log_so3(R))
            x.extend(np.asarray(t, float).ravel())
        return np.array(x, float)

    def _residuals(self, x, fixed):
        poses = self._unpack(x, fixed)
        res = []
        for (i, j, Rm, tm) in self.odom:
            dR, dt = relative_pose(poses[i][0], poses[i][1],
                                   poses[j][0], poses[j][1])
            res.extend(log_so3(Rm.T @ dR) * self.w_odom)
            res.extend((dt - tm) * self.w_odom)
        for (i, j, Rm, td, sc) in self.loops:
            dR, dt = relative_pose(poses[i][0], poses[i][1],
                                   poses[j][0], poses[j][1])
            res.extend(log_so3(Rm.T @ dR) * self.w_loop_rot)
            res.extend((dt - sc * td) * self.w_loop_trans)
        return np.array(res, float)

    def _numeric_jacobian(self, x, fixed, h=1e-6):
        r0 = self._residuals(x, fixed)
        J = np.zeros((len(r0), len(x)))
        for c in range(len(x)):
            xp = x.copy()
            xm = x.copy()
            xp[c] += h
            xm[c] -= h
            J[:, c] = (self._residuals(xp, fixed) - self._residuals(xm, fixed)) / (2 * h)
        return J, r0

    def optimize(self, fixed=(0,), max_iter=60, ftol=1e-10, lam0=1e-3):
        fixed = set(int(f) for f in fixed)
        x = self._pack(fixed)
        if len(x) == 0:
            return 0.0
        r = self._residuals(x, fixed)
        cost = 0.5 * float(r @ r)
        lam = float(lam0)
        for _ in range(int(max_iter)):
            J, _ = self._numeric_jacobian(x, fixed)
            g = J.T @ r
            H = J.T @ J
            improved = False
            step = None
            for _ in range(8):
                A = H + lam * np.diag(np.diag(H) + 1e-9)
                try:
                    step = np.linalg.solve(A, -g)
                except np.linalg.LinAlgError:
                    step = np.linalg.lstsq(A, -g, rcond=None)[0]
                xn = x + step
                rn = self._residuals(xn, fixed)
                cn = 0.5 * float(rn @ rn)
                if cn < cost:
                    x, r, cost = xn, rn, cn
                    lam = max(lam * 0.3, 1e-9)
                    improved = True
                    break
                lam *= 4.0
            if not improved:
                break
            if step is not None and np.linalg.norm(step) < ftol:
                break
        self.nodes = self._unpack(x, fixed)
        return cost

    def poses(self):
        return [(R.copy(), t.copy()) for R, t in self.nodes]

    def centers(self):
        return np.array([camera_center(R, t) for R, t in self.nodes])
