#!/usr/bin/env python3
# Copyright 2026. disaster_drone_ws common geometry utils (ROS-free, host-testable).
"""Shared pure-math helpers used across package cores (spec §8 common).

Imports nothing from ROS. Kept dependency-light so every host test can
``from drone_common.utils import ...``.
"""

import math

import numpy as np

FLOOR_H = 3.0
SLAB = 0.30


def marker_floor(mid):
    """Floor from the ArUco id scheme: 1xx=1F, 2xx=2F, 3xx=3F. Survivors
    900-999 carry no floor in the id, so use z (see floor_from_z)."""
    mid = int(mid)
    if 100 <= mid <= 999 and mid % 1000 < 900:
        return mid // 100
    return None


def floor_from_z(z):
    """Floor 1..3 from world z (scene_gen slab top: 1F 0.35, 2F 3.35, 3F 6.35)."""
    return max(1, int(float(z) // FLOOR_H) + 1)


def flight_z(floor):
    """scene_gen flight altitude for a floor (matches make_scene.flight_z)."""
    return (int(floor) - 1) * FLOOR_H + 1.8


def dist3d(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return float(np.linalg.norm(a - b))


def dist_xy(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def heading_deg(from_xy, to_xy):
    """Bearing (deg, 0=+x/north, CCW) from one xy to another."""
    return float(math.degrees(math.atan2(to_xy[1] - from_xy[1],
                                         to_xy[0] - from_xy[0])))


def angle_normalize_deg(deg):
    d = float(deg) % 360.0
    if d > 180.0:
        d -= 360.0
    return d


def rotation_z_deg(yaw_deg):
    """SO(3) rotation about +z by yaw_deg (ENU, CCW)."""
    a = math.radians(float(yaw_deg))
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)