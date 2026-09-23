#!/usr/bin/env python3
"""Unit tests for survivor_detection core (spec SS8.8).
Run: python tests/test_survivor.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))
from survivor_detection.survivor_detection import core as sc  # noqa: E402
from drone_bringup.drone_bringup import config_loader as cl  # noqa: E402


class TestSurvivorTracker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.map = cl.Config().markers()

    def _tracker(self, min_conf=0.5):
        return sc.SurvivorTracker(self.map, min_confidence=min_conf)

    def test_classify(self):
        t = self._tracker()
        self.assertEqual(t.classify(900), "survivor")
        self.assertEqual(t.classify(901), "survivor")
        self.assertEqual(t.classify(101), "waypoint")
        self.assertEqual(t.classify(99999), "unknown")

    def test_new_survivor_reported_on_first_confirm(self):
        t = self._tracker()
        dets = [{"marker_id": 900, "confidence": 0.9, "x": 3.0, "y": 12.5, "z": 0.35}]
        reps = t.update(dets, 10.0)
        self.assertEqual(len(reps), 1)
        r = reps[0]
        self.assertEqual(r["marker_id"], 900)
        self.assertEqual(r["floor"], 1)
        self.assertEqual(r["n_detections"], 1)
        self.assertEqual(r["confidence"], 0.9)

    def test_duplicate_not_re_reported(self):
        t = self._tracker()
        dets = [{"marker_id": 900, "confidence": 0.9, "x": 3.0, "y": 12.5, "z": 0.35}]
        reps1 = t.update(dets, 10.0)
        reps2 = t.update(dets, 11.0)  # same id again
        self.assertEqual(len(reps1), 1)
        self.assertEqual(len(reps2), 0)
        self.assertEqual(t.count(), 1)

    def test_low_confidence_filtered(self):
        t = self._tracker(min_conf=0.8)
        dets = [{"marker_id": 900, "confidence": 0.4, "x": 3.0, "y": 12.5, "z": 0.35}]
        reps = t.update(dets, 1.0)
        self.assertEqual(reps, [])
        self.assertEqual(t.count(), 0)

    def test_waypoint_markers_ignored(self):
        t = self._tracker()
        dets = [{"marker_id": 101, "confidence": 0.9, "x": 2.0, "y": 1.5, "z": 0.35}]
        reps = t.update(dets, 1.0)
        self.assertEqual(reps, [])
        self.assertEqual(t.reported_ids(), [])

    def test_all_three_survivors_report(self):
        t = self._tracker()
        all_ids = [900, 901, 902]
        for mid in all_ids:
            m = self.map[mid]
            reps = t.update([{"marker_id": mid, "confidence": 0.95,
                              "x": m["x"], "y": m["y"], "z": m["z"]}], float(mid))
            self.assertEqual(len(reps), 1)
            self.assertEqual(t.classify(mid), "survivor")
        self.assertEqual(sorted(t.reported_ids()), all_ids)
        self.assertEqual(t.count(), 3)

    def test_floor_from_z(self):
        self.assertEqual(sc._floor_from_z(0.35), 1)
        self.assertEqual(sc._floor_from_z(3.35), 2)
        self.assertEqual(sc._floor_from_z(6.35), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)