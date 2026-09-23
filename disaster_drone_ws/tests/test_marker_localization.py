#!/usr/bin/env python3
"""Unit tests for marker_localization core (spec SS8.1).

Verifies the solvePnP helper round-trips a synthetic marker, the camera->world
frame transform is a proper ENU rotation, and the simulation fallback rules.
Run: python tests/test_marker_localization.py
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))
from marker_localization.marker_localization import core as mc  # noqa: E402
from drone_common.drone_common import utils as cu  # noqa: E402


def cam_intrinsics(fx=500.0, fy=500.0, cx=320.0, cy=240.0):
    return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=float)


class TestEstimateMarkerPose(unittest.TestCase):
    def test_center_marker_roundtrip(self):
        """A marker at a known off-center camera pose, projected then
        re-estimated, recovers tvec within tolerance. Off-centre avoids the
        symmetric-coplanar mirror ambiguity of solvePnP."""
        size = 0.25
        K = cam_intrinsics()
        tvec_true = np.array([0.3, -0.2, 3.0])
        hw = size / 2.0
        obj = np.array([[-hw, hw, 0], [hw, hw, 0],
                        [hw, -hw, 0], [-hw, -hw, 0]])
        # pinhole project, no distortion
        px = (obj[:, 0] + tvec_true[0]) * 500.0 / tvec_true[2] + 320.0
        py = (obj[:, 1] + tvec_true[1]) * 500.0 / tvec_true[2] + 240.0
        img = np.stack([px, py], axis=1)
        ok, tvec, rvec = mc.estimate_marker_pose(img, size, K)
        self.assertTrue(ok)
        self.assertEqual(tvec.shape, (3,))
        self.assertLess(np.linalg.norm(tvec - tvec_true), 0.05)


def cv2_rodrigues(rvec):
    import cv2
    R, _ = cv2.Rodrigues(np.asarray(rvec, dtype=float))
    return R, None


class TestWorldFromCamPose(unittest.TestCase):
    def test_forward_marker_in_enu(self):
        """Level forward camera at origin, marker 3 m ahead -> world (3,0,0).
        The marker's right edge (optical +x) maps to world -y, so its yaw in
        the ENU convention is -90 deg (faces the camera)."""
        tvec = np.array([0.0, 0.0, 3.0])
        rvec = np.zeros(3)
        pos, yaw = mc.world_from_cam_pose(np.zeros(3), tvec, rvec)
        self.assertLess(np.linalg.norm(pos - np.array([3.0, 0.0, 0.0])), 1e-6)
        self.assertAlmostEqual(yaw, -90.0, places=5)

    def test_marker_right_of_camera_maps_to_negative_y(self):
        """Marker 1 m to camera-right (optical +x) at 3 m ahead -> world y=-1,
        camera offset in world frame shifts the result by cam_world."""
        tvec = np.array([1.0, 0.0, 3.0])
        pos, _ = mc.world_from_cam_pose(np.array([10.0, 20.0, 5.0]), tvec, np.zeros(3))
        self.assertAlmostEqual(pos[0], 13.0, places=5)   # +x forward
        self.assertAlmostEqual(pos[1], 19.0, places=5)   # -y right
        self.assertAlmostEqual(pos[2], 5.0, places=5)

    def test_yaw_rotation(self):
        """Drone yaw 90 deg: forward (+x) becomes world +y."""
        tvec = np.array([0.0, 0.0, 3.0])
        pos, _ = mc.world_from_cam_pose(np.zeros(3), tvec, np.zeros(3),
                                        body_yaw_rad=np.pi / 2)
        self.assertLess(np.linalg.norm(pos - np.array([0.0, 3.0, 0.0])), 1e-6)

    def test_is_proper_rotation(self):
        R = mc.R_CAM_TO_LEVEL
        self.assertAlmostEqual(np.linalg.det(R), 1.0, places=6)
        np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-9)


class TestSimulatedDetection(unittest.TestCase):
    def setUp(self):
        self.map = {
            101: {"id": 101, "x": 2.0, "y": 1.5, "z": 0.35, "kind": "waypoint",
                  "size": 0.25, "yaw": 0.0},
            900: {"id": 900, "x": 3.0, "y": 12.5, "z": 0.35, "kind": "survivor",
                  "size": 0.25, "yaw": 0.0},
        }

    def test_nearby_marker_visible(self):
        d = mc.simulated_detection(101, self.map, (1.0, 1.5, 0.35))
        self.assertIsNotNone(d)
        self.assertEqual(d["marker_id"], 101)
        self.assertEqual(d["confidence"], 1.0)
        self.assertEqual(d["x"], 2.0)

    def test_distant_marker_flagged(self):
        d = mc.simulated_detection(101, self.map, (50.0, 50.0, 0.35))
        self.assertIsNotNone(d)
        self.assertEqual(d["confidence"], 0.0)

    def test_unknown_marker(self):
        self.assertIsNone(mc.simulated_detection(9999, self.map, (0, 0, 0)))


if __name__ == "__main__":
    unittest.main(verbosity=2)