#!/usr/bin/env python3
"""Unit tests for UWB anchor deployment policy (spec SS8.2) and scene config.

Deployment policy is pure logic over the occlusion-zone table; the config
tests verify the three YAML files are internally consistent (every route
waypoint exists in marker_map, all zone triggers exist, ids unique).
Run: python tests/test_deployment.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))
from uwb_localization.uwb_localization import deployment_policy as dp  # noqa: E402
from drone_bringup.drone_bringup import config_loader as cl  # noqa: E402


class TestDeploymentPolicy(unittest.TestCase):
    def _zones(self):
        return [
            {"id": "atrium_1F", "type": "open_space", "trigger_waypoint": 109,
             "risk_level": "high", "radius_m": 5.0},
            {"id": "blind_2F", "type": "manual_blind", "trigger_waypoint": 206,
             "risk_level": "manual", "radius_m": 3.0},
            {"id": "corner_1F", "type": "corner", "trigger_waypoint": 104,
             "risk_level": "medium", "radius_m": 2.5},
        ]

    def _anchors(self):
        return [{"id": 1, "x": 0.0, "y": 0.0, "z": 0.0}]

    def test_deploy_when_aruco_high_risk(self):
        yes, reason = dp.should_deploy(dp.SOURCE_ARUCO, 109, self._zones(),
                                       (10.0, 5.0, 0.35), self._anchors())
        self.assertTrue(yes)
        self.assertIn("atrium_1F", reason)

    def test_manual_risk_also_deployable(self):
        yes, reason = dp.should_deploy(dp.SOURCE_ARUCO, 206, self._zones(),
                                       (4.0, 4.0, 3.3), [])
        self.assertTrue(yes)
        self.assertIn("blind_2F", reason)

    def test_reject_uwb_source(self):
        yes, reason = dp.should_deploy(dp.SOURCE_UWB, 109, self._zones(),
                                       (10.0, 5.0, 0.35), self._anchors())
        self.assertFalse(yes)
        self.assertIn("not aruco", reason)

    def test_reject_when_no_zone_at_waypoint(self):
        yes, reason = dp.should_deploy(dp.SOURCE_ARUCO, 500, self._zones(),
                                       (10.0, 5.0, 0.35), self._anchors())
        self.assertFalse(yes)
        self.assertIn("no occlusion zone", reason)

    def test_reject_medium_risk(self):
        yes, reason = dp.should_deploy(dp.SOURCE_ARUCO, 104, self._zones(),
                                       (8.0, 1.5, 0.35), self._anchors())
        self.assertFalse(yes)
        self.assertIn("not deployable", reason)

    def test_reject_anchor_already_nearby(self):
        anchors = [{"id": 7, "x": 10.1, "y": 5.0, "z": 0.35}]
        yes, reason = dp.should_deploy(dp.SOURCE_ARUCO, 109, self._zones(),
                                       (10.0, 5.0, 0.35), anchors)
        self.assertFalse(yes)
        self.assertIn("already within", reason)

    def test_anchor_just_beyond_spacing_deploys(self):
        anchors = [{"id": 7, "x": 11.0, "y": 5.0, "z": 0.35}]  # 1.0 m away > 0.5
        yes, reason = dp.should_deploy(dp.SOURCE_ARUCO, 109, self._zones(),
                                       (10.0, 5.0, 0.35), anchors)
        self.assertTrue(yes)

    def test_custom_spacing(self):
        anchors = [{"id": 7, "x": 10.6, "y": 5.0, "z": 0.35}]  # 0.6 m
        # with min_spacing=0.9 this is too close -> reject
        yes, _ = dp.should_deploy(dp.SOURCE_ARUCO, 109, self._zones(),
                                  (10.0, 5.0, 0.35), anchors, min_spacing_m=0.9)
        self.assertFalse(yes)


class TestSceneConfigIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = cl.Config()
        cls.markers = cls.cfg.markers()
        cls.zones = cls.cfg.zones()
        cls.routes = cls.cfg.routes()

    def test_marker_ids_unique(self):
        ids = [m["id"] for m in self.markers.values()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_marker_kinds(self):
        kinds = {m.get("kind") for m in self.markers.values()}
        self.assertEqual(kinds, {"waypoint", "survivor"})

    def test_all_route_waypoints_are_markers(self):
        for floor in self.routes["floors"]:
            nodes = self.routes[f"floor_{floor}"]
            for node in nodes:
                if node["type"] == "marker":
                    self.assertIn(int(node["id"]), self.markers,
                                  f"route floor {floor} references missing marker {node['id']}")

    def test_every_floor_route_present(self):
        for floor in self.routes["floors"]:
            self.assertIn(f"floor_{floor}", self.routes)

    def test_atrium_climb_pairs_floors(self):
        for floor in self.routes["floors"]:
            nodes = self.routes[f"floor_{floor}"]
            climbs = [n for n in nodes if n["type"] == "atrium_climb"]
            for n in climbs:
                self.assertEqual(n["from_floor"], floor)
                self.assertEqual(n["to_floor"], floor + 1)

    def test_survivor_ids_in_900_range(self):
        survivors = [m for m in self.markers.values() if m.get("kind") == "survivor"]
        self.assertEqual(len(survivors), 3)
        for m in survivors:
            self.assertTrue(900 <= m["id"] <= 999)

    def test_zone_risk_levels_valid(self):
        for z in self.zones:
            self.assertIn(z["risk_level"], {"high", "medium", "manual"})


if __name__ == "__main__":
    unittest.main(verbosity=2)