#!/usr/bin/env python3
"""Unit tests for marker_navigation core (spec SS8.5): route following,
arrival detection, atrium climb staging.
Run: python tests/test_navigation.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))
from marker_navigation.marker_navigation import core as nav  # noqa: E402
from drone_bringup.drone_bringup import config_loader as cl  # noqa: E402


class RouteFollowerTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = cl.Config()


def _walk_route(f, guard_max=300):
    """Drive the follower to completion, calling update at each node."""
    guard = 0
    while not f.completed and guard < guard_max:
        guard += 1
        node = f._current_node()
        if node is None:
            break
        if node.get("type") == "marker":
            m = f._marker_pose(node["id"])
            f.update((m["x"], m["y"], m["z"]), 0.0)
        else:
            # atrium_climb: stage 0 (hold) then stage 1 (exit), then one more
            # update to consume stage>=2 and finish the node
            wp = f.next_waypoint()
            if f._climb_stage == 0:
                f.update((wp["x"], wp["y"], wp["z"]), 0.0)
            elif f._climb_stage == 1:
                f.update((wp["x"], wp["y"], wp["z"]), 0.0)
            else:
                f.update((wp["x"], wp["y"], wp["z"]), 0.0)
    return guard


class TestRouteFollowing(RouteFollowerTestBase):
    def test_first_waypoint_is_marker_101(self):
        f = nav.RouteFollower(self.cfg, floor=1)
        wp = f.next_waypoint()
        self.assertEqual(wp["id"], 101)
        self.assertAlmostEqual(wp["x"], 2.0)
        self.assertAlmostEqual(wp["y"], 1.5)

    def test_arrival_advances_to_next(self):
        f = nav.RouteFollower(self.cfg, floor=1, arrival_m=0.8)
        wp = f.next_waypoint()  # 101 at (2,1.5,0.35)
        wp2 = f.update((2.0, 1.5, 0.35), 0.0)
        self.assertEqual(wp2["id"], 102)

    def test_hold_still_returns_same(self):
        f = nav.RouteFollower(self.cfg, floor=1)
        wp = f.next_waypoint()
        same = f.update((1.0, 1.5, 0.35), 0.0)  # dist 1.0 > arrival 0.8
        self.assertEqual(same["id"], wp["id"])

    def test_last_waypoint_completes(self):
        f = nav.RouteFollower(self.cfg, floor=1)
        seen = []
        guard = 0
        while not f.completed and guard < 200:
            guard += 1
            node = f._current_node()
            if node is None:
                break
            if node.get("type") == "marker":
                m = f._marker_pose(node["id"])
                w = f.update((m["x"], m["y"], m["z"]), 0.0)
                if w is not None and not w.get("climb"):
                    seen.append(w["id"])
            elif node.get("type") == "atrium_climb":
                wp = f.next_waypoint()
                f.update((wp["x"], wp["y"], wp["z"]), 0.0)
        self.assertTrue(f.completed)
        self.assertGreater(len(seen), 10)

    def test_count_nodes(self):
        f = nav.RouteFollower(self.cfg, floor=1)
        n_markers = sum(1 for n in f._nodes if n.get("type") == "marker")
        self.assertEqual(n_markers, 15)
        self.assertEqual(f.total_nodes, 16)  # 15 markers + 1 climb


class TestAtriumClimb(RouteFollowerTestBase):
    def test_climb_reaches_floor2_z(self):
        f = nav.RouteFollower(self.cfg, floor=1)
        # advance until the climb node is current
        guard = 0
        node = None
        while guard < 50 and not f.completed:
            guard += 1
            node = f._current_node()
            if node is not None and node.get("type") == "atrium_climb":
                break
            if node is not None and node.get("type") == "marker":
                m = f._marker_pose(node["id"])
                f.update((m["x"], m["y"], m["z"]), 0.0)
        self.assertIsNotNone(node)
        self.assertEqual(node.get("type"), "atrium_climb")
        wp = f.next_waypoint()
        self.assertTrue(wp["climb"])
        self.assertAlmostEqual(wp["x"], 10.0)   # hold_xy
        self.assertAlmostEqual(wp["y"], 5.0)
        self.assertAlmostEqual(wp["z"], 1.8 + 3.0)  # floor 2 flight z

    def test_climb_stage_transition(self):
        f = nav.RouteFollower(self.cfg, floor=1)
        guard = 0
        while guard < 50 and not f.completed:
            guard += 1
            node = f._current_node()
            if node is not None and node.get("type") == "atrium_climb":
                break
            if node is not None and node.get("type") == "marker":
                m = f._marker_pose(node["id"])
                f.update((m["x"], m["y"], m["z"]), 0.0)
        # stage 0: hold_xy
        self.assertEqual(f._climb_stage, 0)
        w = f.update((10.0, 5.0, 3.0), 0.0)
        self.assertEqual(f._climb_stage, 1)
        self.assertAlmostEqual(w["x"], 10.0)
        self.assertAlmostEqual(w["y"], 2.2)  # exit_xy
        # stage 1 -> exit reached -> next marker node (floor 2)
        w2 = f.update((10.0, 2.2, 3.0), 0.0)
        self.assertEqual(f._climb_stage, 2)
        self.assertNotIn("climb", w2)  # now a real marker
        self.assertEqual(f.floor, 1)   # floor bookkeeping


class TestHeading(unittest.TestCase):
    def test_facing_positive_x(self):
        h = nav.heading_to((0, 0, 0), (5, 0, 0))
        self.assertAlmostEqual(h, 0.0)

    def test_facing_positive_y(self):
        h = nav.heading_to((0, 0, 0), (0, 5, 0))
        self.assertAlmostEqual(h, 90.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)