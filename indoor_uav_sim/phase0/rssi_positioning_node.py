#!/usr/bin/env python3
# rssi_positioning_node.py
# RSSI trilateration + Kalman filter positioning node.
# True drone pose comes from Gazebo pose/info via gz.transport13.
# Run with:  PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python python3 rssi_positioning_node.py
# Use --sim to run against synthetic motion (no Gazebo) for standalone validation.

import argparse
import math
import os
import threading
import time

import numpy as np

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

DEFAULT_APS = [
    (0.0, 0.0, 2.5),
    (8.0, 0.0, 2.5),
    (8.0, 8.0, 2.5),
    (0.0, 8.0, 2.5),
]
P0_DBM = -40.0       # RSSI at 1 m
PATH_LOSS = 2.2      # path loss exponent
RSSI_NOISE_SIGMA = 3.0  # dBm
SPAWN_POSE = (1.0, 1.0, 1.0)
POSE_TOPIC = "/world/default/pose/info"
DRONE_ENTITY = "x500_0"


def rssi_to_distance(rssi_db):
    return 10.0 ** ((P0_DBM - rssi_db) / (10.0 * PATH_LOSS))


def distance_to_rssi(distance):
    return P0_DBM - 10.0 * PATH_LOSS * math.log10(max(distance, 1e-6))


# ----------------------------------------------------------------------------
# True position source: Gazebo pose/info subscription
# ----------------------------------------------------------------------------

class TruePoseSource:
    def __init__(self):
        from gz import transport13
        from gz.msgs10 import pose_v_pb2

        self._pose_v_pb2 = pose_v_pb2
        self._node = transport13.Node()
        self._lock = threading.Lock()
        self._pose = None
        self._got = False

    def _cb(self, msg):
        for p in msg.pose:
            if p.name == DRONE_ENTITY:
                with self._lock:
                    self._pose = (p.position.x, p.position.y, p.position.z)
                    self._got = True
                return

    def start(self):
        self._node.subscribe(self._pose_v_pb2.Pose_V, POSE_TOPIC, self._cb)
        print(f"[true] subscribing {POSE_TOPIC} for {DRONE_ENTITY}")

    def stop(self):
        try:
            self._node.unsubscribe(POSE_TOPIC)
        except TypeError as exc:
            print(f"[true] unsubscribe failed (ignored): {exc}")

    def get(self):
        with self._lock:
            return self._pose


class SyntheticPoseSource:
    def __init__(self, period=30.0, radius=3.0, center=SPAWN_POSE, t0=None):
        self._period = period
        self._radius = radius
        self._center = np.array(center, dtype=float)
        self._t0 = t0 if t0 is not None else time.monotonic()

    def stop(self):
        pass

    def get(self):
        t = time.monotonic() - self._t0
        ang = 2.0 * math.pi * (t / self._period)
        x = self._center[0] + self._radius * math.cos(ang)
        y = self._center[1] + self._radius * math.sin(ang)
        z = self._center[2]
        return (x, y, z)


# ----------------------------------------------------------------------------
# RSSI measurement model
# ----------------------------------------------------------------------------

def rssi_measurement(aps, true_pos, rng):
    rssi = []
    for ap in aps:
        d = math.sqrt(sum((true_pos[i] - ap[i]) ** 2 for i in range(3)))
        rssi.append(distance_to_rssi(d) + rng.normal(0.0, RSSI_NOISE_SIGMA))
    return rssi


# ----------------------------------------------------------------------------
# Trilateration (non-linear least squares, Gauss-Newton)
# ----------------------------------------------------------------------------

def trilaterate(aps, distances, x0=None):
    aps = np.asarray(aps, dtype=float)
    distances = np.asarray(distances, dtype=float)

    if x0 is None:
        x = aps.mean(axis=0)
    else:
        x = np.asarray(x0, dtype=float).copy()

    lam = 0.1
    for _ in range(30):
        r = np.linalg.norm(aps - x, axis=1)
        r = np.maximum(r, 0.5)
        f = r - distances
        J = (x - aps) / r[:, None]
        try:
            A = J.T @ J + lam * np.eye(3)
            b = -J.T @ f
            dx = np.linalg.solve(A, b)
            x_new = x + dx
        except np.linalg.LinAlgError:
            break
        x = x_new
        if np.linalg.norm(dx) < 1e-6:
            break

    r = np.linalg.norm(aps - x, axis=1)
    r = np.maximum(r, 0.5)
    f = r - distances
    res_norm = np.linalg.norm(f)
    J = (x - aps) / r[:, None]
    try:
        cov = np.linalg.inv(J.T @ J + 0.01 * np.eye(3))
    except np.linalg.LinAlgError:
        cov = np.eye(3) * 1e2
    if not np.all(np.isfinite(x)):
        return None, None
    return x, res_norm


# ----------------------------------------------------------------------------
# Kalman filter (constant-velocity, XYZ independent)
# ----------------------------------------------------------------------------

