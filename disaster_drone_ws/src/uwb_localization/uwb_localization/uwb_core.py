# Copyright 2026. disaster_drone_ws UWB core (ROS-free, host-testable) v1.
"""Pure UWB positioning logic: ranging model, anchor registry, trilateration.

Nothing in this module imports rclpy or any ROS package, so the Phase 5
math can be verified on the host with plain numpy/scipy.

Trilateration uses scipy.optimize.least_squares (spec SS8.3). The anchor
registry persists to ``deployed_anchors.yaml`` and is the permanent record
left for other rescue units (spec SS8.2).
"""

import os
import time

import numpy as np


class RegistryError(RuntimeError):
    pass


def _fmt(v):
    return f"{round(v, 3):.3f}".rstrip("0").rstrip(".")


def dump_anchors_yaml(path, anchors):
    lines = ["deployed_anchors:"]
    for a in anchors:
        lines.append("  -")
        lines.append(f"    id: {int(a['id'])}")
        lines.append(f"    x: {_fmt(a['x'])}")
        lines.append(f"    y: {_fmt(a['y'])}")
        lines.append(f"    z: {_fmt(a['z'])}")
        lines.append(f"    yaw: {_fmt(float(a.get('yaw', 0.0)))}")
        lines.append(f"    deployed_at_s: {_fmt(float(a.get('deployed_at_s', 0.0)))}")
        lines.append(f"    permanent: {bool(a.get('permanent', True))}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def _load_yaml_file(path):
    try:
        from ..drone_bringup.config_loader import load_yaml_file
    except ImportError:
        from drone_bringup.drone_bringup.config_loader import load_yaml_file
    return load_yaml_file(path)


def load_anchors_yaml(path):
    if not os.path.exists(path):
        return []
    data = _load_yaml_file(path).get("deployed_anchors", [])
    out = []
    for a in data:
        out.append({
            "id": int(a["id"]),
            "x": float(a["x"]),
            "y": float(a["y"]),
            "z": float(a["z"]),
            "yaw": float(a.get("yaw", 0.0)),
            "deployed_at_s": float(a.get("deployed_at_s", 0.0)),
            "permanent": bool(a.get("permanent", True)),
        })
    return out


class AnchorRegistry:
    """In-memory + persistent list of deployed UWB anchors (infinite supply,
    never removed once deployed)."""

    def __init__(self, filepath=None, now_fn=time.time):
        self._now = now_fn
        self._filepath = filepath or os.path.join(
            os.environ.get("DISASTER_WS", "."), "deployed_anchors.yaml")
        self._anchors = []
        self._next_id = 1
        self.load()

    def load(self):
        self._anchors = load_anchors_yaml(self._filepath)
        self._next_id = (max([a["id"] for a in self._anchors], default=0) + 1)

    def save(self):
        dump_anchors_yaml(self._filepath, self._anchors)

    def deploy(self, x, y, z, yaw=0.0, permanent=True):
        anchor = {
            "id": self._next_id,
            "x": float(x), "y": float(y), "z": float(z), "yaw": float(yaw),
            "deployed_at_s": self._now(),
            "permanent": permanent,
        }
        self._next_id += 1
        self._anchors.append(anchor)
        self.save()
        return anchor

    def as_list(self):
        return list(self._anchors)

    def count(self):
        return len(self._anchors)

    def nearest_within(self, x, y, z, radius_m):
        best, best_d = None, radius_m
        for a in self._anchors:
            d = ((a["x"] - x) ** 2 + (a["y"] - y) ** 2 + (a["z"] - z) ** 2) ** 0.5
            if d <= best_d:
                best, best_d = a, d
        return best


def ranging_measurement(drone_pose, anchor, effective_range_m, noise_std_m, rng=None):
    """Simulated UWB range: true distance + gaussian noise, range-capped.
    Returns None when beyond effective range (out-of-range / no fix)."""
    d = ((drone_pose[0] - anchor["x"]) ** 2 +
         (drone_pose[1] - anchor["y"]) ** 2 +
         (drone_pose[2] - anchor["z"]) ** 2) ** 0.5
    if d > effective_range_m:
        return None
    noise = (rng or np.random.default_rng()).normal(0.0, noise_std_m)
    return max(0.0, d + noise)


def in_range_ranges(drone_pose, anchors, effective_range_m, noise_std_m, rng=None):
    out = []
    for a in anchors:
        r = ranging_measurement(drone_pose, a, effective_range_m, noise_std_m, rng)
        if r is not None:
            out.append((a, r))
    return out


def trilaterate(anchors, ranges, z_guess=None, rms_threshold_m=1.0):
    """Least-squares 3D position from anchor centers and measured ranges.

    ``anchors``: (n,3) array of anchor world positions.
    ``ranges``:  (n,) measured ranges in meters.
    Returns ``(position_or_None, status, rms)`` where status is one of
    ``insufficient``, ``ok``, ``high_residual``.
    """
    anchors = np.asarray(anchors, dtype=float)
    ranges = np.asarray(ranges, dtype=float)
    if len(anchors) < 3 or len(ranges) != len(anchors):
        return None, "insufficient", np.inf

    def resid(p):
        return np.linalg.norm(anchors - p, axis=1) - ranges

    from scipy.optimize import least_squares
    x0 = np.array([anchors[:, 0].mean(), anchors[:, 1].mean(),
                   anchors[:, 2].mean()])
    if z_guess is not None:
        x0[2] = float(z_guess)
    try:
        result = least_squares(resid, x0, method="lm", max_nfev=500)
    except Exception:
        return None, "solver_error", np.inf
    pos = result.x
    rms = float(np.sqrt(np.mean(result.fun ** 2)))
    if pos[2] < -10.0 or pos[2] > 30.0:
        return None, "z_out_of_bounds", rms
    if rms <= rms_threshold_m:
        return pos, "ok", rms
    return pos, "high_residual", rms


def estimate_error(anchors, pos, ranges):
    """Mean abs error between anchor distances and ranges at pos (m)."""
    anchors = np.asarray(anchors, dtype=float)
    ranges = np.asarray(ranges, dtype=float)
    if len(anchors) == 0:
        return np.inf
    return float(np.mean(np.abs(np.linalg.norm(anchors - pos, axis=1) - ranges)))