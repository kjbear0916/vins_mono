#!/usr/bin/env python3
"""Unit tests for UWB core: trilateration math, ranging model, anchor registry.

Host-side verification of the Phase 5 math (spec SS8.2 / SS8.3) — no ROS,
no Gazebo. Run from the workspace root:
    python tests/test_trilateration.py
    python -m unittest discover -s tests
"""
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))
from uwb_localization.uwb_localization import uwb_core as uc  # noqa: E402


def classic_anchors():
    return np.array([[0, 0, 0], [5, 0, 0], [0, 5, 0], [0, 0, 5]], dtype=float)


class TestTrilaterationExact(unittest.TestCase):
    def test_exact_distances(self):
        anchors = classic_anchors()
        true = np.array([2.0, 2.0, 2.0])
        ranges = np.linalg.norm(anchors - true, axis=1)
        pos, status, rms = uc.trilaterate(anchors, ranges)
        self.assertEqual(status, "ok")
        self.assertLess(np.linalg.norm(pos - true), 1e-6)

    def test_near_floor(self):
        anchors = classic_anchors()
        true = np.array([1.0, 4.0, 0.3])
        ranges = np.linalg.norm(anchors - true, axis=1)
        pos, status, rms = uc.trilaterate(anchors, ranges)
        self.assertEqual(status, "ok")
        self.assertLess(np.linalg.norm(pos - true), 1e-6)

    def test_4_anchor_minimum(self):
        anchors = np.array([[0, 0, 0], [6, 0, 0], [0, 6, 0], [3, 3, 5]], dtype=float)
        true = np.array([2.0, 2.0, 1.0])
        ranges = np.linalg.norm(anchors - true, axis=1)
        pos, status, rms = uc.trilaterate(anchors, ranges)
        self.assertEqual(status, "ok")
        self.assertLess(np.linalg.norm(pos - true), 0.1)


class TestTrilaterationDegenerate(unittest.TestCase):
    def test_too_few_anchors(self):
        anchors = np.array([[0, 0, 0], [5, 0, 0]])
        pos, status, rms = uc.trilaterate(anchors, np.array([3.0, 3.0]))
        self.assertIsNone(pos)
        self.assertEqual(status, "insufficient")

    def test_mismatched_lengths(self):
        anchors = classic_anchors()
        pos, status, rms = uc.trilaterate(anchors, np.array([1.0, 2.0, 3.0]))
        self.assertEqual(status, "insufficient")

    def test_z_out_of_bounds(self):
        anchors = np.array([[0, 0, 0], [8, 0, 0], [0, 8, 0], [4, 4, 6]], dtype=float)
        true = np.array([2.0, 2.0, 40.0])  # outside allowed band
        ranges = np.linalg.norm(anchors - true, axis=1)
        pos, status, rms = uc.trilaterate(anchors, ranges)
        self.assertIsNone(pos)
        self.assertEqual(status, "z_out_of_bounds")

    def test_z_guess_used(self):
        anchors = classic_anchors()
        true = np.array([2.0, 2.0, 2.0])
        ranges = np.linalg.norm(anchors - true, axis=1)
        pos, status, rms = uc.trilaterate(anchors, ranges, z_guess=2.0)
        self.assertEqual(status, "ok")
        self.assertLess(np.linalg.norm(pos - true), 1e-6)


class TestTrilaterationNoisy(unittest.TestCase):
    def test_noisy_recovery(self):
        np.random.seed(42)
        anchors = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 8]], dtype=float)
        true = np.array([3.0, 4.0, 2.5])
        ranges = np.linalg.norm(anchors - true, axis=1)
        errors = []
        nr_success = 0
        for _ in range(100):
            noisy = ranges + np.random.normal(0, 0.2, len(ranges))
            pos, status, rms = uc.trilaterate(anchors, noisy)
            if pos is not None:
                nr_success += 1
                errors.append(np.linalg.norm(pos - true))
        self.assertGreater(nr_success, 80)
        self.assertLess(np.mean(errors), 1.0)

    def test_out_of_range_anchors_excluded(self):
        anchors = np.array([[0, 0, 0], [5, 0, 0], [0, 5, 0], [0, 0, 5], [50, 50, 50]],
                           dtype=float)
        true = np.array([2.0, 2.0, 2.0])
        ranges = np.linalg.norm(anchors - true, axis=1)
        mask = ranges <= 15.0
        pos, status, rms = uc.trilaterate(anchors[mask], ranges[mask])
        self.assertEqual(status, "ok")
        self.assertLess(np.linalg.norm(pos - true), 0.1)


