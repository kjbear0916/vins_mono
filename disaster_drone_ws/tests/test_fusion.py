#!/usr/bin/env python3
"""Unit tests for pose fusion engine (spec SS8.4 source switching).

Pure-Python verification of the ArUco -> UWB -> ArUco state machine.
Run: python tests/test_fusion.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))
from pose_fusion.pose_fusion import fusion_core as fc  # noqa: E402
from drone_bringup.drone_bringup import config_loader as cl  # noqa: E402


class TestFusionEngineSwitching(unittest.TestCase):
    def test_starts_aruco(self):
        f = fc.FusionEngine()
        self.assertEqual(f.source, fc.SOURCE_ARUCO)

    def test_marker_seen_keeps_aruco(self):
        f = fc.FusionEngine(miss_threshold=10, reentry_frames=3, require_zone=True)
        for _ in range(50):
            src = f.update(marker_detected=True, near_zone=False)
            self.assertEqual(src, fc.SOURCE_ARUCO)
        self.assertEqual(f._miss, 0)
        self.assertEqual(f.lost_seconds, 0.0)

    def test_miss_below_threshold_stays_aruco(self):
        f = fc.FusionEngine(miss_threshold=10, require_zone=True)
        for _ in range(9):
            src = f.update(marker_detected=False, near_zone=True)
            self.assertEqual(src, fc.SOURCE_ARUCO)
        self.assertEqual(f._miss, 9)
        self.assertAlmostEqual(f.lost_seconds, 0.9)

    def test_miss_past_threshold_in_zone_switches_to_uwb(self):
        f = fc.FusionEngine(miss_threshold=10, require_zone=True)
        src = fc.SOURCE_ARUCO
        for _ in range(10):
            src = f.update(marker_detected=False, near_zone=True)
        self.assertEqual(src, fc.SOURCE_UWB)
        self.assertEqual(f.last_reason, "markers lost inside occlusion zone")

    def test_miss_past_threshold_outside_zone_stays_aruco(self):
        f = fc.FusionEngine(miss_threshold=10, require_zone=True)
        src = fc.SOURCE_ARUCO
        for _ in range(10):
            src = f.update(marker_detected=False, near_zone=False)
        self.assertEqual(src, fc.SOURCE_ARUCO, "should NOT switch outside a marked zone")

    def test_no_zone_crossing_without_require_zone(self):
        # require_zone=False still respects an explicit False (caller says
        # "definitely not near a zone"): near_zone=None means "unknown, don't care"
        f = fc.FusionEngine(miss_threshold=3, require_zone=False)
        src = fc.SOURCE_ARUCO
        for _ in range(3):
            src = f.update(marker_detected=False, near_zone=False)
        self.assertEqual(src, fc.SOURCE_ARUCO)

    def test_crosses_without_zone_when_zone_unknown(self):
        f = fc.FusionEngine(miss_threshold=3, require_zone=False)
        src = fc.SOURCE_ARUCO
        for _ in range(3):
            src = f.update(marker_detected=False, near_zone=None)
        self.assertEqual(src, fc.SOURCE_UWB)

    def test_reentry_flips_back(self):
        f = fc.FusionEngine(miss_threshold=3, reentry_frames=3, require_zone=True)
        for _ in range(3):
            f.update(marker_detected=False, near_zone=True)  # -> UWB
        self.assertEqual(f.source, fc.SOURCE_UWB)
        src = fc.SOURCE_UWB
        for _ in range(2):
            src = f.update(marker_detected=True, near_zone=True)
            self.assertEqual(src, fc.SOURCE_UWB)  # not enough consecutive yet
        src = f.update(marker_detected=True, near_zone=True)  # 3rd consecutive
        self.assertEqual(src, fc.SOURCE_ARUCO)
        self.assertEqual(f.last_reason, "marker re-acquired")

    def test_accumulates_lost_seconds(self):
        f = fc.FusionEngine(miss_threshold=10)
        for _ in range(10):
            f.update(marker_detected=False, near_zone=True, dt_s=0.2)
        self.assertAlmostEqual(f.lost_seconds, 2.0)

    def test_reset(self):
        f = fc.FusionEngine(miss_threshold=3, require_zone=True)
        for _ in range(3):
            f.update(marker_detected=False, near_zone=True)
        self.assertEqual(f.source, fc.SOURCE_UWB)
        f.reset()
        self.assertEqual(f.source, fc.SOURCE_ARUCO)
        self.assertEqual(f._miss, 0)
        self.assertEqual(f._seen, 0)
        self.assertEqual(f.last_reason, "reset")


class TestFusePose(unittest.TestCase):
    def test_aruco_pose_selected(self):
        aruco = {"x": 1.0, "y": 2.0, "confidence": 0.9}
        uwb = {"x": 9.0, "y": 9.0}
        pose, src, conf = fc.fuse(aruco, uwb, fc.SOURCE_ARUCO)
        self.assertEqual(pose, aruco)
        self.assertEqual(src, fc.SOURCE_ARUCO)
        self.assertEqual(conf, 0.9)

    def test_uwb_pose_selected(self):
        aruco = {"x": 1.0, "y": 2.0}
        uwb = {"x": 9.0, "y": 9.0, "confidence": 0.7}
        pose, src, conf = fc.fuse(aruco, uwb, fc.SOURCE_UWB)
        self.assertEqual(pose, uwb)
        self.assertEqual(src, fc.SOURCE_UWB)
        self.assertEqual(conf, 0.7)

    def test_aruco_none_returns_zero_conf(self):
        pose, src, conf = fc.fuse(None, {"x": 1.0}, fc.SOURCE_ARUCO)
        self.assertEqual(src, fc.SOURCE_ARUCO)
        self.assertEqual(conf, 0.0)


class TestNearRiskZoneRealConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = cl.Config()
        cls.M = cls.cfg.markers()
        cls.Z = cls.cfg.zones()

    def test_real_config_loads(self):
        self.assertGreater(len(self.M), 0)
        self.assertGreater(len(self.Z), 0)

    def test_atrium_109_inside(self):
        # atrium_1F triggers at waypoint 109 (x=10, y=2.2), radius 5
        inside = fc.near_risk_zone(10.0, 5.0, 0.35, self.Z, self.M)
        self.assertTrue(inside)

    def test_far_from_everything_outside(self):
        outside = fc.near_risk_zone(0.0, 0.0, 0.0, self.Z, self.M)
        self.assertFalse(outside)

    def test_survivor_marker_not_trigger(self):
        # markers like 900 (survivor) are not zone triggers
        self.assertEqual(self.cfg.zone_for_waypoint(900), [])

    def test_all_zone_triggers_exist_as_markers(self):
        for z in self.Z:
            mid = int(z.get("trigger_waypoint", -1))
            self.assertIn(mid, self.M, f"zone {z.get('id')} triggers missing marker {mid}")


if __name__ == "__main__":
    unittest.main(verbosity=2)