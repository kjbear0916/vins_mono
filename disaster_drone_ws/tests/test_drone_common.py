#!/usr/bin/env python3
"""Unit tests for drone_common geometry utils (shared across cores).
Run: python tests/test_drone_common.py
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))
from drone_common.drone_common import utils as cu  # noqa: E402


class TestDroneCommon(unittest.TestCase):
    def test_marker_floor(self):
        self.assertEqual(cu.marker_floor(101), 1)
        self.assertEqual(cu.marker_floor(216), 2)
        self.assertEqual(cu.marker_floor(309), 3)
        self.assertIsNone(cu.marker_floor(900))  # survivor, no floor in id

    def test_floor_from_z(self):
        self.assertEqual(cu.floor_from_z(0.35), 1)
        self.assertEqual(cu.floor_from_z(3.35), 2)
        self.assertEqual(cu.floor_from_z(6.35), 3)

    def test_flight_z(self):
        self.assertAlmostEqual(cu.flight_z(1), 1.8)
        self.assertAlmostEqual(cu.flight_z(2), 4.8)
        self.assertAlmostEqual(cu.flight_z(3), 7.8)

    def test_dist(self):
        self.assertAlmostEqual(cu.dist_xy((0, 0), (3, 4)), 5.0)
        self.assertAlmostEqual(cu.dist3d((0, 0, 0), (1, 1, 1)), np.sqrt(3))

    def test_clamp(self):
        self.assertEqual(cu.clamp(5, 0, 3), 3)
        self.assertEqual(cu.clamp(-5, 0, 3), 0)
        self.assertEqual(cu.clamp(1.5, 0, 3), 1.5)

    def test_heading(self):
        self.assertAlmostEqual(cu.heading_deg((0, 0), (1, 0)), 0.0)
        self.assertAlmostEqual(cu.heading_deg((0, 0), (0, 1)), 90.0)
        self.assertAlmostEqual(cu.heading_deg((0, 0), (-1, 0)), 180.0)

    def test_angle_normalize(self):
        self.assertAlmostEqual(cu.angle_normalize_deg(370.0), 10.0)
        self.assertAlmostEqual(cu.angle_normalize_deg(-90.0), -90.0)
        self.assertAlmostEqual(cu.angle_normalize_deg(190.0), -170.0)

    def test_rotation_z(self):
        R = cu.rotation_z_deg(90.0)
        expected = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
        np.testing.assert_allclose(R, expected, atol=1e-9)
        v = R @ np.array([1.0, 0.0, 0.0])
        np.testing.assert_allclose(v, [0.0, 1.0, 0.0], atol=1e-9)


if __name__ == "__main__":
    unittest.main(verbosity=2)