class KalmanFilterXYZ:
    def __init__(self, dt, meas_cov, gate_sigma=5.0):
        self._dt = dt
        self._gate_sigma = gate_sigma
        self._x = np.zeros(6)
        self._P = np.eye(6) * 1e2

        F = np.eye(6)
        F[0, 1] = dt
        F[2, 3] = dt
        F[4, 5] = dt
        self._F = F

        accel_var = 1.0 ** 2
        Q = np.zeros((6, 6))
        for i in (0, 2, 4):
            Q[i, i] = 0.5 * accel_var * dt ** 2
            Q[i + 1, i + 1] = accel_var * dt ** 2
        self._Q = Q

        self._H = np.zeros((3, 6))
        self._H[0, 0] = 1.0
        self._H[1, 2] = 1.0
        self._H[2, 4] = 1.0
        self._R = np.asarray(meas_cov, dtype=float)

    def init(self, xyz):
        self._x = np.array([xyz[0], 0.0, xyz[1], 0.0, xyz[2], 0.0])

    def update(self, xyz):
        x_pred = self._F @ self._x
        P_pred = self._F @ self._P @ self._F.T + self._Q

        z = np.asarray(xyz, dtype=float)
        innov = z - self._H @ x_pred
        S = self._H @ P_pred @ self._H.T + self._R
        dist = float(innov @ np.linalg.solve(S, innov))

        max_innov = self._gate_sigma * np.sqrt(np.diag(S))
        clip = np.minimum(1.0, max_innov / np.maximum(np.abs(innov), 1e-9))
        innov_clipped = innov * clip

        K = P_pred @ self._H.T @ np.linalg.inv(S)
        self._x = x_pred + K @ innov_clipped
        self._P = (np.eye(6) - K @ self._H) @ P_pred
        return self._x[[0, 2, 4]]

    def get(self):
        return self._x[[0, 2, 4]]


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="RSSI trilateration + Kalman positioning node")
    ap.add_argument("--sim", action="store_true", help="synthetic motion instead of Gazebo pose")
    ap.add_argument("--rate", type=float, default=10.0, help="update rate in Hz")
    ap.add_argument("--duration", type=float, default=25.0, help="run for this many seconds")
    ap.add_argument("--aps", type=str, default="",
                    help="comma list of x,y,z per AP (pad groups with commas if <3 coords); default 4 APs at z=2.5")
    args = ap.parse_args()

    if args.aps.strip():
        toks = [float(t) for t in args.aps.replace(";", ",").split(",")]
        aps = [tuple(toks[i:i + 3]) for i in range(0, len(toks), 3)]
        if any(len(g) != 3 for g in aps) or not aps:
            ap.error("--aps needs groups of exactly 3 floats")
        for g in aps:
            if len(g) != 3:
                ap.error("--aps must be groups of exactly 3 floats")
    else:
        aps = DEFAULT_APS
    print(f"[aps] {aps}")

    dt = 1.0 / args.rate

    if args.sim:
        true_src = SyntheticPoseSource()
    else:
        true_src = TruePoseSource()
        true_src.start()

    est = KalmanFilterXYZ(dt, [9.0, 9.0, 25.0])
    init_fixes = []
    first = True
    rng = np.random.default_rng(seed=1234)
    GOOD_SQ_SIZE = 25.0

    t0 = time.monotonic()
    last_err = None
    try:
        while True:
            elapsed = time.monotonic() - t0
            if elapsed >= args.duration:
                break

            true = true_src.get()
            if true is None:
                time.sleep(0.1)
                continue

            if args.sim:
                gt = np.array(true)
            else:
                gt = np.array(true)

            rssi = rssi_measurement(aps, gt, rng)
            dists = [rssi_to_distance(r) for r in rssi]
            x_fix, res_norm = trilaterate(aps, dists)

            if x_fix is None or res_norm > GOOD_SQ_SIZE:
                continue

            if first:
                init_fixes.append(x_fix)
                if len(init_fixes) < 5:
                    continue
                est.init(np.median(np.array(init_fixes), axis=0))
                first = False
                continue
            est_xyz = est.update(x_fix)

            err_xyz = gt - est_xyz
            err_xy = math.hypot(err_xyz[0], err_xyz[1])
            err_3d = np.linalg.norm(err_xyz)
            last_err = (err_xy, err_3d, float(gt[2]), float(est_xyz[2]))

            print(f"[{elapsed:6.1f}s] true=({gt[0]:6.2f},{gt[1]:6.2f},{gt[2]:6.2f}) "
                  f"est =({est_xyz[0]:6.2f},{est_xyz[1]:6.2f},{est_xyz[2]:6.2f}) "
                  f"errXY={err_xy:5.2f}m err3D={err_3d:5.2f}m")

            time.sleep(max(0.0, dt - (time.time() % dt)))
    finally:
        true_src.stop()

    if last_err:
        print(f"\n[summary] last XY error={last_err[0]:.2f}m  3D={last_err[1]:.2f}m  "
              f"true z={last_err[2]:.2f}  est z={last_err[3]:.2f}")


if __name__ == "__main__":
    main()