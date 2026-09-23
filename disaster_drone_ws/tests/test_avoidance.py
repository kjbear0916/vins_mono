#!/usr/bin/env python3
"""Unit tests for obstacle_avoidance core (spec SS8.7): sector logic.
Run: python tests/test_avoidance.py
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))
from obstacle_avoidance.obstacle_avoidance import core as oa  # noqa: E402


def free(clear=20.0):
    return [float(clear)] * oa.N_SECTORS


class TestAvoidance(unittest.TestCase):
    def test_all_free_baseline(self):
        av = oa.ObstacleAvoidance(stop_range_m=1.0, slow_range_m=2.0)
        cmd = av.update(free())
        self.assertFalse(cmd["stopping"])
        self.assertFalse(av.active)
        self.assertGreater(cmd["vx"], 0.5)
        self.assertEqual(cmd["yaw_rate_deg_s"], 0.0)

    def test_blocked_dead_ahead_stops(self):
        av = oa.ObstacleAvoidance(stop_range_m=1.0, slow_range_m=2.0)
        r = free(0.5)  # 20 cm obstacle dead ahead (sector 0 = forward)
        cmd = av.update(r)
        self.assertTrue(cmd["stopping"])
        self.assertEqual(cmd["vx"], 0.0)

    def test_obstacle_in_slow_band_rotates(self):
        av = oa.ObstacleAvoidance(stop_range_m=1.0, slow_range_m=2.0)
        r = free(1.5)  # obstacle 1.5 m ahead
        cmd = av.update(r)
        self.assertNotEqual(cmd["yaw_rate_deg_s"], 0.0)
        self.assertLess(cmd["vx"], 1.0)
        self.assertTrue(av.active)

    def test_obstacle_on_left_turns_clockwise_away(self):
        """Obstacle at +90 deg (left side in ENU, since +y is left) -> negative
        yaw_rate (clockwise turn away), still translating slowly."""
        av = oa.ObstacleAvoidance(stop_range_m=1.0, slow_range_m=2.0, turn_rate_deg=30.0)
        r = free(clear=10.0)  # far everywhere
        left_sector = int(90 // oa.SECTOR_DEG) % oa.N_SECTORS
        r[left_sector] = 1.3  # only the left band is near
        cmd = av.update(r)
        self.assertTrue(av.active)
        self.assertFalse(cmd["stopping"])
        self.assertLess(cmd["yaw_rate_deg_s"], 0.0)  # clockwise (away from +y)

    def test_min_sector_bounds(self):
        av = oa.ObstacleAvoidance()
        with self.assertRaises(ValueError):
            av.update(np.zeros(5))

    def test_front_clear_gate(self):
        r = free()
        self.assertTrue(oa.front_clear(r))
        r[0] = 1.0
        self.assertFalse(oa.front_clear(r, threshold_m=1.5))

    def test_sector_occupied(self):
        r = [float("inf")] * oa.N_SECTORS
        self.assertFalse(oa.sector_occupied(r, 0, 1.0))
        r[3] = 0.5
        self.assertTrue(oa.sector_occupied(r, 3, 1.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)