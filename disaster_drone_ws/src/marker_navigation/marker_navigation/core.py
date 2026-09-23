#!/usr/bin/env python3
# Copyright 2026. disaster_drone_ws marker navigation core (ROS-free, host-testable).
"""Route following over marker waypoints + atrium climb (spec SS8.5).

Consumes ``waypoint_routes.yaml`` and ``marker_map.yaml`` via config_loader;
pure geometry + state, no rclpy. The ROS node turns the selected waypoint
into an offboard setpoint.
"""

import math

import numpy as np


class RouteError(RuntimeError):
    pass


def _dist(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(np.linalg.norm(a - b))


class RouteFollower:
    """Walk the scene route floor by floor, holding position at each marker
    until reached, then advancing. Handles atrium_climb as a synthetic
    waypoint pair (hold_xy -> exit_xy) after the matching marker node.
    """

    def __init__(self, config, floor=1, arrival_m=0.8, hold_s=0.0):
        self.routes = config.routes()
        self.markers = config.markers()
        self._floor = int(floor)
        self._nodes = self._route_for(self._floor)
        self._idx = 0            # index in the current floor's node list
        self._arrival_m = float(arrival_m)
        self._hold_s = float(hold_s)
        self._hold_started = None
        self._climb_stage = 0    # 0=approach hold_xy, 1=exit_xy, 2=done
        self._pending_floor = None
        self._completed = False
        self.last_reason = "init"

    def _route_for(self, floor):
        key = f"floor_{int(floor)}"
        if key not in self.routes:
            raise RouteError(f"no route for floor {floor}")
        return list(self.routes[key])

    def _marker_pose(self, mid):
        try:
            return self.markers[int(mid)]
        except (KeyError, ValueError):
            raise RouteError(f"route references unknown marker {mid}")

    # -- state -----------------------------------------------------------
    @property
    def floor(self):
        return self._floor

    @property
    def current_index(self):
        return self._idx

    @property
    def total_nodes(self):
        return len(self._nodes)

    @property
    def completed(self):
        return self._completed

    # -- waypoint selection ---------------------------------------------
    def next_waypoint(self):
        """The next concrete waypoint (dict with x/y/z), skipping the synthetic
        atrium_climb entry — used by the node to publish a setpoint."""
        node = self._current_node()
        if node is None:
            return None
        if node.get("type") == "marker":
            return self._marker_pose(node["id"])
        return self._climb_waypoint(node)

    def _climb_waypoint(self, node):
        if self._climb_stage == 0:
            pos = _parse_xy(node.get("hold_xy"))
        elif self._climb_stage == 1:
            pos = _parse_xy(node.get("exit_xy"))
        else:
            raise RouteError(f"climb stage {self._climb_stage} out of range")
        return {"x": float(pos[0]), "y": float(pos[1]),
                "z": float(self._climb_target_z(node)), "climb": True}

    def _climb_target_z(self, node):
        from_floor = int(node.get("from_floor", self._floor))
        to_floor = int(node.get("to_floor", from_floor + 1))
        # flight altitude of the destination floor (scene_gen flight_z)
        return (to_floor - 1) * 3.0 + 1.8

    def _current_node(self):
        if self._idx >= len(self._nodes):
            return None
        return self._nodes[self._idx]

    # -- update / arrival ------------------------------------------------
    def update(self, pose_xyz, t_s):
        """Drive the state machine with the current fused pose. Returns the
        active waypoint dict (or None when the whole route is complete)."""
        node = self._current_node()
        if node is None:
            self._completed = True
            return None

        if node.get("type") == "marker":
            target = self._marker_pose(node["id"])
            if _dist(pose_xyz, (target["x"], target["y"], target["z"])) <= self._arrival_m:
                self._idx += 1
                self._climb_stage = 0
                if self._pending_floor is not None:
                    self._floor = int(self._pending_floor)
                    self._pending_floor = None
                self.last_reason = f"reached marker {node['id']}"
                return self.update(pose_xyz, t_s)  # skip to next
            return self.next_waypoint()

        # atrium_climb synthetic node
        if self._climb_stage >= 2:
            self._idx += 1
            self._climb_stage = 0
            self.last_reason = "climb finished"
            return self.update(pose_xyz, t_s)
        wp = self.next_waypoint()
        target_xy = (wp["x"], wp["y"])
        if _dist(pose_xyz[:2], target_xy) <= self._arrival_m:
            self._climb_stage += 1
            self.last_reason = f"climb stage {self._climb_stage} reached"
            if self._climb_stage < 2:
                return self.next_waypoint()
            # exit reached: finish this node and chain into the next floor
            self._idx += 1
            to_floor = int(node.get("to_floor", self._floor + 1))
            self._nodes = self._route_for(to_floor)
            self._idx = 0
            self._pending_floor = to_floor
            self.last_reason = f"climbed to floor {to_floor}"
            return self.update(pose_xyz, t_s)
        return wp


def _parse_xy(v):
    if isinstance(v, (list, tuple)):
        if len(v) != 2:
            raise RouteError(f"bad xy pair {v}")
        return float(v[0]), float(v[1])
    s = str(v).strip().strip("[]()").replace(" ", "")
    parts = [p for p in s.split(",") if p]
    if len(parts) != 2:
        raise RouteError(f"bad xy pair {v!r}")
    return float(parts[0]), float(parts[1])


def heading_to(pose_xyz, target_xyz):
    return float(math.degrees(math.atan2(target_xyz[1] - pose_xyz[1],
                                         target_xyz[0] - pose_xyz[0])))