#!/usr/bin/env python3
"""Unit tests for mission_control core (spec SS8.6): FSM transitions and the
MissionStatus.msg-shaped status dict.
Run: python tests/test_mission.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))
from mission_control.mission_control import core as mc  # noqa: E402
from marker_navigation.marker_navigation import core as nav  # noqa: E402
from drone_bringup.drone_bringup import config_loader as cl  # noqa: E402


class TestMissionFSM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = cl.Config()

    def _fsm(self):
        route = nav.RouteFollower(self.cfg, floor=1)
        return mc.MissionFSM(route)

    def test_initial_status_shape(self):
        fsm = self._fsm()
        s = fsm.status()
        self.assertEqual(set(s), {"state", "current_floor", "current_waypoint",
                                  "total_waypoints", "deployed_anchors", "note"})
        self.assertEqual(s["state"], "IDLE")
        self.assertEqual(s["current_floor"], 1)
        self.assertEqual(s["deployed_anchors"], 0)
        self.assertEqual(s["total_waypoints"], 16)

    def test_takeoff_complete(self):
        fsm = self._fsm()
        self.assertEqual(fsm.on_takeoff_complete(), "NAVIGATE")

    def test_first_update_navigates(self):
        fsm = self._fsm()
        state, wp = fsm.on_waypoint_update((1.0, 1.5, 0.35), 0.0)
        self.assertEqual(state, "NAVIGATE")
        self.assertEqual(wp["id"], 101)

    def test_bad_state_rejected(self):
        fsm = self._fsm()
        with self.assertRaises(ValueError):
            fsm.transition("NOPE")

    def test_anchor_tracking(self):
        fsm = self._fsm()
        fsm.on_anchor_deployed()
        fsm.on_anchor_deployed()
        self.assertEqual(fsm.status()["deployed_anchors"], 2)
        fsm.on_anchor_deployed(count=5)
        self.assertEqual(fsm.status()["deployed_anchors"], 5)

    def test_run_route_to_hold(self):
        fsm = self._fsm()
        guard = 0
        while guard < 300 and fsm.state != "HOLD":
            guard += 1
            node = fsm.route._current_node()
            if node is None:
                break
            if node.get("type") == "marker":
                m = fsm.route._marker_pose(node["id"])
                fsm.on_waypoint_update((m["x"], m["y"], m["z"]), 0.0)
            else:
                fsm.on_waypoint_update((10.0, 5.0, 3.0), 0.0)
                fsm.on_waypoint_update((10.0, 2.2, 3.0), 0.0)
        self.assertEqual(fsm.state, "HOLD")
        s = fsm.status()
        self.assertTrue(s["current_waypoint"] >= 0 or s["state"] == "HOLD")

    def test_enter_climb_state(self):
        fsm = self._fsm()
        guard = 0
        entered_climb = False
        while guard < 200 and fsm.state != "HOLD":
            guard += 1
            node = fsm.route._current_node()
            if node is None:
                break
            if node.get("type") == "marker":
                m = fsm.route._marker_pose(node["id"])
                state, wp = fsm.on_waypoint_update((m["x"], m["y"], m["z"]), 0.0)
            else:
                state, wp = fsm.on_waypoint_update((10.0, 5.0, 3.0), 0.0)
                fsm.on_waypoint_update((10.0, 2.2, 3.0), 0.0)
            if wp is not None and wp.get("climb"):
                entered_climb = True
                self.assertEqual(state, "CLIMB")
        self.assertTrue(entered_climb)


if __name__ == "__main__":
    unittest.main(verbosity=2)