#!/usr/bin/env python3
# Copyright 2026. disaster_drone_ws obstacle avoidance core (ROS-free, host-testable).
"""LiDAR-based reactive avoidance (spec SS8.7).

Simplified but testable: the drone holds a desired heading/speed vector and
the lidar returns range buckets. We produce a corrected velocity command
that (a) stops when blocked closer than the hard stop, (b) rotates away from
the nearest obstacle band, (c) returns to baseline once clear.
No rclpy; the node reads the LiDAR scan and applies the returned vector.
"""

import math

import numpy as np

# LiDAR sector layout: 18 sectors x 20 deg, 0 deg = forward (+x).
N_SECTORS = 18
SECTOR_DEG = 360.0 / N_SECTORS


def _band(deg):
    d = ((int(deg) % 360) + 360) % 360
    return int(d // SECTOR_DEG) % N_SECTORS


class ObstacleAvoidance:
    def __init__(self, stop_range_m=1.0, slow_range_m=2.0, min_range_m=0.3,
                 turn_deg=40.0, baseline_vx=1.0, baseline_vy=0.0, turn_rate_deg=30.0):
        self.stop = float(stop_range_m)
        self.slow = float(slow_range_m)
        self.min_r = float(min_range_m)
        self.turn = float(turn_deg)
        self.baseline = (float(baseline_vx), float(baseline_vy))
        self.turn_rate = float(turn_rate_deg)
        self.active = False
        self.last_cmd = None

    def update(self, ranges, heading_deg=0.0):
        """ranges: length N_SECTORS list/array of meters (inf = free).
        Returns a command dict {vx, vy, yaw_rate_deg_s, stopping} where
        (vx, vy) is in the drone's body frame rotated to world by not needed
        here — the node applies yaw_rate itself. Pure sector logic."""
        r = np.asarray(ranges, dtype=float)
        if r.size != N_SECTORS:
            raise ValueError(f"expected {N_SECTORS} sectors, got {r.size}")

        min_r = float(np.min(r))
        min_idx = int(np.argmin(r))
        self.last_cmd = {}

        if min_r <= self.stop or min_r <= self.min_r:
            # blocked dead ahead or closer than min -> halt
            return {"vx": 0.0, "vy": 0.0, "yaw_rate_deg_s": 0.0, "stopping": True}

        near = min_r <= self.slow
        if min_r <= self.slow + 0.2:  # danger band
            # turn away from the nearest obstacle, keep progressing slowly
            theta = min_idx * SECTOR_DEG
            # prefer the sector opposite the obstacle heading in +x frame
            away_deg = (theta + 180.0) % 360.0
            # compute the yaw error to away direction in the -180..180 sense
            turn = _angle_to(0.0, away_deg)
            yaw_rate = self.turn_rate * (1.0 if turn >= 0 else -1.0) * (1.0 if near else 0.5)
            vx = 0.3 if near else 0.7
            self.active = True
            return {"vx": vx, "vy": 0.0, "yaw_rate_deg_s": float(yaw_rate),
                    "stopping": min_r <= self.stop}
        self.active = False
        return {"vx": float(self.baseline[0]), "vy": float(self.baseline[1]),
                "yaw_rate_deg_s": 0.0, "stopping": False}


def _angle_to(heading_deg, target_deg):
    d = (target_deg - heading_deg) % 360.0
    if d > 180.0:
        d -= 360.0
    return d


def sector_occupied(ranges, sector_idx, threshold_m):
    r = float(ranges[sector_idx])
    return math.isfinite(r) and r <= threshold_m


def front_clear(ranges, threshold_m=1.5, front_half_deg=40.0):
    """True when all sectors within front_half_deg of forward are beyond
    threshold — used as a gate to resume navigation."""
    for i in range(N_SECTORS):
        center = (i * SECTOR_DEG) % 360.0
        # shortest angular distance from forward (0 deg)
        d = _angle_to(0.0, center)
        if abs(d) <= front_half_deg:
            if float(ranges[i]) <= threshold_m:
                return False
    return True