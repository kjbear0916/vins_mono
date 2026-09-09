import cv2
import numpy as np


def log_so3(R):
    w, _ = cv2.Rodrigues(R)
    return w.ravel()


def exp_so3(w):
    R, _ = cv2.Rodrigues(w)
    return R


def project(K, R, t, X):
    t = np.asarray(t).ravel()
    X = np.asarray(X).ravel()
    Xc = R @ X + t
    z = Xc[2]
    inv = 1.0 / z
    u = K[0, 0] * Xc[0] * inv + K[0, 2]
    v = K[1, 1] * Xc[1] * inv + K[1, 2]
    return u, v, z


def triangulate(K, R1, t1, R2, t2, o1, o2):
    P1 = K @ np.hstack([R1, t1.reshape(3, 1)])
    P2 = K @ np.hstack([R2, t2.reshape(3, 1)])
    X4 = cv2.triangulatePoints(P1, P2, o1.astype(np.float64),
                               o2.astype(np.float64))
    ok = X4[3] != 0
    X = np.zeros(3)
    if ok:
        X = (X4[:3] / X4[3]).ravel()
    return X


class BundleAdjuster:
    """Levenberg-Marquardt bundle adjustment over keyframe poses and 3D
    points, minimising reprojection error in pixels. Pure numpy -- no scipy.

    State layout: for each keyframe i: [log_so3(R_i) (3), t_i (3)], then for
    each point j: [X_j (3)]. Cameras use the world->cam convention
    (X_cam = R @ X_world + t)."""

    def __init__(self, K, kf_Rs, kf_ts, obs, pt_idx, max_iter=50,
                 ftol=1e-7, fixed=None, anchors=None, anchor_w=0.0,
                 rho=0.0, z_floor=0.05, z_w=200.0):
        self.K = K
        self.M = len(kf_Rs)
        self.N = (int(np.max(pt_idx)) + 1) if len(pt_idx) else 0
        self.rho = rho
        self.z_floor = z_floor
        self.z_w = z_w
        self.fixed = set()
        if fixed:
            for f in fixed:
                if 0 <= f < 6 * self.M + 3 * self.N:
                    self.fixed.add(f)
        self.anchors = anchors
        self.anchor_w = anchor_w
        self.obs_kf = obs[:, 0].astype(np.int32)
        self.obs_pt = obs[:, 1].astype(np.int32)
        self.obs_uv = obs[:, 2:4].astype(np.float64)
        self.pt_idx = np.asarray(pt_idx, np.int32)
        self.max_iter = max_iter
        self.ftol = ftol
        self.Rs = [R.copy() for R in kf_Rs]
        self.ts = [t.copy() for t in kf_ts]
        self.X = [np.zeros(3) for _ in range(self.N)]

    def _pack(self):
        w = np.concatenate([log_so3(self.Rs[i]) for i in range(self.M)])
        t = np.concatenate([self.ts[i].ravel() for i in range(self.M)])
        x = np.concatenate(self.X)
        return np.concatenate([w, t, x])

    def _unpack(self, p, Rs, ts, X):
        q = 3 * self.M
        for i in range(self.M):
            Rs[i] = exp_so3(p[3 * i:3 * i + 3])
            ts[i] = p[q + 3 * i:q + 3 * i + 3].copy()
        base = q + 3 * self.M
        for j in range(self.N):
            X[j] = p[base + 3 * j:base + 3 * j + 3].copy()

    def _residual(self, p):
        Rs = [np.eye(3) for _ in range(self.M)]
        ts = [np.zeros(3) for _ in range(self.M)]
        Xp = [np.zeros(3) for _ in range(self.N)]
        self._unpack(p, Rs, ts, Xp)
        nr = 2 * len(self.obs_kf) + 3 * len(self.anchors or [])
        r = np.empty(nr)
        for k in range(len(self.obs_kf)):
            i = self.obs_kf[k]
            j = self.obs_pt[k]
            u, v, z = project(self.K, Rs[i], ts[i], Xp[j])
            r[2 * k] = u - self.obs_uv[k, 0]
            r[2 * k + 1] = v - self.obs_uv[k, 1]
            if z < self.z_floor:
                # soft pull: penalize but keep it smooth and comparable
                # in scale to pixel residuals; robust rho down-weights it
                pen = self.z_w * (z - self.z_floor)
                r[2 * k] += pen
                r[2 * k + 1] += pen
        base = 2 * len(self.obs_kf)
        for a, (pj, xyz) in enumerate(self.anchors or []):
            d = Xp[pj] - xyz
            r[base + 3 * a] = self.anchor_w * d[0]
            r[base + 3 * a + 1] = self.anchor_w * d[1]
            r[base + 3 * a + 2] = self.anchor_w * d[2]
        return r

    def solve(self):
        p = self._pack()
        r = self._residual(p)
        cost = float(r @ r)
        lam = 1e-3
        for it in range(self.max_iter):
            J = self._jacobian(p)
            if self.rho > 0.0:
                w = 1.0 / (1.0 + (r / self.rho) ** 2)
                Jw = J * np.sqrt(w)[:, None]
                S = Jw.T @ Jw
                g = Jw.T @ (np.sqrt(w) * r)
            else:
                S = J.T @ J
                g = J.T @ r
            accept = False
            for _ in range(40):
                try:
                    d = np.linalg.solve(S + lam * np.diag(np.diag(S) + 1e-10),
                                        -g)
                except np.linalg.LinAlgError:
                    lam *= 10.0
                    continue
                pn = p + d
                for f in self.fixed:
                    pn[f] = p[f]
                rn = self._residual(pn)
                cn = float(rn @ rn)
                if cn < cost:
                    p, r, cost, lam = pn, rn, cn, max(lam / 3.0, 1e-8)
                    accept = True
                    break
                lam *= 10.0
                if lam > 1e12:
                    break
            if not accept or lam > 1e12:
                break
            if it and abs(cost - prev_cost) < self.ftol * max(cost, 1.0):
                break
            prev_cost = cost
        self._unpack(p, self.Rs, self.ts, self.X)
        return cost

    def _jacobian(self, p):
        base = self._residual(p)
        r = base.copy()
        n = len(p)
        m = len(base)
        cols = []
        for k in range(n):
            if k in self.fixed:
                cols.append(np.zeros(m))
                continue
            pc = p.copy()
            h = 1e-6 * max(abs(p[k]), 1.0)
            pc[k] += h
            dd = (self._residual(pc) - base) / h
            cols.append(dd)
        return np.stack(cols, axis=1)