class TestRangingModel(unittest.TestCase):
    def _anchors(self):
        return [{"id": 1, "x": 0.0, "y": 0.0, "z": 0.0},
                {"id": 2, "x": 5.0, "y": 0.0, "z": 0.0},
                {"id": 3, "x": 0.0, "y": 5.0, "z": 0.0}]

    def test_in_range_noisy(self):
        rng = np.random.default_rng(0)
        drone = (1.0, 1.0, 1.0)
        ms = uc.in_range_ranges(drone, self._anchors(), 15.0, 0.2, rng)
        self.assertEqual(len(ms), 3)
        for a, v in ms:
            true_d = np.linalg.norm(np.array(drone) - np.array([a["x"], a["y"], a["z"]]))
            self.assertLess(abs(v - true_d), 1.0)

    def test_out_of_range_none(self):
        drone = (0.0, 0.0, 0.0)
        r = uc.ranging_measurement(drone, {"x": 50.0, "y": 0.0, "z": 0.0}, 15.0, 0.2,
                                   np.random.default_rng(0))
        self.assertIsNone(r)

    def test_noise_never_negative(self):
        rng = np.random.default_rng(123)
        for _ in range(500):
            r = uc.ranging_measurement((0.0, 0.0, 0.0), {"x": 0.05, "y": 0.0, "z": 0.0},
                                       15.0, 0.2, rng)
            self.assertIsNotNone(r)
            self.assertGreaterEqual(r, 0.0)


class TestAnchorRegistry(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "anchors.yaml")
            reg = uc.AnchorRegistry(filepath=path, now_fn=lambda: 100.0)
            a1 = reg.deploy(1.0, 2.0, 3.0, yaw=0.5)
            a2 = reg.deploy(4.0, 5.0, 6.0, permanent=False)
            self.assertEqual([a1["id"], a2["id"]], [1, 2])
            self.assertTrue(a1["permanent"])
            self.assertFalse(a2["permanent"])
            self.assertEqual(reg.count(), 2)
            # reload from disk
            reg2 = uc.AnchorRegistry(filepath=path)
            self.assertEqual(reg2.count(), 2)
            self.assertEqual([a["id"] for a in reg2.as_list()], [1, 2])
            self.assertEqual(reg2.as_list()[1]["permanent"], False)
            self.assertEqual(reg2.as_list()[0]["yaw"], 0.5)
            self.assertEqual(reg2.as_list()[0]["deployed_at_s"], 100.0)

    def test_next_id_continues(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "anchors.yaml")
            reg = uc.AnchorRegistry(filepath=path)
            reg.deploy(0, 0, 0)
            reg.deploy(0, 0, 1)
            reg2 = uc.AnchorRegistry(filepath=path)
            a3 = reg2.deploy(0, 0, 2)
            self.assertEqual(a3["id"], 3)

    def test_nearest_within(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "anchors.yaml")
            reg = uc.AnchorRegistry(filepath=path)
            reg.deploy(0, 0, 0)
            reg.deploy(5, 5, 5)
            near = reg.nearest_within(0.2, 0.1, 0.0, 1.0)
            self.assertEqual(near["id"], 1)
            far = reg.nearest_within(5.4, 5.0, 5.0, 1.0)
            self.assertEqual(far["id"], 2)
            none = reg.nearest_within(50, 50, 50, 3.0)
            self.assertIsNone(none)

    def test_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            reg = uc.AnchorRegistry(filepath=os.path.join(td, "missing.yaml"))
            self.assertEqual(reg.count(), 0)
            self.assertEqual(reg.as_list(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)